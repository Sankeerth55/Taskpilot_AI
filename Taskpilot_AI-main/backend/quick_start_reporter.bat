@echo off
REM Quick Start Script for ReporterAgent Upgrade
REM This script installs dependencies and tests the upgraded system

echo ============================================================
echo TaskPilot AI - ReporterAgent Upgrade Quick Start
echo ============================================================
echo.

echo [1/3] Installing dependencies...
echo.
cd backend
pip install -q transformers torch sentencepiece

echo.
echo [2/3] Installing other requirements...
echo.
pip install -q -r requirements.txt

echo.
echo [3/3] Running tests...
echo.
python test_reporter_upgrade.py

echo.
echo ============================================================
echo Installation Complete!
echo ============================================================
echo.
echo To start the server:
echo   cd backend
echo   python -m uvicorn app.main:app --reload --port 8000
echo.
echo The BART model (~1.6GB) will download automatically on first run.
echo.
pause
