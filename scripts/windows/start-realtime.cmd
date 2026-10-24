@echo off
cd /d "%~dp0..\.."
".venv\Scripts\python.exe" -m sorting_vision.realtime --env-file .env --config config/realtime.windows.local.yaml
if errorlevel 1 pause
