@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" start.py
) else (
  echo Virtual environment not found. Running setup first...
  call setup_windows.bat
  if errorlevel 1 exit /b 1
  ".venv\Scripts\python.exe" start.py
)

pause
