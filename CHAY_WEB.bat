@echo off
setlocal EnableDelayedExpansion
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

REM The mobile app signs in, so the server needs a token-signing secret and an
REM administrator account. Both are generated once and kept on disk: a secret
REM that changed between restarts would invalidate every token already issued,
REM and a regenerated password would lock the operator out mid-shift.
if not exist "%DATA_ROOT%\auth-secret.txt" (
  python -c "import secrets,pathlib;pathlib.Path(r'%DATA_ROOT%\auth-secret.txt').write_bytes(secrets.token_urlsafe(48).encode())"
  if errorlevel 1 (
    echo Khong tao duoc khoa ky token. Xem %DATA_ROOT%
    pause
    exit /b 1
  )
)
set /p HMS_QR_AUTH_SECRET=<"%DATA_ROOT%\auth-secret.txt"
set "HMS_QR_AUTH_SECRET=%HMS_QR_AUTH_SECRET: =%"

if not exist "%DATA_ROOT%\admin-password.txt" (
  python -c "import secrets,pathlib;pathlib.Path(r'%DATA_ROOT%\admin-password.txt').write_bytes(secrets.token_urlsafe(16).encode())"
  if errorlevel 1 (
    echo Khong tao duoc mat khau quan tri. Xem %DATA_ROOT%
    pause
    exit /b 1
  )
  set "FIRST_RUN=1"
)
set /p ADMIN_PASSWORD=<"%DATA_ROOT%\admin-password.txt"
set "HMS_QR_BOOTSTRAP_ADMIN_USERNAME=admin"
set "HMS_QR_BOOTSTRAP_ADMIN_PASSWORD=%ADMIN_PASSWORD%"

REM Cross-origin origins are opt-in: drop them in cors-origins.txt, one per line
REM or comma-separated. Empty or absent means LAN-only, same-origin, as before.
REM Every line is kept: a plain "set" inside the loop would leave only the last
REM one, so adding a second frontend would silently lock the first out.
if exist "%DATA_ROOT%\cors-origins.txt" (
  set "HMS_QR_CORS_ORIGINS="
  for /f "usebackq delims=" %%o in ("%DATA_ROOT%\cors-origins.txt") do (
    if defined HMS_QR_CORS_ORIGINS (
      set "HMS_QR_CORS_ORIGINS=!HMS_QR_CORS_ORIGINS!,%%o"
    ) else (
      set "HMS_QR_CORS_ORIGINS=%%o"
    )
  )
)

if defined FIRST_RUN (
  echo.
  echo ============================================================
  echo  TAI KHOAN QUAN TRI - chi hien mot lan
  echo    ten dang nhap : admin
  echo    mat khau      : %ADMIN_PASSWORD%
  echo  Ghi lai. Muon doi thi xoa admin-password.txt roi chay lai
  echo  ^(xoa ca database neu muon dat lai toan bo^).
  echo ============================================================
  echo.
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
    echo  ^(o MAY CHU -^> dan URL -^> LUU ^& KET NOI^)
    echo ============================================================
    type "%DATA_ROOT%\tunnel-url.txt"
    echo ============================================================
    echo.
  )
)

start "" http://localhost:8000
python -m uvicorn apps.server.app:app --host 0.0.0.0 --port 8000
