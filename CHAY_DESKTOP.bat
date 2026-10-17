@echo off
setlocal
title HMS QR Desktop LAN
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0"

echo HMS QR Desktop LAN
echo Server is found automatically on the Private LAN.
echo Enter a Server URL only when discovery cannot find Machine 1.
echo.
py -3.14 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.14 x64 chua duoc cai dat. Cai Python 3.14 truoc khi mo Desktop.
  pause
  exit /b 1
)
py -3.14 -m apps.desktop
if errorlevel 1 (
  echo.
  echo Desktop did not start. Check Python 3.14, the LAN connection, and Machine 1.
  pause
)
exit /b %errorlevel%
