@echo off
chcp 65001 >nul
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\create-hms-qr-shortcuts.ps1"
if errorlevel 1 (
  echo Không thể tạo shortcut trên Desktop.
  pause
  exit /b 1
)
pause
