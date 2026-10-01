# DevPilot PowerShell 1-Click Launcher
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  DevPilot - Autonomous AI Engineering Platform    " -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Open browser after a slight delay
Start-Process "http://localhost:8000"

if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "[+] Running with Astral uv on http://localhost:8000..." -ForegroundColor Green
    uv run uvicorn app.main:app --app-dir backend --port 8000 --reload
} else {
    Write-Host "[+] Running with Python on http://localhost:8000..." -ForegroundColor Yellow
    $env:PYTHONPATH = "backend"
    python -m uvicorn app.main:app --app-dir backend --port 8000 --reload
}
