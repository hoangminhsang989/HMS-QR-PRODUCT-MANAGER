# Run Alembic migrations against the staging DB (secrets loaded from environment.ps1, never printed)
$ErrorActionPreference = 'Stop'
Set-Location 'C:\HMS-QR-TEST'
. 'C:\HMS-QR-STAGING\environment.ps1'
$env:PYTHONPATH = 'C:\HMS-QR-TEST'
$python = 'C:\HMS-QR-TEST\venv\Scripts\python.exe'
& $python -m alembic current
if ($LASTEXITCODE -ne 0) { throw "alembic current failed: $LASTEXITCODE" }
& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "alembic upgrade head failed: $LASTEXITCODE" }
'ALEMBIC_OK'
