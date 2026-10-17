$ErrorActionPreference = 'Stop'
$root = 'C:\HMS-QR-STAGING'
$status = Join-Path $root 'pip-dryrun.status'
$stdout = Join-Path $root 'pip-dryrun.stdout.log'
$stderr = Join-Path $root 'pip-dryrun.stderr.log'
Remove-Item $status,$stdout,$stderr -Force -ErrorAction SilentlyContinue
$script = "& py -3.14 -m pip install --dry-run --no-index --find-links C:\exchange\QR\installer\wheels -r C:\exchange\QR\requirements.txt *> '$stdout'; `$code = `$LASTEXITCODE; Set-Content -LiteralPath '$status' -Value `$code -Encoding ascii"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
$p = Start-Process -FilePath "$PSHOME\powershell.exe" -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',$encoded) -WindowStyle Hidden -PassThru
Set-Content -LiteralPath (Join-Path $root 'pip-dryrun.pid') -Value $p.Id -Encoding ascii
Write-Output "Started background pip dry-run PID $($p.Id)."
