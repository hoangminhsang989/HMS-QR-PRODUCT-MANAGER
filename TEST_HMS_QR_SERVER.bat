@echo off
setlocal
title HMS QR Test Server
set "HMS_QR_ENV=dev"
set "HMS_QR_DATABASE_URL=sqlite:///F:/HMS-QR-TEST-RUNTIME/hms_qr_test.sqlite"
set "HMS_QR_STORAGE_ROOT=F:\HMS-QR-TEST-RUNTIME\storage"
set "HMS_QR_AUTH_SECRET=hms-qr-test-only-signing-secret-2026"
set "HMS_QR_BOOTSTRAP_ADMIN_USERNAME=test-admin"
set "HMS_QR_BOOTSTRAP_ADMIN_PASSWORD=test-password-123"
set "HMS_QR_ALLOW_EMPTY_PASSWORDS=false"
set "PYTHONDONTWRITEBYTECODE=1"

if not exist "F:\HMS-QR-TEST-RUNTIME" mkdir "F:\HMS-QR-TEST-RUNTIME"
if not exist "F:\HMS-QR-TEST-RUNTIME\storage" mkdir "F:\HMS-QR-TEST-RUNTIME\storage"

netstat -ano | findstr /R /C:":8010 .*LISTENING" >nul
if not errorlevel 1 (
  echo HMS QR test server is already listening at http://127.0.0.1:8010
  goto tool
)

REM The engine cutover removed Alembic from the runtime path: there is no
REM alembic.ini and migrations/versions is empty, so the old upgrade command
REM fails outright. The DEV server applies the shipped engine migrations itself
REM through Stage2Repository.create_schema(), so this step only has to make sure
REM the database directory exists and the schema is current before the
REM administrator is bootstrapped.
echo Applying test database migrations...
py -3.14 -c "from config.environments import load_config; from packages.persistence.database import create_database_runtime; from packages.persistence.sqlalchemy_repository import Stage2Repository; runtime=create_database_runtime(load_config()); Stage2Repository(runtime).create_schema(); runtime.dispose()"
if errorlevel 1 (
  echo Migration failed. The test server was not started.
  pause
  exit /b 1
)

py -3.14 -c "from config.environments import load_config; from packages.application.server_auth import ServerAuthService; from packages.persistence.database import create_database_runtime; runtime=create_database_runtime(load_config()); ServerAuthService(runtime).bootstrap_admin(); runtime.dispose()"
if errorlevel 1 (
  echo Test administrator bootstrap failed. The test server was not started.
  pause
  exit /b 1
)

echo Opening HMS QR Server Tool...
:tool
py -3.14 -m apps.server.tool
