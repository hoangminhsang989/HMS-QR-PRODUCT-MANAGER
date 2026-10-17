@echo off
setlocal
title HMS QR Server Tool
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0"

if /I not "%~1"=="elevated" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ComSpec%' -ArgumentList '/c ""%~f0" elevated"' -Verb RunAs"
  if errorlevel 1 (
    echo Khong the mo HMS QR Server Tool voi quyen Administrator.
    pause
  )
  exit /b
)

py -3.14 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.14 x64 chua duoc cai dat.
  pause
  exit /b 1
)
py -3.14 -m apps.server.tool
if errorlevel 1 pause
exit /b %errorlevel%
