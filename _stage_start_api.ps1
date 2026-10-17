# Start staging API (uvicorn) and verify readiness; secrets loaded from environment.ps1, never printed
$ErrorActionPreference = 'Stop'
Set-Location 'C:\HMS-QR-TEST'
. 'C:\HMS-QR-STAGING\environment.ps1'
$env:PYTHONPATH = 'C:\HMS-QR-TEST'
$python = 'C:\HMS-QR-TEST\venv\Scripts\python.exe'
$existing = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue
if (-not $existing) {
    Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'apps.server.app:app', '--host', '0.0.0.0', '--port', '8010') -WorkingDirectory 'C:\HMS-QR-TEST' -WindowStyle Hidden
    Start-Sleep -Seconds 10
}
$listen = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue
if (-not $listen) { throw 'API is not listening on 8010.' }
$r = Invoke-WebRequest -Uri 'http://127.0.0.1:8010/health/readiness/database' -TimeoutSec 30 -UseBasicParsing
"HTTP $($r.StatusCode): $($r.Content)"
