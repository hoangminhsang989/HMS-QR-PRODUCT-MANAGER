@echo off
setlocal
title HMS QR Product Manager
set "HMS_QR_TEST_ROOT=F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST"
set "HMS_QR_DATABASE_URL=sqlite:///D:/HMS-QR-DATA/hms_qr_shared.sqlite"
set "HMS_QR_STORAGE_ROOT=D:\HMS-QR-DATA\storage"
set "PYTHONDONTWRITEBYTECODE=1"

if not exist "D:\HMS-QR-DATA\storage" mkdir "D:\HMS-QR-DATA\storage"

netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 (
  echo HMS QR is already running. Opening the application...
  start "" http://localhost:8000
  exit /b 0
)

echo Starting HMS QR Product Manager...
if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" (
  start "Cloudflare Tunnel" /b "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8000
)

start "" http://localhost:8000
python -m uvicorn apps.server.app:app --host 0.0.0.0 --port 8000
