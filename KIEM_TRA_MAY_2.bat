@echo off
setlocal
title Kiem tra HMS QR Machine 2
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0"

py -3.14 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.14 x64 chua duoc cai dat.
  pause
  exit /b 1
)
py -3.14 -m apps.desktop.lan_diagnostic
set "RESULT=%errorlevel%"
echo.
if "%RESULT%"=="0" (
  echo Kiem tra hoan tat. Nhan phim bat ky de dong cua so.
) else (
  echo Kiem tra khong dat. Nhan phim bat ky de dong cua so.
)
pause >nul
exit /b %RESULT%
