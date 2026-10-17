$ErrorActionPreference = 'Stop'
$root = 'C:\HMS-QR-STAGING'
$optionFile = Join-Path $root 'postgresql-installer-options.txt'
$installer = 'C:\exchange\postgresql-17.11-4-windows-x64.exe'
$worker = 'C:\exchange\_run_pg_installer.ps1'
if (Get-Service -Name 'postgresql-hmsqr-staging' -ErrorAction SilentlyContinue) { throw 'Staging service already exists.' }
if (Test-Path 'C:\Program Files\PostgreSQL\17-HMSQR-Staging\bin\psql.exe') { throw 'Staging PostgreSQL binaries already exist.' }
New-Item -ItemType Directory -Force -Path $root,(Join-Path $root 'postgresql'),(Join-Path $root 'storage'),(Join-Path $root 'logs'),(Join-Path $root 'backups'),'C:\HMS-QR-TEST-DATA' | Out-Null
$adminPassword = [guid]::NewGuid().ToString('N') + 'A9!'
$dbPassword = [guid]::NewGuid().ToString('N') + 'B7!'
$optionLines = @('mode=unattended','unattendedmodeui=minimal','prefix=C:\Program Files\PostgreSQL\17-HMSQR-Staging','datadir=C:\HMS-QR-STAGING\postgresql','serverport=55432','servicename=postgresql-hmsqr-staging',('superpassword=' + $dbPassword),'')
[IO.File]::WriteAllLines($optionFile, [string[]]$optionLines, [Text.Encoding]::ASCII)
$randomBytes = New-Object byte[] 48
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($randomBytes)
$rng.Dispose()
$authSecret = [Convert]::ToBase64String($randomBytes)
$dbUrl = "postgresql+psycopg://hmsqr_staging:$adminPassword@127.0.0.1:55432/hmsqr_staging"
$storage = 'C:\HMS-QR-STAGING\storage'
$testRoot = 'C:\HMS-QR-TEST-DATA'
$envLines = @("`$env:HMS_QR_ENV = 'staging'", "`$env:HMS_QR_DATABASE_URL = '$dbUrl'", "`$env:HMS_QR_STORAGE_ROOT = '$storage'", "`$env:HMS_QR_AUTH_SECRET = '$authSecret'", "`$env:HMS_QR_BOOTSTRAP_ADMIN_USERNAME = 'admin'", "`$env:HMS_QR_BOOTSTRAP_ADMIN_PASSWORD = '$adminPassword'", "`$env:HMS_QR_TEST_ROOT = '$testRoot'")
Set-Content -LiteralPath (Join-Path $root 'environment.ps1') -Value $envLines -Encoding ascii
Set-Content -LiteralPath (Join-Path $root 'stage-admin.txt') -Value "username=admin`r`npassword=$adminPassword" -Encoding ascii
$stdout = Join-Path $root 'postgresql-installer.stdout.log'
$stderr = Join-Path $root 'postgresql-installer.stderr.log'
$status = Join-Path $root 'postgresql-installer.exit'
Remove-Item $status -Force -ErrorAction SilentlyContinue
$argumentLine = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Installer "{1}" -OptionFile "{2}" -StatusFile "{3}"' -f $worker,$installer,$optionFile,$status
$process = Start-Process -FilePath "$PSHOME\powershell.exe" -ArgumentList $argumentLine -WorkingDirectory $root -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
Set-Content -LiteralPath (Join-Path $root 'postgresql-installer.pid') -Value $process.Id -Encoding ascii
Write-Output "Installer worker started with PID $($process.Id); poll C:\HMS-QR-STAGING\postgresql-installer.exit."
