$ErrorActionPreference = 'Stop'
$venv = 'C:\HMS-QR-STAGING\venv'
& "$venv\Scripts\python.exe" -c 'import fastapi, sqlalchemy, psycopg, alembic, numpy, cv2; print(1)'
if ($LASTEXITCODE -ne 0) { throw "Python import validation failed: $LASTEXITCODE" }
. 'C:\HMS-QR-STAGING\environment.ps1'
$env:PYTHONPATH = 'C:\exchange\QR'
$env:HMS_QR_ENV = 'staging'
Push-Location 'C:\exchange\QR'
try {
    & "$venv\Scripts\alembic.exe" heads
    if ($LASTEXITCODE -ne 0) { throw "Alembic heads failed: $LASTEXITCODE" }
    & "$venv\Scripts\alembic.exe" current
    if ($LASTEXITCODE -ne 0) { throw "Alembic current failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}
