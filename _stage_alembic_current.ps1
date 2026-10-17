$ErrorActionPreference = 'Stop'
$root = 'C:\HMS-QR-STAGING'
$status = Join-Path $root 'alembic-current.status'
$stdout = Join-Path $root 'alembic-current.stdout.log'
$stderr = Join-Path $root 'alembic-current.stderr.log'
Remove-Item $status,$stdout,$stderr -Force -ErrorAction SilentlyContinue
$script = "Set-Location C:\exchange\QR; . C:\HMS-QR-STAGING\environment.ps1; `$env:HMS_QR_ENV='staging'; `$env:PYTHONPATH='C:\exchange\QR'; & C:\HMS-QR-STAGING\venv\Scripts\alembic.exe current *> '$stdout'; `$code=`$LASTEXITCODE; Set-Content -LiteralPath '$status' -Value `$code -Encoding ascii"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
$p = Start-Process -FilePath "$PSHOME\powershell.exe" -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',$encoded) -WindowStyle Hidden -PassThru
Set-Content -LiteralPath (Join-Path $root 'alembic-current.pid') -Value $p.Id -Encoding ascii
Write-Output "Started read-only Alembic current check, PID $($p.Id)."
