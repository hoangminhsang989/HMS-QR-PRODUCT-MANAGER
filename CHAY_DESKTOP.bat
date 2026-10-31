@echo off
chcp 65001 >nul
setlocal
title HMS QR Desktop LAN
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0"

echo HMS QR Desktop LAN
echo Server được tự tìm trên mạng Private LAN.
echo Chỉ nhập URL Server khi không tìm được Máy 1.
echo.
py -3.14 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.14 x64 chưa được cài đặt. Cài Python 3.14 trước khi mở Desktop.
  pause
  exit /b 1
)
py -3.14 -m apps.desktop
if errorlevel 1 (
  echo.
  echo Desktop không khởi động được. Kiểm tra Python 3.14, kết nối LAN và Máy 1.
  pause
)
exit /b %errorlevel%
