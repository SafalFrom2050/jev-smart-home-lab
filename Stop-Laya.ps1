$ErrorActionPreference = 'Stop'
$pidPath = Join-Path $PSScriptRoot 'laya-server.pid'
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Host 'No saved Laya server PID.'; exit 0 }
$savedPid = [int](Get-Content -LiteralPath $pidPath)
$server = Get-Process -Id $savedPid -ErrorAction SilentlyContinue
if ($server) {
    $taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if ($server.Path -ne $taskPython) { throw "PID $savedPid belongs to another program; leaving it alone." }
    Stop-Process -Id $savedPid
}
Remove-Item -LiteralPath $pidPath
Write-Host 'Laya stopped.'
