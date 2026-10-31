@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title HMS QR Product Manager
cd /d "%~dp0"
set "HMS_QR_TEST_ROOT=D:\HMS-QR-CHECK"
set "HMS_QR_DATABASE_URL=sqlite:///D:/HMS-QR-DATA/hms_qr_shared.sqlite"
set "HMS_QR_STORAGE_ROOT=D:\HMS-QR-DATA\storage"
set "PYTHONDONTWRITEBYTECODE=1"
set "DATA_ROOT=D:\HMS-QR-DATA"
set "CLOUDFLARED=C:\Program Files (x86)\cloudflared\cloudflared.exe"

if not exist "%DATA_ROOT%\storage" mkdir "%DATA_ROOT%\storage"

netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 (
  echo HMS QR đang chạy. Đang mở ứng dụng...
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
    echo Không tạo được khóa ký token. Xem %DATA_ROOT%
    pause
    exit /b 1
  )
)
set /p HMS_QR_AUTH_SECRET=<"%DATA_ROOT%\auth-secret.txt"
set "HMS_QR_AUTH_SECRET=%HMS_QR_AUTH_SECRET: =%"

if not exist "%DATA_ROOT%\admin-password.txt" (
  python -c "import secrets,pathlib;pathlib.Path(r'%DATA_ROOT%\admin-password.txt').write_bytes(secrets.token_urlsafe(16).encode())"
  if errorlevel 1 (
    echo Không tạo được mật khẩu quản trị. Xem %DATA_ROOT%
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
  echo  TÀI KHOẢN QUẢN TRỊ - chỉ hiện một lần
  echo    tên đăng nhập : admin
  echo    mật khẩu      : %ADMIN_PASSWORD%
  echo  Ghi lại. Muốn đổi thì xóa admin-password.txt rồi chạy lại
  echo  ^(xóa cả database nếu muốn đặt lại toàn bộ^).
  echo ============================================================
  echo.
)

echo Đang khởi động HMS QR Product Manager...
if exist "%CLOUDFLARED%" (
  if exist "%DATA_ROOT%\cloudflared.log" del "%DATA_ROOT%\cloudflared.log"
  start "Cloudflare Tunnel" /b "%CLOUDFLARED%" tunnel --url http://localhost:8000 --logfile "%DATA_ROOT%\cloudflared.log"
  echo Đang mở Cloudflare Tunnel, vui lòng chờ...
  python -m apps.server.tunnel_url "%DATA_ROOT%\cloudflared.log" "%DATA_ROOT%\tunnel-url.txt"
  if errorlevel 1 (
    echo Không lấy được URL tunnel. Xem %DATA_ROOT%\cloudflared.log
  ) else (
    echo.
    echo ============================================================
    echo  URL CÔNG KHAI: nhập dòng bên dưới vào app mobile
    echo  ^(o MÁY CHỦ -^> dán URL -^> LƯU ^& KẾT NỐI^)
    echo ============================================================
    type "%DATA_ROOT%\tunnel-url.txt"
    echo ============================================================
    echo.
  )
)

start "" http://localhost:8000
python -m uvicorn apps.server.app:app --host 0.0.0.0 --port 8000
