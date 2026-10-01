@echo off
title DevPilot - AI Engineering Platform
echo ===================================================
echo   Starting DevPilot AI Engineering Platform...
echo ===================================================
echo.

cd /d "%~dp0"

echo [1/2] Checking environment and launching server...
start "" http://localhost:8000

where uv >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Using uv ultra-fast runner...
    uv run uvicorn app.main:app --app-dir backend --port 8000 --reload
) else (
    echo Using system Python runner...
    set PYTHONPATH=backend
    python -m uvicorn app.main:app --app-dir backend --port 8000 --reload
)

pause
