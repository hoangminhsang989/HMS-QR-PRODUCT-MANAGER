$ErrorActionPreference = 'Stop'
$PSModuleAutoLoadingPreference = 'None'
__AUTHORITY_ASSIGNMENTS__
function Get-Sha256([string]$path) {
    $stream = [IO.File]::OpenRead($path); $hash = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $hash.Dispose(); $stream.Dispose() }
}
function Copy-Verified([string]$source, [string]$name, [string]$expected, [string]$root) {
    $destination = [IO.Path]::Combine($root, $name)
    [IO.File]::Copy($source, $destination, $false)
    if ((Get-Sha256 $destination) -ine $expected) { throw "Hash mismatch: $name" }
    return $destination
}
function Assert-NoReparseAncestor([string]$path) {
    $current = [IO.DirectoryInfo]([IO.Path]::GetFullPath($path))
    while ($null -ne $current) {
        if ($current.Exists -and (($current.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) { throw "Reparse point forbidden: $($current.FullName)" }
        if ($current.Parent -eq $null -or $current.Parent.FullName -eq $current.FullName) { break }; $current = $current.Parent
    }
}
function Assert-SafeAttemptId([string]$attemptId) {
    if ($attemptId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$' -or $attemptId.Contains('..') -or $attemptId.EndsWith('.') -or $attemptId.EndsWith(' ') -or $attemptId.Contains(':') -or $attemptId.Contains('/') -or $attemptId.Contains([string][char]92)) { throw 'Attempt ID is not a safe direct child' }
    $stem = $attemptId.Split('.', 2)[0].ToUpperInvariant()
    if ($stem -in @('CON','PRN','AUX','NUL','COM1','COM2','COM3','COM4','COM5','COM6','COM7','COM8','COM9','LPT1','LPT2','LPT3','LPT4','LPT5','LPT6','LPT7','LPT8','LPT9')) { throw 'Attempt ID uses a reserved Windows device basename' }
}
function Ensure-AdminOnlyDirectory([string]$path) {
    if ([IO.Directory]::Exists($path) -and (([IO.File]::GetAttributes($path) -band [IO.FileAttributes]::ReparsePoint) -ne 0)) { throw "Reparse point forbidden: $path" }
    if ([IO.File]::Exists($path)) { throw "Staging namespace is not a directory: $path" }
    $sddl = 'O:BAD:PAI(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'
    $security = [Security.AccessControl.DirectorySecurity]::new(); $security.SetSecurityDescriptorSddlForm($sddl)
    if (-not [IO.Directory]::Exists($path)) { [void][IO.Directory]::CreateDirectory($path, $security) }
    $readback = [IO.Directory]::GetAccessControl($path, 'Access,Owner')
    if (-not $readback.AreAccessRulesProtected -or $readback.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::All) -ine $sddl) { throw "Admin-only staging ACL readback failed: $path" }
}
function Create-AttemptClaim([string]$attemptRoot) {
    try { $stream = [IO.File]::Open([IO.Path]::Combine($attemptRoot, 'attempt.claim'), [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None); $stream.Dispose() }
    catch [IO.IOException] { throw 'Attempt claim already exists' }
}
if ([DateTime]::UtcNow -gt [DateTime]::Parse($authority.expires_utc).ToUniversalTime()) { throw 'D2 authority expired before staging' }
if ([Environment]::MachineName -ine $authority.machine_name) { throw 'Machine identity does not match frozen authority' }
$target = [IO.Path]::GetFullPath([string]$authority.target_root)
if ($target -ine [string]$authority.target_root -or -not [IO.Directory]::Exists($target)) { throw 'Production target prestate is not exact' }
Assert-NoReparseAncestor $target
$rootSddl = "O:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FX;;;$($authority.service_sid))"
$rootAcl = [IO.Directory]::GetAccessControl($target, 'Access,Owner')
if (-not $rootAcl.AreAccessRulesProtected -or $rootAcl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::All) -ine $rootSddl) { throw 'Production target owner/DACL prestate is not exact' }
$stagingRoot = [IO.Path]::Combine($target, 'staging')
Assert-SafeAttemptId ([string]$authority.attempt_id)
$namespaceRoot = [IO.Path]::Combine($stagingRoot, '.hms-qr-d2')
$attemptRoot = [IO.Path]::GetFullPath([IO.Path]::Combine($namespaceRoot, [string]$authority.attempt_id))
if ($attemptRoot -ine [IO.Path]::Combine($namespaceRoot, [string]$authority.attempt_id)) { throw 'Attempt path is not confined to D2 namespace' }
if ([IO.Directory]::Exists($attemptRoot)) { throw 'Attempt staging already exists' }
Ensure-AdminOnlyDirectory $stagingRoot
Assert-NoReparseAncestor $stagingRoot
Ensure-AdminOnlyDirectory $namespaceRoot
Assert-NoReparseAncestor $namespaceRoot
Ensure-AdminOnlyDirectory $attemptRoot
Create-AttemptClaim $attemptRoot
$payload = Copy-Verified ([string]$authority.payload_source) 'r011_d2_protected_payload.ps1' ([string]$authority.payload_sha256) $attemptRoot
$runtime = Copy-Verified ([string]$authority.runtime_archive) 'python-embed.zip' ([string]$authority.runtime_sha256) $attemptRoot
$bundle = Copy-Verified ([string]$authority.bundle_source) 'deployment-bundle.zip' ([string]$authority.bundle_sha256) $attemptRoot
& $payload -Authority $authority -StagingPath $attemptRoot -ProtectedPayloadPath $payload -ProtectedRuntimeArchive $runtime -ProtectedBundle $bundle
