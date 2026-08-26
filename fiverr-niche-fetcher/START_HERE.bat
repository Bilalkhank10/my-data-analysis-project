@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Fiverr Gig Growth System
color 0A

echo.
echo  ============================================================
echo                FIVERR GIG GROWTH SYSTEM
echo                  One-click local launcher
echo  ============================================================
echo.

REM Find Python. The launcher never displays or copies API-key values.
where py >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=py -3"
  goto :python_ready
)
where python >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=python"
  goto :python_ready
)

where winget >nul 2>nul
if errorlevel 1 goto :python_help
choice /C YN /M "Python is missing. Install Python 3.12 automatically with winget"
if errorlevel 2 goto :python_help
winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :python_help
echo Python was installed. Close this window, then double-click START_HERE.bat again.
pause
exit /b 0

:python_ready
if not exist ".venv\Scripts\python.exe" (
  echo [1/5] Creating isolated Python environment...
  %PY_CMD% -m venv .venv
  if errorlevel 1 goto :failed
) else (
  echo [1/5] Virtual environment ready.
)

echo [2/5] Checking project requirements...
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 'requirements.txt').Hash"`) do set "REQ_HASH=%%H"
set "OLD_HASH="
if exist ".venv\requirements.sha256" set /p OLD_HASH=<".venv\requirements.sha256"

if /I not "%REQ_HASH%"=="%OLD_HASH%" (
  echo       Installing/updating dependencies. This can take a minute on first run...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 goto :failed
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :failed
  >".venv\requirements.sha256" echo %REQ_HASH%
) else (
  echo       Dependencies already installed.
)

if not exist ".env" (
  echo [3/5] Creating private local configuration...
  copy /Y ".env.example" ".env" >nul
) else (
  echo [3/5] Private local configuration found.
)

echo [4/5] Running system diagnostics...
".venv\Scripts\python.exe" doctor.py
if errorlevel 1 goto :failed

echo [5/5] Starting the application...
echo.
echo The browser will open automatically.
echo Keep this window open while using the system.
echo Press Ctrl+C to stop the server.
echo.

set "AUTO_OPEN_BROWSER=true"
".venv\Scripts\python.exe" start.py
exit /b %errorlevel%

:python_help
echo.
echo Download Python from: https://www.python.org/downloads/windows/
echo During installation enable: Add Python to PATH
echo Then double-click START_HERE.bat again.
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1

:failed
echo.
echo [ERROR] Automatic setup did not complete.
echo Review the message above or read LOCAL_SETUP_GUIDE.md.
pause
exit /b 1
