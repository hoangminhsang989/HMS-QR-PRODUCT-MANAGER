@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\create-hms-qr-shortcuts.ps1"
if errorlevel 1 (
  echo Khong the tao shortcut tren Desktop.
  pause
  exit /b 1
)
pause
