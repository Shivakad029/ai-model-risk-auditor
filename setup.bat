@echo off
REM One-time setup: create the virtual environment and install dependencies.
setlocal
cd /d "%~dp0"
echo ============================================================
echo  AI Model Risk Auditor - Windows setup
echo ============================================================
echo.
echo Creating virtual environment (.venv) ...
python -m venv .venv
if errorlevel 1 (
  echo.
  echo ERROR: could not create the virtual environment.
  echo Make sure Python 3.11 or 3.12 is installed and on your PATH
  echo ^(try: python --version^).
  pause
  exit /b 1
)
echo Upgrading pip ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
echo Installing dependencies from requirements.txt ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERROR: dependency install failed. See the messages above.
  pause
  exit /b 1
)
echo.
echo Setup complete.  Next:
echo    test.bat    - run the 14 tests
echo    run.bat     - start the dashboard at http://localhost:8000
echo    audit.bat   - run an audit from the command line
echo.
pause
endlocal
