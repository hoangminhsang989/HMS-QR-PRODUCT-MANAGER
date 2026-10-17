# PostgreSQL staging bootstrap for linked clone (secrets never leave guest)
$ErrorActionPreference = 'Stop'
$root = 'C:\HMS-QR-STAGING'
$testRoot = 'C:\HMS-QR-TEST-DATA'
$pgPrefix = 'C:\Program Files\PostgreSQL\17-HMSQR-Staging'
$pgData = Join-Path $root 'postgresql'
$pgService = 'postgresql-hmsqr-staging'
$installer = 'C:\exchange\postgresql-17.11-4-windows-x64.exe'
$expectedHash = 'C9828FD3A4DAEBBEEACE19BEC2DE5F38D73C047FCE47278148B525CFBE28A5E4'

$actualHash = (Get-FileHash -Algorithm SHA256 $installer).Hash
if ($actualHash -ne $expectedHash) { throw "Installer checksum mismatch: $actualHash" }
if (Get-Service -Name $pgService -ErrorAction SilentlyContinue) { throw 'Staging service already exists; refusing to overwrite.' }
if (Test-Path (Join-Path $pgPrefix 'bin\psql.exe')) { throw 'Staging PostgreSQL binaries already exist.' }

New-Item -ItemType Directory -Force -Path $root,$testRoot,$pgData,(Join-Path $root 'storage'),(Join-Path $root 'logs'),(Join-Path $root 'backups') | Out-Null

$adminPassword = [guid]::NewGuid().ToString('N') + 'A9!'
$dbPassword = [guid]::NewGuid().ToString('N') + 'B7!'

$optionFile = Join-Path $root 'postgresql-installer-options.txt'
@('mode=unattended','unattendedmodeui=minimal',"prefix=$pgPrefix","datadir=$pgData",'serverport=55432',"servicename=$pgService",('superpassword=' + $dbPassword),'') | Set-Content -LiteralPath $optionFile -Encoding ascii
try {
    $process = Start-Process -FilePath $installer -ArgumentList @('--optionfile', $optionFile, '--enable_acledit', '1') -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "PostgreSQL installer exited with $($process.ExitCode)." }
} finally {
    Remove-Item -LiteralPath $optionFile -Force -ErrorAction SilentlyContinue
}

Set-Service -Name $pgService -StartupType Automatic
Start-Service -Name $pgService

$pgBin = Join-Path $pgPrefix 'bin'
$env:PGPASSWORD = $dbPassword

$sqlFile = Join-Path $root 'bootstrap-role.sql'
@("CREATE ROLE hmsqr_staging LOGIN PASSWORD '$adminPassword';", 'CREATE DATABASE hmsqr_staging OWNER hmsqr_staging;') | Set-Content -LiteralPath $sqlFile -Encoding ascii
try {
    & (Join-Path $pgBin 'psql.exe') -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -f $sqlFile
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create isolated staging database role.' }
} finally {
    Remove-Item -LiteralPath $sqlFile -Force -ErrorAction SilentlyContinue
}
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue

$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$randomBytes = New-Object byte[] 48
$rng.GetBytes($randomBytes)
$rng.Dispose()
$authSecret = [Convert]::ToBase64String($randomBytes)
$dbUrl = "postgresql+psycopg://hmsqr_staging:$adminPassword@127.0.0.1:55432/hmsqr_staging"
$envLines = @(
    '$env:HMS_QR_ENV = ''staging''',
    "`$env:HMS_QR_DATABASE_URL = 'postgresql+psycopg://hmsqr_staging:$adminPassword@127.0.0.1:55432/hmsqr_staging'",
    "`$env:HMS_QR_AUTH_SECRET = '$authSecret'",
    "`$env:HMS_QR_BOOTSTRAP_ADMIN_USERNAME = 'admin'",
    "`$env:HMS_QR_BOOTSTRAP_ADMIN_PASSWORD = '$adminPassword'",
    "`$env:HMS_QR_TEST_ROOT = '$testRoot'"
)
Set-Content -LiteralPath (Join-Path $root 'environment.ps1') -Value $envLines -Encoding ascii
Set-Content -LiteralPath (Join-Path $root 'stage-admin.txt') -Value "username=admin`r`npassword=$adminPassword" -Encoding ascii

$envCheck = & powershell.exe -NoProfile -Command ". 'C:\HMS-QR-STAGING\environment.ps1'; if (`$env:HMS_QR_ENV -eq 'staging' -and `$env:HMS_QR_DATABASE_URL -like 'postgresql+psycopg://*' -and `$env:HMS_QR_AUTH_SECRET.Length -ge 32 -and `$env:HMS_QR_BOOTSTRAP_ADMIN_USERNAME -eq 'admin' -and `$env:HMS_QR_BOOTSTRAP_ADMIN_PASSWORD.Length -ge 8) { 'ENV_OK' } else { 'ENV_BAD' }"
if ($envCheck -notmatch 'ENV_OK') { throw "environment.ps1 self-check failed: $envCheck" }

$listen = Test-NetConnection -ComputerName 127.0.0.1 -Port 55432 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $listen) { throw 'PostgreSQL staging not listening on 55432.' }
'BOOTSTRAP_OK'
