@echo off
REM Run an audit from the command line.  Usage:  audit.bat v1   (or v2)
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" ( echo Run setup.bat first. & pause & exit /b 1 )
set VER=%1
if "%VER%"=="" set VER=v1
".venv\Scripts\python.exe" -m app.cli audit --version %VER%
echo.
pause
endlocal
