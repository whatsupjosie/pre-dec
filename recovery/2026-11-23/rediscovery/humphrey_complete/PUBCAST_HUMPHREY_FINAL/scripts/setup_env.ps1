Param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
}

$venvPython = Join-Path (Resolve-Path ".venv") "Scripts\python.exe"

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements\dev.txt

Write-Host "Virtual environment ready. Activate it with:`n.\\.venv\\Scripts\\Activate.ps1"
