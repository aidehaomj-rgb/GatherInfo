$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
$BackendPython = Join-Path $ProjectDir "backend\.venv\Scripts\python.exe"
$PidFile = Join-Path $ProjectDir ".dev-pids"

function Resolve-NpmCommand {
  $NpmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if ($NpmCmd) {
    return $NpmCmd.Source
  }

  $CommonNpm = Join-Path $env:ProgramFiles "nodejs\npm.cmd"
  if (Test-Path $CommonNpm) {
    return $CommonNpm
  }

  $Npm = Get-Command npm -ErrorAction SilentlyContinue
  if ($Npm) {
    return $Npm.Source
  }

  return $null
}

function Get-PortOwner {
  param([int]$Port)

  $Connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if (!$Connection) {
    return $null
  }

  $Process = Get-Process -Id $Connection.OwningProcess -ErrorAction SilentlyContinue
  return [PSCustomObject]@{
    Port = $Port
    Pid = $Connection.OwningProcess
    Name = if ($Process) { $Process.ProcessName } else { "unknown" }
  }
}

function Assert-PortAvailable {
  param([int]$Port, [string]$ServiceName)

  $Owner = Get-PortOwner -Port $Port
  if ($Owner) {
    Write-Host "ERROR: $ServiceName port $Port is already in use by PID $($Owner.Pid) ($($Owner.Name))."
    Write-Host "Open the existing service, or stop it before starting a new dev session."
    exit 1
  }
}

if (!(Test-Path $BackendPython)) {
  Write-Host "ERROR: backend virtual environment is missing."
  Write-Host "Run: python -m venv backend\.venv"
  Write-Host "Then: backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt"
  exit 1
}

$NpmCommand = Resolve-NpmCommand
if (!$NpmCommand) {
  Write-Host "ERROR: npm was not found in PATH. Install Node.js/npm before starting the frontend."
  exit 1
}
$NodeDir = Split-Path -Parent $NpmCommand
if ($env:PATH -notlike "*$NodeDir*") {
  $env:PATH = "$NodeDir;$env:PATH"
}

$LogDir = Join-Path $ProjectDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Assert-PortAvailable -Port 8109 -ServiceName "Backend"
Assert-PortAvailable -Port 5178 -ServiceName "Frontend"
Remove-Item -Path $PidFile -ErrorAction SilentlyContinue

Write-Host "[dev] Starting backend on http://127.0.0.1:8109 ..."
$Backend = Start-Process -FilePath $BackendPython `
  -ArgumentList @("-m", "uvicorn", "app.main:create_app", "--factory", "--host", "127.0.0.1", "--port", "8109", "--app-dir", "backend") `
  -WorkingDirectory $ProjectDir `
  -RedirectStandardOutput (Join-Path $LogDir "backend.log") `
  -RedirectStandardError (Join-Path $LogDir "backend.err.log") `
  -PassThru `
  -WindowStyle Hidden

Write-Host "[dev] Starting frontend on http://127.0.0.1:5178 ..."
$Frontend = Start-Process -FilePath $NpmCommand `
  -ArgumentList @("--prefix", "frontend", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5178") `
  -WorkingDirectory $ProjectDir `
  -RedirectStandardOutput (Join-Path $LogDir "frontend.log") `
  -RedirectStandardError (Join-Path $LogDir "frontend.err.log") `
  -PassThru `
  -WindowStyle Hidden

Write-Host "[dev] Backend PID=$($Backend.Id) Frontend PID=$($Frontend.Id)"
Set-Content -Path $PidFile -Value @($Backend.Id, $Frontend.Id)
Write-Host "[dev] Press Ctrl+C to stop both servers."

try {
  while ($true) {
    Start-Sleep -Seconds 2
    if ($Backend.HasExited) {
      Write-Host "[dev] Backend exited. See logs\backend.log and logs\backend.err.log."
      exit $Backend.ExitCode
    }
    if ($Frontend.HasExited) {
      Write-Host "[dev] Frontend exited. See logs\frontend.log and logs\frontend.err.log."
      exit $Frontend.ExitCode
    }
  }
}
finally {
  if (!$Backend.HasExited) { Stop-Process -Id $Backend.Id -Force }
  if (!$Frontend.HasExited) { Stop-Process -Id $Frontend.Id -Force }
  Remove-Item -Path $PidFile -ErrorAction SilentlyContinue
}
