@echo off
chcp 65001 >nul
setlocal
title Kiểm tra HMS QR Machine 2
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0"

py -3.14 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.14 x64 chưa được cài đặt.
  pause
  exit /b 1
)
py -3.14 -m apps.desktop.lan_diagnostic
set "RESULT=%errorlevel%"
echo.
if "%RESULT%"=="0" (
  echo Kiểm tra hoàn tất. Nhấn phím bất kỳ để đóng cửa sổ.
) else (
  echo Kiểm tra không đạt. Nhấn phím bất kỳ để đóng cửa sổ.
)
pause >nul
exit /b %RESULT%
