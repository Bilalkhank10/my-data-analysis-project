@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Fiverr Gig Growth System - Windows Setup
echo ==========================================

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY_CMD=py -3"
) else (
  where python >nul 2>nul
  if not %errorlevel%==0 (
    echo ERROR: Python was not found.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/
    echo During setup, enable "Add Python to PATH".
    pause
    exit /b 1
  )
  set "PY_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY_CMD% -m venv .venv
  if errorlevel 1 goto :fail
)

echo Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo Installing project dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo Created .env from .env.example.
  echo Add a NEW rotated OpenRouter key there only when you need real Phase 3/4 runs.
)

echo Running diagnostics...
".venv\Scripts\python.exe" doctor.py
if errorlevel 1 goto :fail

echo.
echo Setup complete.
echo Run run.bat, then open http://127.0.0.1:8000
pause
exit /b 0

:fail
echo.
echo Setup failed. Read the error above and run this file again.
pause
exit /b 1
