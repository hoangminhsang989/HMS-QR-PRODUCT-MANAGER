$ErrorActionPreference = 'Stop'
$root = 'C:\HMS-QR-STAGING'
$venv = Join-Path $root 'venv'
$status = Join-Path $root 'pip-install.status'
$stdout = Join-Path $root 'pip-install.stdout.log'
$stderr = Join-Path $root 'pip-install.stderr.log'
Remove-Item $status,$stdout,$stderr -Force -ErrorAction SilentlyContinue
if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) {
    & py -3.14 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed with exit code $LASTEXITCODE" }
}
$script = "& '$venv\Scripts\python.exe' -m pip install --no-index --find-links C:\exchange\QR\installer\wheels -r C:\exchange\QR\requirements.txt *> '$stdout'; `$code = `$LASTEXITCODE; Set-Content -LiteralPath '$status' -Value `$code -Encoding ascii"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
$p = Start-Process -FilePath "$PSHOME\powershell.exe" -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',$encoded) -WindowStyle Hidden -PassThru
Set-Content -LiteralPath (Join-Path $root 'pip-install.pid') -Value $p.Id -Encoding ascii
Write-Output "Started offline dependency install in staging venv; worker PID $($p.Id)."
