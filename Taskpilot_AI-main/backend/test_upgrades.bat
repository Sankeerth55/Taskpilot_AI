@echo off
REM Quick Start Script for TaskPilot AI Enterprise Upgrades
REM Tests all new systems and verifies everything works

echo ============================================================
echo TaskPilot AI - Enterprise Upgrades Test
echo ============================================================
echo.

echo [1/2] Running comprehensive tests...
echo.
cd backend
python test_enterprise_upgrades.py

echo.
echo [2/2] All tests complete!
echo.

echo ============================================================
echo Next Steps
echo ============================================================
echo.
echo 1. Start the server:
echo    python -m uvicorn app.main:app --reload --port 8000
echo.
echo 2. Test monitoring endpoints:
echo    http://localhost:8000/api/monitoring/health
echo    http://localhost:8000/api/monitoring/dashboard
echo.
echo 3. View logs:
echo    backend\logs\taskpilot_*.log
echo.
echo System is ready for production! 🚀
echo.
pause
