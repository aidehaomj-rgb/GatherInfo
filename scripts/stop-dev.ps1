$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $ProjectDir ".dev-pids"

if (Test-Path $PidFile) {
  Get-Content $PidFile | ForEach-Object {
    $ProcessId = [int]$_
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($Process) {
      Write-Host "[dev] Stopping PID=$ProcessId ($($Process.ProcessName))"
      Stop-Process -Id $ProcessId -Force
    }
  }
  Remove-Item -Path $PidFile -ErrorAction SilentlyContinue
} else {
  Write-Host "[dev] No .dev-pids file found. Checking default ports..."
}

$Ports = @(8109, 5178, 5179)
foreach ($Port in $Ports) {
  Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $Process = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    if ($Process) {
      Write-Host "[dev] Stopping port $Port PID=$($Process.Id) ($($Process.ProcessName))."
      Stop-Process -Id $Process.Id -Force
    }
  }
}
