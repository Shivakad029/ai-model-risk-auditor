@echo off
REM Run the test suite.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" ( echo Run setup.bat first. & pause & exit /b 1 )
".venv\Scripts\python.exe" -m pytest tests/ -q
echo.
pause
endlocal
