@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" src\server.py
  goto end
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 src\server.py
  goto end
)
where python >nul 2>&1
if not errorlevel 1 (
  python src\server.py
  goto end
)
echo Install Python 3.11 or later, then run this file again.
:end
pause
