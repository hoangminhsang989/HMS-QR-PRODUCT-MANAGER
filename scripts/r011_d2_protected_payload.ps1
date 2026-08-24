[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][hashtable]$Authority,
    [Parameter(Mandatory = $true)][string]$StagingPath,
    [Parameter(Mandatory = $true)][string]$ProtectedPayloadPath,
    [Parameter(Mandatory = $true)][string]$ProtectedRuntimeArchive,
    [Parameter(Mandatory = $true)][string]$ProtectedBundle
)

$ErrorActionPreference = 'Stop'
$PSModuleAutoLoadingPreference = 'None'
function Get-Sha256([string]$path) {
    $stream = [IO.File]::OpenRead($path); $hash = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $hash.Dispose(); $stream.Dispose() }
}
function Assert-EqualValue([string]$actual, [string]$expected, [string]$label) { if ($actual -ine $expected) { throw "$label did not match frozen authority" } }
function Assert-Hash([string]$path, [string]$expected, [string]$label) { Assert-EqualValue (Get-Sha256 $path) $expected $label }
function Get-RoleSddl([string]$serviceSid, [string]$role) {
    $service = if ($role -in @('releases', 'runtime')) { "(A;OICI;0x1200a9;;;$serviceSid)" } else { '' }
    return "O:BAD:PAI(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)$service"
}
function Set-ProtectedDirectory([string]$path, [string]$sddl) {
    $security = [Security.AccessControl.DirectorySecurity]::new(); $security.SetSecurityDescriptorSddlForm($sddl)
    if (-not [IO.Directory]::Exists($path)) { [void][IO.Directory]::CreateDirectory($path, $security) } else { [IO.Directory]::SetAccessControl($path, $security) }
    Assert-DeploymentAcl $path $sddl
}
function Assert-DeploymentAcl([string]$path, [string]$expectedSddl) {
    $acl = [IO.Directory]::GetAccessControl($path, 'Access,Owner')
    if (-not $acl.AreAccessRulesProtected) { throw 'Deployment ACL inheritance is not protected' }
    Assert-EqualValue $acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::All) $expectedSddl 'Deployment SDDL readback'
    $dangerous = [Security.AccessControl.FileSystemRights]::WriteDac -bor [Security.AccessControl.FileSystemRights]::WriteOwner -bor [Security.AccessControl.FileSystemRights]::Delete -bor [Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles
    foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
        $sid = $rule.IdentityReference.Value
        if ($sid -in @('S-1-1-0', 'S-1-5-11', 'S-1-5-32-545')) { throw "Broad principal forbidden: $sid" }
        if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow) { throw 'Deny ACEs are not part of D2 contract' }
        if ($sid -notin @('S-1-5-18', 'S-1-5-32-544', [string]$Authority.service_sid) -and (($rule.FileSystemRights -band $dangerous) -ne 0)) { throw "Unexpected dangerous authority: $sid" }
    }
}
function Get-ZipEntries([string]$archive) {
    $framework = [Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()
    $compression = [IO.Path]::Combine($framework, 'System.IO.Compression.FileSystem.dll')
    if (-not [IO.File]::Exists($compression)) { throw 'OS-trusted compression assembly is absent' }
    [void][Reflection.Assembly]::LoadFrom($compression)
    $zip = [IO.Compression.ZipFile]::OpenRead($archive); $seen = @{}
    try {
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName; $mode = ([uint32]$entry.ExternalAttributes -shr 16) -band 0xF000; $dos = [uint32]$entry.ExternalAttributes -band 0xFFFF
            if (-not $name -or $name.StartsWith('/') -or $name.StartsWith([string][char]92) -or $name -match '(^|/|\\)\.\.($|/|\\)' -or $name.Contains(':') -or $seen.ContainsKey($name) -or ($mode -notin @(0, 0x8000)) -or (($dos -band 0x400) -ne 0)) { throw "Unsafe ZIP entry: $name" }
            $seen[$name] = $entry
        }
        return $seen
    } finally { $zip.Dispose() }
}
function Get-EntrySha256([object]$entry) {
    $stream = $entry.Open(); $hash = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $hash.Dispose(); $stream.Dispose() }
}
function Expand-SafeZip([string]$archive, [string]$destination) {
    $entries = Get-ZipEntries $archive; $root = [IO.Path]::GetFullPath($destination); [void][IO.Directory]::CreateDirectory($root)
    $zip = [IO.Compression.ZipFile]::OpenRead($archive); $expected = @{}
    try {
        foreach ($entry in $zip.Entries) {
            $out = [IO.Path]::GetFullPath([IO.Path]::Combine($root, $entry.FullName))
            if ($out -ne $root -and -not $out.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "ZIP escapes destination: $($entry.FullName)" }
            if ($entry.FullName.EndsWith('/')) { [void][IO.Directory]::CreateDirectory($out); continue }
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($out)); if ([IO.File]::Exists($out)) { throw "ZIP collision: $($entry.FullName)" }
            $expected[$entry.FullName] = Get-EntrySha256 $entry
            $input = $entry.Open(); $output = [IO.File]::Open($out, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
            try { $input.CopyTo($output) } finally { $output.Dispose(); $input.Dispose() }
            Assert-Hash $out ([string]$expected[$entry.FullName]) "Extracted ZIP entry $($entry.FullName)"
        }
    } finally { $zip.Dispose() }
    return $expected
}
function Assert-ExactFiles([string]$root, [hashtable]$expected, [string]$label) {
    $actual = @{}; foreach ($file in [IO.Directory]::EnumerateFiles($root, '*', [IO.SearchOption]::AllDirectories)) { $relative = $file.Substring($root.Length).TrimStart([char]92, [char]47).Replace([char]92, [char]47); $actual[$relative] = Get-Sha256 $file }
    if ($actual.Count -ne $expected.Count) { throw "$label file count mismatch" }
    foreach ($name in $expected.Keys) { if (-not $actual.ContainsKey($name) -or $actual[$name] -ine [string]$expected[$name]) { throw "$label exact file set/hash mismatch: $name" } }
}
function Assert-BundleManifest([string]$app, [hashtable]$extracted) {
    $manifestPath = [IO.Path]::Combine($app, 'bundle-manifest.txt'); if (-not [IO.File]::Exists($manifestPath)) { throw 'Deployment bundle manifest is absent' }
    $expected = @{}; foreach ($line in [IO.File]::ReadAllLines($manifestPath)) { if ($line -notmatch '^([0-9a-f]{64}) ([A-Za-z0-9_./-]+)$') { throw 'Deployment bundle manifest line is invalid' }; $expected[$Matches[2]] = $Matches[1] }
    if ($expected.Count -eq 0 -or $extracted.Count -ne ($expected.Count + 1)) { throw 'Deployment bundle manifest/file set mismatch' }
    foreach ($name in $expected.Keys) { if (-not $extracted.ContainsKey($name) -or [string]$extracted[$name] -ine [string]$expected[$name]) { throw "Deployment bundle manifest hash mismatch: $name" } }
    Assert-ExactFiles $app $extracted 'Deployment bundle'
}
function Set-OneShotLatch([string]$root) {
    try { $stream = [IO.File]::Open([IO.Path]::Combine($root, 'apply.latch'), [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None); $stream.Dispose() }
    catch [IO.IOException] { throw 'This authority has already consumed its apply latch' }
}
function Assert-NoReparseAncestor([string]$path) {
    $current = [IO.DirectoryInfo]([IO.Path]::GetFullPath($path))
    while ($null -ne $current) {
        if ($current.Exists -and (($current.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) { throw "Reparse point forbidden: $($current.FullName)" }
        if ($current.Parent -eq $null -or $current.Parent.FullName -eq $current.FullName) { break }; $current = $current.Parent
    }
}
function Assert-PostState([string]$target, [string[]]$roles) {
    Assert-NoReparseAncestor $target
    foreach ($role in $roles) {
        $path = [IO.Path]::Combine($target, $role)
        if (-not [IO.Directory]::Exists($path)) { throw "Poststate role missing: $role" }
        Assert-NoReparseAncestor $path
        Assert-DeploymentAcl $path (Get-RoleSddl ([string]$Authority.service_sid) $role)
    }
}

if ([DateTime]::UtcNow -gt [DateTime]::Parse($Authority.expires_utc).ToUniversalTime()) { throw 'D2 authority expired before apply' }
Assert-EqualValue ([Environment]::MachineName) ([string]$Authority.machine_name) 'Machine identity'; Assert-EqualValue ([IO.Path]::GetFullPath([string]$Authority.target_root)) ([string]$Authority.target_root) 'Production target'
Assert-Hash $ProtectedPayloadPath ([string]$Authority.payload_sha256) 'Protected payload'; Assert-Hash $ProtectedRuntimeArchive ([string]$Authority.runtime_sha256) 'Protected runtime archive'; Assert-Hash $ProtectedBundle ([string]$Authority.bundle_sha256) 'Protected deployment bundle'
$runtime = [IO.Path]::Combine($StagingPath, 'runtime'); Set-ProtectedDirectory $runtime (Get-RoleSddl ([string]$Authority.service_sid) 'runtime')
$runtimeFiles = Expand-SafeZip $ProtectedRuntimeArchive $runtime
if (-not $runtimeFiles.ContainsKey('python.exe') -or -not $runtimeFiles.ContainsKey('python314.zip')) { throw 'Private runtime archive layout is incomplete' }
Assert-ExactFiles $runtime $runtimeFiles 'Private runtime archive'
$app = [IO.Path]::Combine($runtime, 'app'); Set-ProtectedDirectory $app (Get-RoleSddl ([string]$Authority.service_sid) 'runtime'); $bundleFiles = Expand-SafeZip $ProtectedBundle $app; Assert-BundleManifest $app $bundleFiles
$pth = ".`r`npython314.zip`r`napp`r`n"; $pthPath = [IO.Path]::Combine($runtime, 'python314._pth'); [IO.File]::WriteAllText($pthPath, $pth, [Text.UTF8Encoding]::new($false)); $runtimeFiles['python314._pth'] = ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.UTF8Encoding]::new($false).GetBytes($pth)))).Replace('-', '').ToLowerInvariant()
foreach ($name in $bundleFiles.Keys) { $runtimeFiles['app/' + $name] = $bundleFiles[$name] }; Assert-ExactFiles $runtime $runtimeFiles 'Final private runtime'
if ([DateTime]::UtcNow -gt [DateTime]::Parse($Authority.expires_utc).ToUniversalTime()) { throw 'D2 authority expired before irreversible apply' }
Set-OneShotLatch $StagingPath; $python = [IO.Path]::Combine($runtime, 'python.exe'); if (-not [IO.File]::Exists($python)) { throw 'Private Python executable is absent' }
$argv = @('-B', '-m', 'packages.deployment.provisioning', '--target-root', [string]$Authority.target_root, '--service-account', [string]$Authority.service_account, '--roles', 'releases', 'runtime', 'staging', '--apply')
$unsafeArgument = $false; foreach ($argument in $argv) { if ($argument -match '[\s"]') { $unsafeArgument = $true } }; if ($unsafeArgument) { throw 'Frozen provisioner argv contains unsupported whitespace or quotes' }
$start = [Diagnostics.ProcessStartInfo]::new(); $start.FileName = $python; $start.Arguments = [string]::Join(' ', $argv); $start.UseShellExecute = $false; $process = [Diagnostics.Process]::new(); $process.StartInfo = $start
if (-not $process.Start()) { throw 'Private Python process did not start' }; $process.WaitForExit(); if ($process.ExitCode -ne 0) { throw "Provisioner failed with native exit code $($process.ExitCode); retry is forbidden" }
Assert-PostState ([string]$Authority.target_root) @('releases', 'runtime', 'staging')
[IO.File]::WriteAllText([IO.Path]::Combine($StagingPath, 'terminal-evidence.json'), "{`"schema`":`"r011.d2.one-shot.v1`",`"status`":`"APPLIED`",`"attempt_id`":`"$($Authority.attempt_id)`"}", [Text.UTF8Encoding]::new($false))
