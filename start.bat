@echo off
setlocal enabledelayedexpansion
title Universal Media Downloader ^& Converter - Local Engine

echo ============================================================================
echo   UNIVERSAL MEDIA DOWNLOADER ^& CONVERTER (Windows Local Edition)
echo ============================================================================
echo.

cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links" set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links"

:: 1. Check Python availability
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.12+ was not found in your system PATH.
    echo         Install Python from https://www.python.org/downloads/
    echo         or run: winget install Python.Python.3.12
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [OK] Found %PYVER%

:: 2. Create Python virtual environment if necessary
if not exist "backend\.venv\Scripts\python.exe" (
    echo [SETUP] Creating Python virtual environment in backend\.venv ...
    python -m venv "backend\.venv"
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: 3. Install or update backend requirements if necessary
if not exist "backend\.venv\.deps_installed" (
    echo [SETUP] Installing backend dependencies (FastAPI, Uvicorn, yt-dlp, Pydantic)...
    "backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
    "backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install backend Python packages.
        pause
        exit /b 1
    )
    echo installed > "backend\.venv\.deps_installed"
) else (
    echo [OK] Backend Python dependencies verified.
)

:: 4. Check Node.js and install frontend dependencies if necessary
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js / npm was not found in your system PATH.
    echo         Install Node.js LTS via: winget install OpenJS.NodeJS.LTS
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo [SETUP] Installing frontend dependencies (React, TypeScript, Vite, Tailwind)...
    pushd "frontend"
    call npm install
    if !errorlevel! neq 0 (
        popd
        echo [ERROR] npm install failed.
        pause
        exit /b 1
    )
    popd
) else (
    echo [OK] Frontend node_modules verified.
)

:: 5. Check FFmpeg and FFprobe availability
where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] FFmpeg was not detected on your system PATH.
    echo           Install via: winget install Gyan.FFmpeg
    echo           Or set a custom FFmpeg path inside the Settings tab.
) else (
    echo [OK] FFmpeg detected on system PATH.
)

:: 6. Start Backend (127.0.0.1:8000) and Frontend (127.0.0.1:5173)
echo.
echo [LAUNCH] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "UMT Backend (FastAPI)" /D "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [LAUNCH] Starting Vite React Frontend on http://127.0.0.1:5173 ...
start "UMT Frontend (Vite)" /D "%~dp0frontend" cmd /k "npm run dev"

:: 7. Wait until servers are ready, then open local web application in default browser
echo [WAIT] Waiting for backend and frontend servers to become ready...
powershell -NoProfile -Command "$deadline = (Get-Date).AddSeconds(20); while ((Get-Date) -lt $deadline) { try { $b = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/settings' -UseBasicParsing -TimeoutSec 2; $f = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 2; if ($b.StatusCode -eq 200 -and $f.StatusCode -eq 200) { break } } catch {}; Start-Sleep -Milliseconds 500 }"
echo [OPEN] Opening http://127.0.0.1:5173 in your default browser...
start "" "http://127.0.0.1:5173"

echo.
echo Universal Media Downloader ^& Converter is running locally.
endlocal
