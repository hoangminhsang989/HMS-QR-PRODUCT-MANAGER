param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Read-Section {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("os", "hardware", "volumes", "network", "listeners", "firewall_profiles", "firewall_rules", "services", "postgresql", "python", "hms", "certificates", "security", "time", "pending_reboot", "execution_context")]
        [string]$Name
    )
    try {
        $value = switch ($Name) {
            "os" {
                Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture, LastBootUpTime
            }
            "hardware" {
                Get-CimInstance Win32_ComputerSystem | Select-Object Name, Domain, PartOfDomain, TotalPhysicalMemory, NumberOfLogicalProcessors
            }
            "volumes" {
                Get-Volume | Select-Object DriveType, FileSystem, FileSystemLabel, Size, SizeRemaining, HealthStatus
            }
            "network" {
                Get-NetIPConfiguration | Select-Object InterfaceAlias, InterfaceDescription, NetProfile, IPv4Address, IPv6Address, IPv4DefaultGateway, DNSServer
            }
            "listeners" {
                Get-NetTCPConnection -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess
            }
            "firewall_profiles" {
                Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction
            }
            "firewall_rules" {
                Get-NetFirewallRule -Enabled True | Select-Object DisplayName, Direction, Action, Profile, PolicyStoreSourceType
            }
            "services" {
                Get-CimInstance -Query "SELECT Name, DisplayName, State, StartMode, StartName FROM Win32_Service" |
                    Select-Object Name, DisplayName, State, StartMode, StartName
            }
            "postgresql" {
                Get-CimInstance -Query "SELECT Name, DisplayName, State, StartMode, StartName FROM Win32_Service" |
                    Where-Object { $_.Name -like "postgresql*" -or $_.DisplayName -like "PostgreSQL*" } |
                    ForEach-Object {
                        [pscustomobject]@{
                            Name = $_.Name
                            DisplayName = $_.DisplayName
                            State = $_.State
                            StartMode = $_.StartMode
                            StartName = $_.StartName
                            executable_path = @{ state = "UNKNOWN"; reason = "UNSAFE_SOURCE_OMITTED" }
                            version = @{ state = "UNKNOWN"; reason = "SAFE_SOURCE_NOT_AVAILABLE" }
                        }
                    }
            }
            "python" {
                Get-Command python.exe -All | Select-Object Name, Source, Version
            }
            "hms" {
                Get-CimInstance -Query "SELECT Name, DisplayName, State, StartMode, StartName FROM Win32_Service" |
                    Where-Object { $_.Name -like "HMS*" -or $_.DisplayName -like "HMS*" } |
                    Select-Object Name, DisplayName, State, StartMode, StartName
            }
            "certificates" {
                Get-ChildItem Cert:\LocalMachine\My | Select-Object Thumbprint, Subject, Issuer, NotBefore, NotAfter, HasPrivateKey
            }
            "security" {
                Get-MpComputerStatus | Select-Object AntivirusEnabled, AntispywareEnabled, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated
            }
            "time" {
                $zone = Get-TimeZone
                $service = Get-Service W32Time
                [pscustomobject]@{ timezone_id = $zone.Id; time_service_status = $service.Status.ToString() }
            }
            "pending_reboot" {
                $paths = @(
                    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
                    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
                )
                [pscustomobject]@{ pending = [bool]($paths | Where-Object { Test-Path -LiteralPath $_ }) }
            }
            "execution_context" {
                $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
                $principal = [Security.Principal.WindowsPrincipal]::new($identity)
                [pscustomobject]@{
                    identity_name = $identity.Name
                    elevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
                    process_architecture = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString()
                }
            }
        }
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

$os = Read-Section -Name "os"
$computer = Read-Section -Name "hardware"
$volumes = Read-Section -Name "volumes"
$network = Read-Section -Name "network"
$listeners = Read-Section -Name "listeners"
$firewallProfiles = Read-Section -Name "firewall_profiles"
$firewallRules = Read-Section -Name "firewall_rules"
$services = Read-Section -Name "services"
$postgresql = Read-Section -Name "postgresql"
$python = Read-Section -Name "python"
$hms = Read-Section -Name "hms"
$certificates = Read-Section -Name "certificates"
$security = Read-Section -Name "security"
$time = Read-Section -Name "time"
$pendingReboot = Read-Section -Name "pending_reboot"
$executionContext = Read-Section -Name "execution_context"

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
    collector_version = "r011-wp1a-r1a1-1"
}

$inventory | ConvertTo-Json -Depth 12 -Compress
