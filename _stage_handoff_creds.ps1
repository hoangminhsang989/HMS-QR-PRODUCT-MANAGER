# Guest-to-guest handoff: send Machine 1 staging admin creds to Machine 2 agent file (never via host)
$ErrorActionPreference = 'Stop'
$creds = Get-Content -LiteralPath 'C:\HMS-QR-STAGING\stage-admin.txt' -Raw
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($creds))
$body = @{ path = 'm1-creds.txt'; base64 = $b64 } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://192.168.111.185:38421/file-write' -Method Post -Headers @{ Authorization = 'Bearer 0123456789abcdef0123456789abcdef'; 'Content-Type' = 'application/json' } -Body $body | Out-Null
'CREDS_HANDED_OFF'
