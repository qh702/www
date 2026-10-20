$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

python -m PyInstaller --noconfirm --clean `
    --distpath "$root\dist" `
    --workpath "$root\build" `
    "$root\SignalConsoleFixed.spec"

Write-Host "Build complete: $root\dist\SignalConsoleFixed.exe"
