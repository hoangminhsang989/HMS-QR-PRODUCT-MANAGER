# Wipe partial PostgreSQL staging install, then re-run fixed bootstrap (secrets stay in guest)
$ErrorActionPreference = 'Stop'
$root = 'C:\HMS-QR-STAGING'
$pgPrefix = 'C:\Program Files\PostgreSQL\17-HMSQR-Staging'
$pgData = Join-Path $root 'postgresql'
$pgService = 'postgresql-hmsqr-staging'

$svc = Get-Service -Name $pgService -ErrorAction SilentlyContinue
if ($svc) {
    Stop-Service -Name $pgService -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    & sc.exe delete $pgService | Out-Null
    Start-Sleep -Seconds 2
}
if (Test-Path $pgPrefix) { Remove-Item $pgPrefix -Recurse -Force }
if (Test-Path $pgData) { Remove-Item $pgData -Recurse -Force }
'WIPE_OK'
