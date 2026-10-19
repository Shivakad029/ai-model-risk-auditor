@echo off
REM Start the dashboard + API on http://localhost:8000  (Ctrl+C to stop)
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" ( echo Run setup.bat first. & pause & exit /b 1 )
echo Starting Auditor dashboard at http://localhost:8000  (Ctrl+C to stop) ...
".venv\Scripts\python.exe" run_server.py
endlocal
