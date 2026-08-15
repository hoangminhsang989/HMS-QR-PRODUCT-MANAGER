param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Read-Section {
    param([Parameter(Mandatory = $true)][scriptblock]$Reader)
    try {
        $value = & $Reader
        if ($null -eq $value -or @($value).Count -eq 0) {
            return @{ state = "NOT_PRESENT"; items = @() }
        }
        return @{ state = "KNOWN"; items = @($value) }
    }
    catch [System.UnauthorizedAccessException] {
        return @{ state = "ACCESS_DENIED"; items = @() }
    }
    catch [System.Management.Automation.CommandNotFoundException] {
        return @{ state = "UNSUPPORTED"; items = @() }
    }
    catch {
        return @{ state = "UNKNOWN"; items = @(); diagnostic_type = $_.Exception.GetType().Name }
    }
}

$os = Read-Section { Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture, LastBootUpTime }
$computer = Read-Section { Get-CimInstance Win32_ComputerSystem | Select-Object Name, Domain, PartOfDomain, TotalPhysicalMemory, NumberOfLogicalProcessors }
$volumes = Read-Section { Get-Volume | Select-Object DriveType, FileSystem, FileSystemLabel, Size, SizeRemaining, HealthStatus }
$network = Read-Section { Get-NetIPConfiguration | Select-Object InterfaceAlias, InterfaceDescription, NetProfile, IPv4Address, IPv6Address, IPv4DefaultGateway, DNSServer }
$listeners = Read-Section { Get-NetTCPConnection -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess }
$firewallProfiles = Read-Section { Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction }
$firewallRules = Read-Section { Get-NetFirewallRule -Enabled True | Select-Object DisplayName, Direction, Action, Profile, PolicyStoreSourceType }
$services = Read-Section { Get-CimInstance Win32_Service | Select-Object Name, DisplayName, State, StartMode, PathName, StartName }
$postgresql = Read-Section { Get-CimInstance Win32_Service | Where-Object { $_.Name -like "postgresql*" -or $_.DisplayName -like "PostgreSQL*" } | Select-Object Name, DisplayName, State, StartMode, PathName, StartName }
$python = Read-Section { Get-Command python.exe -All | Select-Object Name, Source, Version }
$hms = Read-Section { Get-CimInstance Win32_Service | Where-Object { $_.Name -like "HMS*" -or $_.DisplayName -like "HMS*" } | Select-Object Name, DisplayName, State, StartMode, PathName, StartName }
$certificates = Read-Section { Get-ChildItem Cert:\LocalMachine\My | Select-Object Thumbprint, Subject, Issuer, NotBefore, NotAfter, HasPrivateKey }
$security = Read-Section { Get-MpComputerStatus | Select-Object AntivirusEnabled, AntispywareEnabled, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated }
$time = Read-Section {
    $zone = Get-TimeZone
    $service = Get-Service W32Time
    [pscustomobject]@{ timezone_id = $zone.Id; time_service_status = $service.Status.ToString() }
}
$pendingReboot = Read-Section {
    $paths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
    )
    [pscustomobject]@{ pending = [bool]($paths | Where-Object { Test-Path -LiteralPath $_ }) }
}
$executionContext = Read-Section {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    [pscustomobject]@{
        identity_name = $identity.Name
        elevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        process_architecture = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString()
    }
}

$unknowns = @()
$sections = @{ os=$os; hardware=$computer; volumes=$volumes; network=$network; listeners=$listeners; firewall_profiles=$firewallProfiles; firewall_rules=$firewallRules; services=$services; postgresql=$postgresql; python=$python; hms_qr=$hms; tls=$certificates; time=$time; security=$security; pending_reboot=$pendingReboot; execution_context=$executionContext }
foreach ($entry in $sections.GetEnumerator()) {
    if ($entry.Value.state -in @("UNKNOWN", "ACCESS_DENIED", "UNSUPPORTED")) {
        $unknowns += @{ section = $entry.Key; state = $entry.Value.state }
    }
}

$inventory = [ordered]@{
    inventory_schema_version = "r011.machine-inventory.v1"
    captured_at = [DateTimeOffset]::UtcNow.ToString("o")
    machine_identity = @{ state = "KNOWN"; hostname = $env:COMPUTERNAME; execution_context = $executionContext }
    os = $os
    hardware = $computer
    volumes = $volumes
    network = $network
    listeners = $listeners
    firewall = @{ profiles = $firewallProfiles; rules = $firewallRules }
    services = $services
    postgresql = $postgresql
    python = $python
    hms_qr = $hms
    tls = $certificates
    time = $time
    security = $security
    pending_reboot = $pendingReboot
    unknowns = $unknowns
    collector_version = "r011-wp1a-1"
}

$inventory | ConvertTo-Json -Depth 12 -Compress
