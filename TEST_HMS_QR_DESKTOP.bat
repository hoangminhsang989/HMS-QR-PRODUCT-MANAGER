@echo off
chcp 65001 >nul
setlocal
title HMS QR Desktop Test
cd /d "%~dp0"
set "HMS_QR_SERVER_URL=http://127.0.0.1:8010"
set "HMS_QR_USERNAME=test-admin"
set "HMS_QR_PASSWORD=test-password-123"
set "PYTHONDONTWRITEBYTECODE=1"

echo Đang mở HMS QR Desktop với %HMS_QR_SERVER_URL%...
py -3.14 -m apps.desktop
if errorlevel 1 pause
