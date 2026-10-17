$ErrorActionPreference = 'Stop'
$root = 'C:\HMS-QR-STAGING'
$testRoot = 'C:\HMS-QR-TEST-DATA'
$pgPrefix = 'C:\Program Files\PostgreSQL\17-HMSQR-Staging'
$pgData = Join-Path $root 'postgresql'
$pgService = 'postgresql-hmsqr-staging'
$installer = 'C:\exchange\postgresql-17.11-4-windows-x64.exe'
$expectedHash = 'C9828FD3A4DAEBBEEACE19BEC2DE5F38D73C047FCE47278148B525CFBE28A5E4'
$actualHash = (Get-FileHash -Algorithm SHA256 $installer).Hash
if ($actualHash -ne $expectedHash) { throw 'PostgreSQL installer checksum mismatch.' }
if (Get-Service -Name $pgService -ErrorAction SilentlyContinue) { throw 'Staging PostgreSQL service already exists; refusing to overwrite.' }
New-Item -ItemType Directory -Force -Path $root,$testRoot,$pgData,(Join-Path $root 'storage'),(Join-Path $root 'logs'),(Join-Path $root 'backups') | Out-Null
$adminPassword = [guid]::NewGuid().ToString('N') + 'A9!'
$dbPassword = [guid]::NewGuid().ToString('N') + 'B7!'
$optionFile = Join-Path $root 'postgresql-installer-options.txt'
@('mode=unattended','unattendedmodeui=minimal',"prefix=$pgPrefix","datadir=$pgData",'serverport=55432',"servicename=$pgService",'superpassword=' + $dbPassword,'') | Set-Content -LiteralPath $optionFile -Encoding ascii
try {
    $process = Start-Process -FilePath $installer -ArgumentList @('--optionfile', $optionFile, '--enable_acledit', '1') -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "PostgreSQL installer exited with $($process.ExitCode)." }
} finally { Remove-Item -LiteralPath $optionFile -Force -ErrorAction SilentlyContinue }
Set-Service -Name $pgService -StartupType Automatic
Start-Service -Name $pgService
$pgBin = Join-Path $pgPrefix 'bin'
$env:PGPASSWORD = $dbPassword
$create = & (Join-Path $pgBin 'psql.exe') -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -c "CREATE ROLE hmsqr_staging LOGIN PASSWORD '$adminPassword'"
if ($LASTEXITCODE -ne 0) { throw 'Failed to create isolated staging database role.' }
$createDb = & (Join-Path $pgBin 'psql.exe') -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -c 'CREATE DATABASE hmsqr_staging OWNER hmsqr_staging'
if ($LASTEXITCODE -ne 0) { throw 'Failed to create isolated staging database.' }
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
$authSecret = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
$env:HMS_QR_ENV = 'staging'
$env:HMS_QR_DATABASE_URL = "postgresql+psycopg://hmsqr_staging:$adminPassword@127.0.0.1:55432/hmsqr_staging"
$env:HMS_QR_STORAGE_ROOT = Join-Path $root 'storage'
$env:HMS_QR_AUTH_SECRET = $authSecret
$env:HMS_QR_BOOTSTRAP_ADMIN_USERNAME = 'admin'
$env:HMS_QR_BOOTSTRAP_ADMIN_PASSWORD = $adminPassword
$env:HMS_QR_TEST_ROOT = $testRoot
Set-Content -LiteralPath (Join-Path $root 'environment.ps1') -Encoding ascii -Value @(
    "$env:HMS_QR_ENV='staging'",
    "$env:HMS_QR_DATABASE_URL='$($env:HMS_QR_DATABASE_URL)'",
    "$env:HMS_QR_STORAGE_ROOT='$($env:HMS_QR_STORAGE_ROOT)'",
    "$env:HMS_QR_AUTH_SECRET='$authSecret'",
    "$env:HMS_QR_BOOTSTRAP_ADMIN_USERNAME='admin'",
    "$env:HMS_QR_BOOTSTRAP_ADMIN_PASSWORD='$adminPassword'",
    "$env:HMS_QR_TEST_ROOT='$testRoot'"
)
Set-Content -LiteralPath (Join-Path $root 'stage-admin.txt') -Encoding ascii -Value "username=admin`r`npassword=$adminPassword"
Write-Output 'PostgreSQL staging service created on port 55432; credentials stored under staging root.'
