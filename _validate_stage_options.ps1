$dbPassword = 'DummyForFormatTest42!'
$lines = @(
    'mode=unattended',
    'unattendedmodeui=minimal',
    'prefix=C:\Program Files\PostgreSQL\17-HMSQR-Staging',
    'datadir=C:\HMS-QR-STAGING\postgresql',
    'serverport=55432',
    'servicename=postgresql-hmsqr-staging',
    ('superpassword=' + $dbPassword),
    ''
)
$output = Join-Path $env:TEMP 'stage-options-format-test.txt'
[IO.File]::WriteAllLines($output, [string[]]$lines, [Text.Encoding]::ASCII)
$roundTrip = [IO.File]::ReadAllLines($output)
if ($roundTrip[6] -ne 'superpassword=' + $dbPassword) { throw 'superpassword option was not serialized as one line' }
if ($roundTrip.Count -ne 8) { throw "Expected eight option lines, received $($roundTrip.Count)" }
Write-Output 'PASS: superpassword is one option line; eight lines total.'
Remove-Item -LiteralPath $output -Force
