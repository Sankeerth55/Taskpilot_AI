@echo off
echo ============================================
echo TaskPilot AI - Mirrored Browser Setup
echo ============================================
echo.
echo This installs Playwright for VISIBLE browser automation
echo You will SEE voice commands executing in real-time!
echo.

echo [1/4] Installing Python dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install requirements
    exit /b 1
)

echo.
echo [2/4] Installing Playwright browsers (VISIBLE mode)...
playwright install chromium
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install Chromium
)

playwright install msedge
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Edge installation failed (may need manual installation)
)

playwright install firefox
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Firefox installation failed (optional)
)

echo.
echo [3/4] Installing Playwright system dependencies...
playwright install-deps
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: System deps installation failed (may need manual installation)
)

echo.
echo [4/4] Testing Playwright installation...
python -c "from playwright.sync_api import sync_playwright; print('✅ Playwright ready!')"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Playwright test failed
    exit /b 1
)

echo.
echo ============================================
echo ✅ Setup Complete!
echo ============================================
echo.
echo MIRRORED BROWSER MODE:
echo   • Launches VISIBLE browser window
echo   • Mirrors your shared tab URL
echo   • You SEE actions happening in real-time!
echo   • Screenshot proof for every action
echo   • NO EXTENSIONS NEEDED!
echo.
echo Next steps:
echo   1. Start backend: python -m uvicorn app.main:app --reload
echo   2. Test mirrored browser: python test_playwright_integration.py
echo   3. Watch browser window appear and execute actions!
echo.
echo Backend runs on: http://localhost:8000
echo WebSocket endpoint: ws://localhost:8000/api/ws/actions
echo.
echo Supported browsers:
echo   - Chrome (you'll see window appear!)
echo   - Microsoft Edge (visible window!)
echo   - Firefox (visible window!)
echo.
echo Usage in frontend:
echo   await playwrightService.connect();
echo   await playwrightService.startBrowser('chrome');
echo   actionExecutor.setExecutionMode('playwright');
echo   // Watch voice commands execute in visible browser! 🎬
echo.
pause
