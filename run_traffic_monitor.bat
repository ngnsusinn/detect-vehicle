@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" traffic_monitor.py %*
) else (
    python traffic_monitor.py %*
)
if errorlevel 1 pause
