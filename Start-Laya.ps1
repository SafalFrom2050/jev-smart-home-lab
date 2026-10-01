param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$pidPath = Join-Path $taskRoot 'laya-server.pid'
if (Test-Path -LiteralPath $pidPath) {
    $savedPid = [int](Get-Content -LiteralPath $pidPath)
    $existing = Get-Process -Id $savedPid -ErrorAction SilentlyContinue
    if ($existing -and $existing.Path -eq $taskPython) {
        Write-Host "Laya is already running (PID $savedPid). http://127.0.0.1:$Port"
        exit 0
    }
}
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Local Python environment is missing.' }
$logDir = Join-Path $taskRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$server = Start-Process -FilePath $taskPython -ArgumentList @('smart_home_server.py', '--host', '127.0.0.1', '--port', "$Port") -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'server.stdout.log') -RedirectStandardError (Join-Path $logDir 'server.stderr.log') -PassThru
Set-Content -LiteralPath $pidPath -Value $server.Id
Write-Host "Laya started (PID $($server.Id)). http://127.0.0.1:$Port"
Write-Host 'Startup and errors: logs\server.stderr.log. Stop with .\Stop-Laya.ps1'
