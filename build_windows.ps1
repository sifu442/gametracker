$ErrorActionPreference = "Stop"

$python = ""
if (Test-Path ".\.venv\Scripts\python.exe") {
    $python = ".\.venv\Scripts\python.exe"
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $python = ".\venv\Scripts\python.exe"
} else {
    $python = "python"
}

Write-Host "[build] using python: $python"

& $python -m pip install --upgrade pip pyinstaller
& $python -m PyInstaller --noconfirm --clean .\gametracker.spec

Write-Host ""
Write-Host "[build] done"
Write-Host "Output: .\\dist\\GameTracker\\"
