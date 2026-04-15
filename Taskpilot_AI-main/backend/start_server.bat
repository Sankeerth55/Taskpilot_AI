@echo off
REM TaskPilot AI Backend - Quick Start Script for Windows
REM This script starts the backend server with proper configuration

cd /d "%~dp0"

echo.
echo ================================================
echo   TaskPilot AI Backend - Starting Server
echo ================================================
echo.

REM Check if we're in the backend directory
if not exist "app\main.py" (
    echo [ERROR] Please run this script from the backend directory
    exit /b 1
)

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call venv\Scripts\activate.bat
) else if exist "env\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call env\Scripts\activate.bat
) else (
    echo [WARN] No virtual environment found.
    echo [INFO] Using system Python...
)

REM Check if .env file exists
if not exist ".env" (
    echo [WARN] .env file not found!
    echo [INFO] Creating .env from .env.example...
    if exist ".env.example" (
        copy .env.example .env
        echo [SUCCESS] Created .env file
        echo [ACTION] Please edit .env and add your GEMINI_API_KEY
    ) else (
        echo [ERROR] .env.example not found!
        exit /b 1
    )
)

REM Check if dependencies are installed
echo [INFO] Checking dependencies...
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo [WARN] Dependencies not installed!
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        exit /b 1
    )
    echo [SUCCESS] Dependencies installed
    echo.
)

REM Verify Gemini configuration (optional, set START_VERIFY_GEMINI=1 to enable)
if /I "%START_VERIFY_GEMINI%"=="1" (
    echo.
    echo [INFO] Running Gemini verification...
    python verify_gemini.py
    if errorlevel 1 (
        echo [WARN] Verification failed, but server can still run with fallbacks
    )
    echo.
)

REM Start the server
echo.
echo ================================================
echo   Starting FastAPI Server
echo ================================================
echo.
echo [INFO] Server will be available at:
echo        http://127.0.0.1:8000
echo        http://127.0.0.1:8000/docs (API Documentation)
echo.
echo [INFO] Press Ctrl+C to stop the server
echo.

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

REM If server exits unexpectedly
echo.
echo [INFO] Server stopped
