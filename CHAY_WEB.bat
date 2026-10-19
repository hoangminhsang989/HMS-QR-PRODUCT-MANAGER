@echo off
setlocal
title HMS QR Product Manager
set "HMS_QR_TEST_ROOT=F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST"
set "HMS_QR_DATABASE_URL=sqlite:///D:/HMS-QR-DATA/hms_qr_shared.sqlite"
set "HMS_QR_STORAGE_ROOT=D:\HMS-QR-DATA\storage"
set "PYTHONDONTWRITEBYTECODE=1"
set "DATA_ROOT=D:\HMS-QR-DATA"
set "CLOUDFLARED=C:\Program Files (x86)\cloudflared\cloudflared.exe"

if not exist "%DATA_ROOT%\storage" mkdir "%DATA_ROOT%\storage"

netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 (
  echo HMS QR is already running. Opening the application...
  start "" http://localhost:8000
  exit /b 0
)

REM Cross-origin origins are opt-in: drop them in cors-origins.txt, one per line
REM or comma-separated. Empty or absent means LAN-only, same-origin, as before.
if exist "%DATA_ROOT%\cors-origins.txt" (
  for /f "usebackq delims=" %%o in ("%DATA_ROOT%\cors-origins.txt") do set "HMS_QR_CORS_ORIGINS=%%o"
)

echo Starting HMS QR Product Manager...
if exist "%CLOUDFLARED%" (
  if exist "%DATA_ROOT%\cloudflared.log" del "%DATA_ROOT%\cloudflared.log"
  start "Cloudflare Tunnel" /b "%CLOUDFLARED%" tunnel --url http://localhost:8000 --logfile "%DATA_ROOT%\cloudflared.log"
  echo Dang mo Cloudflare Tunnel, vui long cho...
  python -m apps.server.tunnel_url "%DATA_ROOT%\cloudflared.log" "%DATA_ROOT%\tunnel-url.txt"
  if errorlevel 1 (
    echo Khong lay duoc URL tunnel. Xem %DATA_ROOT%\cloudflared.log
  ) else (
    echo.
    echo ============================================================
    echo  URL CONG KHAI: nhap dong ben duoi vao app mobile
    echo  ^(o MAY CHU -^> dan URL -^> LUU ^& KET NOI)
    echo ============================================================
    type "%DATA_ROOT%\tunnel-url.txt"
    echo ============================================================
    echo.
  )
)

start "" http://localhost:8000
python -m uvicorn apps.server.app:app --host 0.0.0.0 --port 8000
