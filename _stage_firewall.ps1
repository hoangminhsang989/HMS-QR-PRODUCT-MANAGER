# Staging firewall: allow API TCP 8010 and discovery UDP 8011 from VMnet subnet only
$ErrorActionPreference = 'Stop'
$rules = @(
    @{ Name = 'HMS-QR-Staging-API-TCP-8010'; Protocol = 'TCP'; Port = 8010 },
    @{ Name = 'HMS-QR-Staging-Discovery-UDP-8011'; Protocol = 'UDP'; Port = 8011 }
)
foreach ($r in $rules) {
    if (-not (Get-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $r.Name -Direction Inbound -Protocol $r.Protocol -LocalPort $r.Port -Profile Public -RemoteAddress 192.168.111.0/24 -Action Allow | Out-Null
    }
}
Get-NetFirewallRule -DisplayName 'HMS-QR-Staging-*' | Select-Object DisplayName, Enabled, Direction, Action | Format-Table -AutoSize
'FIREWALL_OK'
