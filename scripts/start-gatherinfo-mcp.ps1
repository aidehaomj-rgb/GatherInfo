$env:GATHERINFO_API_URL = if ($env:GATHERINFO_API_URL) { $env:GATHERINFO_API_URL } else { "http://127.0.0.1:8110/api/v1" }
& "$PSScriptRoot\..\backend\.venv\Scripts\python.exe" "$PSScriptRoot\..\backend\mcp_server.py"
