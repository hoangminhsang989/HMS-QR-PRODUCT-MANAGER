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
function Get-BytesSha256([byte[]]$bytes) {
    $hash = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $hash.Dispose() }
}
function Write-DurableEvidenceBytes([string]$path, [byte[]]$bytes) {
    $temporary = $path + '.tmp'
    $stream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
    Move-EvidenceFile $temporary $path
    $readback = Read-EvidenceBytes $path
    if ($readback.Length -ne $bytes.Length -or (Get-BytesSha256 $readback) -ine (Get-BytesSha256 $bytes)) { throw 'Durable evidence readback mismatch' }
}
function Move-EvidenceFile([string]$source, [string]$destination) { [IO.File]::Move($source, $destination) }
function Read-EvidenceBytes([string]$path) { return [IO.File]::ReadAllBytes($path) }
function Test-EqualBytes([byte[]]$left, [byte[]]$right) {
    return $left.Length -eq $right.Length -and (Get-BytesSha256 $left) -ieq (Get-BytesSha256 $right)
}
function Write-DurableCommitBytes([string]$path, [byte[]]$bytes) {
    $stream = [IO.File]::Open($path, [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $durable = $false
    try {
        $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true); $stream.Position = 0
        $readback = [byte[]]::new($bytes.Length); $offset = 0
        while ($offset -lt $readback.Length) { $count = $stream.Read($readback, $offset, $readback.Length - $offset); if ($count -eq 0) { break }; $offset += $count }
        if ($offset -ne $bytes.Length -or -not (Test-EqualBytes $readback $bytes)) { throw 'Durable commit readback mismatch' }
        $durable = $true
    } finally {
        if ($durable) { try { $stream.Dispose() } catch {} } else { $stream.Dispose() }
    }
}
function Set-OneShotLatch([string]$root, [string]$baselineSha256) {
    $bytes = [Text.Encoding]::ASCII.GetBytes("baseline_sha256=$baselineSha256`n")
    try { Write-DurableCommitBytes ([IO.Path]::Combine($root, 'apply.latch')) $bytes }
    catch [IO.IOException] { throw 'This authority has already consumed its apply latch' }
}
function Read-LatchBaselineSha256([string]$latchPath) {
    if (-not [IO.File]::Exists($latchPath)) { throw 'Durable apply latch is absent' }
    $bytes = Read-EvidenceBytes $latchPath
    $prefix = [Text.Encoding]::ASCII.GetBytes('baseline_sha256=')
    if ($bytes.Length -ne ($prefix.Length + 65)) { throw 'Durable apply latch is malformed' }
    for ($index = 0; $index -lt $prefix.Length; $index++) { if ($bytes[$index] -ne $prefix[$index]) { throw 'Durable apply latch is malformed' } }
    for ($index = $prefix.Length; $index -lt ($prefix.Length + 64); $index++) {
        $value = $bytes[$index]
        if (-not (($value -ge 0x30 -and $value -le 0x39) -or ($value -ge 0x61 -and $value -le 0x66))) { throw 'Durable apply latch is malformed' }
    }
    if ($bytes[$bytes.Length - 1] -ne 0x0a) { throw 'Durable apply latch is malformed' }
    $digest = [Text.Encoding]::ASCII.GetString($bytes, $prefix.Length, 64)
    $expected = [Text.Encoding]::ASCII.GetBytes("baseline_sha256=$digest`n")
    if (-not (Test-EqualBytes $bytes $expected)) { throw 'Durable apply latch is malformed' }
    return $digest
}
function New-TerminalEnvelopeBytes([string]$status, [string]$phase, [Nullable[int]]$nativeExitCode, [string]$failureCode, [string]$detail) {
    if ($status -notin @('SUCCESS', 'FAILED', 'INDETERMINATE')) { throw 'Terminal status is invalid' }
    foreach ($token in @($phase, $failureCode)) { if ($token -notmatch '^[A-Z0-9_.-]{1,64}$') { throw 'Terminal evidence token is invalid' } }
    $native = if ($null -eq $nativeExitCode) { 'null' } else { $nativeExitCode.ToString([Globalization.CultureInfo]::InvariantCulture) }
    $detailBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($detail))
    $payload = '{' +
        '"attempt_id":"' + [string]$Authority.attempt_id + '",' +
        '"failure_code":"' + $failureCode + '",' +
        '"failure_detail_base64":"' + $detailBase64 + '",' +
        '"native_exit_code":' + $native + ',' +
        '"phase":"' + $phase + '",' +
        '"retry_authorized":false,' +
        '"status":"' + $status + '",' +
        '"trust_manifest_sha256":"' + [string]$Authority.trust_manifest_sha256 + '"' +
        '}'
    $payloadBytes = [Text.Encoding]::UTF8.GetBytes($payload)
    $payloadHash = Get-BytesSha256 $payloadBytes
    $envelope = '{' +
        '"payload_base64":"' + [Convert]::ToBase64String($payloadBytes) + '",' +
        '"payload_sha256":"' + $payloadHash + '",' +
        '"schema":"r011.d2.terminal-envelope.v1"' +
        '}'
    return [Text.Encoding]::UTF8.GetBytes($envelope)
}
function Publish-TerminalEvidence([string]$path, [string]$status, [string]$phase, [Nullable[int]]$nativeExitCode, [string]$failureCode, [string]$detail) {
    $bytes = New-TerminalEnvelopeBytes $status $phase $nativeExitCode $failureCode $detail
    Write-DurableEvidenceBytes $path $bytes
}
function New-TerminalAuthorityIndexBytes([string]$baselineSha256, [string]$terminalSha256) {
    $index = '{' +
        '"authoritative_receipt":"terminal-evidence.json",' +
        '"baseline_sha256":"' + $baselineSha256 + '",' +
        '"schema":"r011.d2.terminal-authority-index.v1",' +
        '"terminal_sha256":"' + $terminalSha256 + '"' +
        '}'
    return [Text.Encoding]::UTF8.GetBytes($index)
}
function Publish-AuthoritativeTerminalEvidence([string]$baselinePath, [string]$latchPath, [string]$terminalPath, [string]$indexPath, [string]$status, [string]$phase, [Nullable[int]]$nativeExitCode, [string]$failureCode, [string]$detail) {
    $baselineHash = Get-BytesSha256 (Read-EvidenceBytes $baselinePath)
    $latchedBaselineHash = Read-LatchBaselineSha256 $latchPath
    if ($latchedBaselineHash -cne $baselineHash) { throw 'Terminal baseline does not match durable apply latch' }
    $bytes = New-TerminalEnvelopeBytes $status $phase $nativeExitCode $failureCode $detail
    Write-DurableEvidenceBytes $terminalPath $bytes
    $terminalHash = Get-BytesSha256 (Read-EvidenceBytes $terminalPath)
    $indexBytes = New-TerminalAuthorityIndexBytes $baselineHash $terminalHash
    Write-DurableCommitBytes $indexPath $indexBytes
}
function Resolve-TerminalEvidencePath([string]$baselinePath, [string]$latchPath, [string]$terminalPath, [string]$indexPath) {
    if (-not [IO.File]::Exists($baselinePath)) { throw 'Durable terminal baseline is absent' }
    $baselineHash = Get-BytesSha256 (Read-EvidenceBytes $baselinePath)
    $latchedBaselineHash = Read-LatchBaselineSha256 $latchPath
    if ($latchedBaselineHash -cne $baselineHash) { throw 'Terminal baseline does not match durable apply latch' }
    if (-not [IO.File]::Exists($terminalPath) -or -not [IO.File]::Exists($indexPath)) { return $baselinePath }
    $terminalHash = Get-BytesSha256 (Read-EvidenceBytes $terminalPath)
    $expected = New-TerminalAuthorityIndexBytes $baselineHash $terminalHash
    $actual = Read-EvidenceBytes $indexPath
    if (-not (Test-EqualBytes $actual $expected)) { return $baselinePath }
    return $terminalPath
}
function Publish-NativeExitEvidence([string]$root, [int]$nativeExitCode) {
    $bytes = [Text.Encoding]::ASCII.GetBytes($nativeExitCode.ToString([Globalization.CultureInfo]::InvariantCulture) + "`n")
    Write-DurableEvidenceBytes ([IO.Path]::Combine($root, 'provisioner-native-exit-code.txt')) $bytes
}
function Get-TerminalFailureClassification([string]$phase, [Nullable[int]]$nativeExitCode) {
    if ($phase -eq 'NATIVE_EXIT_PUBLICATION') { return @{ status = 'INDETERMINATE'; failure_code = 'NATIVE_EXIT_PUBLICATION_FAILED' } }
    if ($null -eq $nativeExitCode) { return @{ status = 'INDETERMINATE'; failure_code = 'INTERRUPTED_OR_NO_NATIVE_EXIT' } }
    if ($nativeExitCode -ne 0) { return @{ status = 'FAILED'; failure_code = 'NATIVE_NONZERO' } }
    return @{ status = 'FAILED'; failure_code = 'POSTSTATE_FAILED' }
}
function New-NativeDelegateType([Type[]]$parameterTypes, [Type]$returnType) {
    if ($null -eq $script:D2NativeDelegateModule) {
        $assemblyName = [Reflection.AssemblyName]::new('HmsQrD2NativeDelegates')
        $assembly = [AppDomain]::CurrentDomain.DefineDynamicAssembly($assemblyName, [Reflection.Emit.AssemblyBuilderAccess]::Run)
        $script:D2NativeDelegateModule = $assembly.DefineDynamicModule('NativeDelegates')
    }
    $attributes = [Reflection.TypeAttributes]'Class, Public, Sealed, AnsiClass, AutoClass'
    $builder = $script:D2NativeDelegateModule.DefineType(('D2NativeDelegate' + [Guid]::NewGuid().ToString('N')), $attributes, [MulticastDelegate])
    $unmanagedCtor = [Runtime.InteropServices.UnmanagedFunctionPointerAttribute].GetConstructor([Type[]]@([Runtime.InteropServices.CallingConvention]))
    $unmanaged = [Reflection.Emit.CustomAttributeBuilder]::new($unmanagedCtor, @([Runtime.InteropServices.CallingConvention]::Winapi))
    $builder.SetCustomAttribute($unmanaged)
    $ctor = $builder.DefineConstructor([Reflection.MethodAttributes]'RTSpecialName, HideBySig, Public', [Reflection.CallingConventions]::Standard, $parameterTypes)
    $ctor.SetImplementationFlags([Reflection.MethodImplAttributes]'Runtime, Managed')
    $invoke = $builder.DefineMethod('Invoke', [Reflection.MethodAttributes]'Public, HideBySig, NewSlot, Virtual', $returnType, $parameterTypes)
    $invoke.SetImplementationFlags([Reflection.MethodImplAttributes]'Runtime, Managed')
    return $builder.CreateType()
}
function Get-NativeFunctionPointer([string]$name) {
    $frameworkAssembly = [Data.DataTable].Assembly
    $publicKeyToken = ([BitConverter]::ToString($frameworkAssembly.GetName().GetPublicKeyToken())).Replace('-', '').ToLowerInvariant()
    if (-not $frameworkAssembly.GlobalAssemblyCache -or $publicKeyToken -ne 'b77a5c561934e089') { throw 'OS framework native resolver identity is not trusted' }
    $candidate = $frameworkAssembly.GetType('System.Data.Common.SafeNativeMethods', $false)
    if ($null -eq $candidate) { throw 'OS framework native resolver is unavailable' }
    $getModuleHandle = $null; $getProcAddress = $null
    foreach ($method in $candidate.GetMethods([Reflection.BindingFlags]'Static, NonPublic, Public')) {
        $parameters = $method.GetParameters()
        if ($method.Name -eq 'GetModuleHandle' -and $parameters.Count -eq 1 -and $parameters[0].ParameterType -eq [string]) { $getModuleHandle = $method }
        if ($method.Name -eq 'GetProcAddress' -and $parameters.Count -eq 2 -and $parameters[0].ParameterType -eq [IntPtr] -and $parameters[1].ParameterType -eq [string]) { $getProcAddress = $method }
    }
    if ($null -eq $getModuleHandle -or $null -eq $getProcAddress) { throw 'OS native symbol resolver is unavailable' }
    $module = [IntPtr]$getModuleHandle.Invoke($null, @('kernel32.dll'))
    $pointer = [IntPtr]$getProcAddress.Invoke($null, @($module, $name))
    if ($pointer -eq [IntPtr]::Zero) { throw "OS native function is unavailable: $name" }
    return $pointer
}
function Get-NativeDelegate([string]$name, [Type[]]$parameterTypes, [Type]$returnType) {
    $type = New-NativeDelegateType $parameterTypes $returnType
    return [Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer((Get-NativeFunctionPointer $name), $type)
}
function Initialize-D2NativeApi() {
    if ($null -ne $script:D2NativeApi) { return }
    $script:D2NativeApi = @{
        CreateJobObjectW = Get-NativeDelegate 'CreateJobObjectW' ([Type[]]@([IntPtr], [IntPtr])) ([IntPtr])
        SetInformationJobObject = Get-NativeDelegate 'SetInformationJobObject' ([Type[]]@([IntPtr], [int], [IntPtr], [uint32])) ([bool])
        QueryInformationJobObject = Get-NativeDelegate 'QueryInformationJobObject' ([Type[]]@([IntPtr], [int], [IntPtr], [uint32], [IntPtr])) ([bool])
        InitializeProcThreadAttributeList = Get-NativeDelegate 'InitializeProcThreadAttributeList' ([Type[]]@([IntPtr], [uint32], [uint32], [IntPtr])) ([bool])
        UpdateProcThreadAttribute = Get-NativeDelegate 'UpdateProcThreadAttribute' ([Type[]]@([IntPtr], [uint32], [IntPtr], [IntPtr], [UIntPtr], [IntPtr], [IntPtr])) ([bool])
        DeleteProcThreadAttributeList = Get-NativeDelegate 'DeleteProcThreadAttributeList' ([Type[]]@([IntPtr])) ([void])
        CreateProcessW = Get-NativeDelegate 'CreateProcessW' ([Type[]]@([IntPtr], [IntPtr], [IntPtr], [IntPtr], [bool], [uint32], [IntPtr], [IntPtr], [IntPtr], [IntPtr])) ([bool])
        IsProcessInJob = Get-NativeDelegate 'IsProcessInJob' ([Type[]]@([IntPtr], [IntPtr], [IntPtr])) ([bool])
        ResumeThread = Get-NativeDelegate 'ResumeThread' ([Type[]]@([IntPtr])) ([uint32])
        WaitForSingleObject = Get-NativeDelegate 'WaitForSingleObject' ([Type[]]@([IntPtr], [uint32])) ([uint32])
        GetExitCodeProcess = Get-NativeDelegate 'GetExitCodeProcess' ([Type[]]@([IntPtr], [IntPtr])) ([bool])
        TerminateProcess = Get-NativeDelegate 'TerminateProcess' ([Type[]]@([IntPtr], [uint32])) ([bool])
        TerminateJobObject = Get-NativeDelegate 'TerminateJobObject' ([Type[]]@([IntPtr], [uint32])) ([bool])
        CloseHandle = Get-NativeDelegate 'CloseHandle' ([Type[]]@([IntPtr])) ([bool])
        GetLastError = Get-NativeDelegate 'GetLastError' ([Type[]]@()) ([uint32])
    }
}
function Close-D2NativeHandle([IntPtr]$handle) { if ($handle -ne [IntPtr]::Zero) { [void]$script:D2NativeApi.CloseHandle.Invoke($handle) } }
function Start-ContainedProcess([string]$executable, [string]$arguments, [string]$workingDirectory) {
    Initialize-D2NativeApi
    if ($executable.Contains('"') -or $arguments.Contains("`0") -or $workingDirectory.Contains('"')) { throw 'Contained process input is invalid' }
    $job = [IntPtr]::Zero; $process = [IntPtr]::Zero; $thread = [IntPtr]::Zero
    $jobInfo = [IntPtr]::Zero; $queryInfo = [IntPtr]::Zero; $startup = [IntPtr]::Zero; $processInfo = [IntPtr]::Zero
    $attributeSize = [IntPtr]::Zero; $attributeList = [IntPtr]::Zero; $jobAttribute = [IntPtr]::Zero
    $application = [IntPtr]::Zero; $commandLine = [IntPtr]::Zero; $currentDirectory = [IntPtr]::Zero
    $assigned = $false; $resumed = $false
    try {
        $job = [IntPtr]$script:D2NativeApi.CreateJobObjectW.Invoke([IntPtr]::Zero, [IntPtr]::Zero)
        if ($job -eq [IntPtr]::Zero) { throw 'CreateJobObjectW failed' }
        $jobInfoSize = if ([IntPtr]::Size -eq 8) { 144 } else { 112 }
        $jobInfo = [Runtime.InteropServices.Marshal]::AllocHGlobal($jobInfoSize); $queryInfo = [Runtime.InteropServices.Marshal]::AllocHGlobal($jobInfoSize)
        [Runtime.InteropServices.Marshal]::Copy([byte[]]::new($jobInfoSize), 0, $jobInfo, $jobInfoSize)
        [Runtime.InteropServices.Marshal]::Copy([byte[]]::new($jobInfoSize), 0, $queryInfo, $jobInfoSize)
        [Runtime.InteropServices.Marshal]::WriteInt32($jobInfo, 16, 0x00002000)
        if (-not $script:D2NativeApi.SetInformationJobObject.Invoke($job, 9, $jobInfo, [uint32]$jobInfoSize)) { throw 'SetInformationJobObject failed' }
        if (-not $script:D2NativeApi.QueryInformationJobObject.Invoke($job, 9, $queryInfo, [uint32]$jobInfoSize, [IntPtr]::Zero)) { throw 'QueryInformationJobObject failed' }
        $effectiveFlags = [Runtime.InteropServices.Marshal]::ReadInt32($queryInfo, 16)
        if (($effectiveFlags -band 0x00002000) -eq 0 -or ($effectiveFlags -band 0x00000c00) -ne 0) { throw 'Job containment flags are not exact' }
        $baseStartupSize = if ([IntPtr]::Size -eq 8) { 104 } else { 68 }; $startupSize = $baseStartupSize + [IntPtr]::Size
        $processInfoSize = if ([IntPtr]::Size -eq 8) { 24 } else { 16 }
        $attributeSize = [Runtime.InteropServices.Marshal]::AllocHGlobal([IntPtr]::Size); [Runtime.InteropServices.Marshal]::WriteIntPtr($attributeSize, [IntPtr]::Zero)
        [void]$script:D2NativeApi.InitializeProcThreadAttributeList.Invoke([IntPtr]::Zero, [uint32]1, [uint32]0, $attributeSize)
        $attributeBytes = [Runtime.InteropServices.Marshal]::ReadIntPtr($attributeSize).ToInt64()
        if ($attributeBytes -le 0 -or $attributeBytes -gt 65536) { throw 'PROC_THREAD_ATTRIBUTE_LIST size is invalid' }
        $attributeList = [Runtime.InteropServices.Marshal]::AllocHGlobal([IntPtr]$attributeBytes)
        if (-not $script:D2NativeApi.InitializeProcThreadAttributeList.Invoke($attributeList, [uint32]1, [uint32]0, $attributeSize)) { throw 'InitializeProcThreadAttributeList failed' }
        $jobAttribute = [Runtime.InteropServices.Marshal]::AllocHGlobal([IntPtr]::Size); [Runtime.InteropServices.Marshal]::WriteIntPtr($jobAttribute, $job)
        $attributeValueSize = [UIntPtr]::new([uint64][IntPtr]::Size)
        if (-not $script:D2NativeApi.UpdateProcThreadAttribute.Invoke($attributeList, [uint32]0, [IntPtr]0x0002000d, $jobAttribute, $attributeValueSize, [IntPtr]::Zero, [IntPtr]::Zero)) { throw 'PROC_THREAD_ATTRIBUTE_JOB_LIST publication failed' }
        $startup = [Runtime.InteropServices.Marshal]::AllocHGlobal($startupSize); $processInfo = [Runtime.InteropServices.Marshal]::AllocHGlobal($processInfoSize)
        [Runtime.InteropServices.Marshal]::Copy([byte[]]::new($startupSize), 0, $startup, $startupSize)
        [Runtime.InteropServices.Marshal]::Copy([byte[]]::new($processInfoSize), 0, $processInfo, $processInfoSize)
        [Runtime.InteropServices.Marshal]::WriteInt32($startup, $startupSize)
        [Runtime.InteropServices.Marshal]::WriteIntPtr($startup, $baseStartupSize, $attributeList)
        $application = [Runtime.InteropServices.Marshal]::StringToHGlobalUni($executable)
        $commandLine = [Runtime.InteropServices.Marshal]::StringToHGlobalUni(('"' + $executable + '" ' + $arguments))
        $currentDirectory = [Runtime.InteropServices.Marshal]::StringToHGlobalUni($workingDirectory)
        if (-not $script:D2NativeApi.CreateProcessW.Invoke($application, $commandLine, [IntPtr]::Zero, [IntPtr]::Zero, $false, [uint32]0x01080004, [IntPtr]::Zero, $currentDirectory, $startup, $processInfo)) { throw 'CreateProcessW with atomic Job assignment failed' }
        $process = [Runtime.InteropServices.Marshal]::ReadIntPtr($processInfo, 0); $thread = [Runtime.InteropServices.Marshal]::ReadIntPtr($processInfo, [IntPtr]::Size)
        $childPid = [Runtime.InteropServices.Marshal]::ReadInt32($processInfo, [IntPtr]::Size * 2)
        $assigned = $true
        $membership = [Runtime.InteropServices.Marshal]::AllocHGlobal(4)
        try {
            [Runtime.InteropServices.Marshal]::WriteInt32($membership, 0)
            if (-not $script:D2NativeApi.IsProcessInJob.Invoke($process, $job, $membership) -or [Runtime.InteropServices.Marshal]::ReadInt32($membership) -eq 0) { throw 'Provisioner Job membership verification failed' }
        } finally { [Runtime.InteropServices.Marshal]::FreeHGlobal($membership) }
        $resumeResult = $script:D2NativeApi.ResumeThread.Invoke($thread)
        if ($resumeResult -ne 1) { $nativeError = $script:D2NativeApi.GetLastError.Invoke(); throw "ResumeThread did not release the single suspended provisioner thread: result=$resumeResult error=$nativeError" }; $resumed = $true
        Close-D2NativeHandle $thread; $thread = [IntPtr]::Zero
        return @{ job = $job; process = $process; pid = $childPid }
    } catch {
        if ($process -ne [IntPtr]::Zero) {
            [void]$script:D2NativeApi.TerminateProcess.Invoke($process, [uint32]3759264256)
            [void]$script:D2NativeApi.WaitForSingleObject.Invoke($process, [uint32]30000)
        }
        if ($assigned -and $job -ne [IntPtr]::Zero) { [void]$script:D2NativeApi.TerminateJobObject.Invoke($job, [uint32]3759264257) }
        Close-D2NativeHandle $thread; Close-D2NativeHandle $process; Close-D2NativeHandle $job
        throw
    } finally {
        if ($attributeList -ne [IntPtr]::Zero) { $script:D2NativeApi.DeleteProcThreadAttributeList.Invoke($attributeList) }
        foreach ($buffer in @($jobInfo, $queryInfo, $startup, $processInfo, $attributeSize, $attributeList, $jobAttribute, $application, $commandLine, $currentDirectory)) { if ($buffer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::FreeHGlobal($buffer) } }
    }
}
function Wait-ContainedProcess([hashtable]$contained) {
    try {
        if ($script:D2NativeApi.WaitForSingleObject.Invoke([IntPtr]$contained.process, [uint32]4294967295) -ne 0) { throw 'Provisioner wait failed' }
        $exitBuffer = [Runtime.InteropServices.Marshal]::AllocHGlobal(4)
        try {
            if (-not $script:D2NativeApi.GetExitCodeProcess.Invoke([IntPtr]$contained.process, $exitBuffer)) { throw 'GetExitCodeProcess failed' }
            return [Runtime.InteropServices.Marshal]::ReadInt32($exitBuffer)
        } finally { [Runtime.InteropServices.Marshal]::FreeHGlobal($exitBuffer) }
    } catch {
        [void]$script:D2NativeApi.TerminateJobObject.Invoke([IntPtr]$contained.job, [uint32]3759264258)
        throw
    } finally {
        Close-D2NativeHandle ([IntPtr]$contained.process); Close-D2NativeHandle ([IntPtr]$contained.job)
    }
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

# __D2_MAIN__
$applyConsumed = $false
$nativeExitCode = $null
$phase = 'PRE_APPLY'
$terminalPublicationAttempted = $false
$baselinePath = [IO.Path]::Combine($StagingPath, 'terminal-baseline.json')
$latchPath = [IO.Path]::Combine($StagingPath, 'apply.latch')
$terminalPath = [IO.Path]::Combine($StagingPath, 'terminal-evidence.json')
$indexPath = [IO.Path]::Combine($StagingPath, 'terminal-authority-index.json')
try {
    $authorityCreated = [DateTime]::Parse($Authority.created_utc).ToUniversalTime()
    $authorityExpires = [DateTime]::Parse($Authority.expires_utc).ToUniversalTime()
    if ([DateTime]::UtcNow -lt $authorityCreated -or [DateTime]::UtcNow -gt $authorityExpires) { throw 'D2 authority is not active before apply' }
    Assert-EqualValue ([Environment]::MachineName) ([string]$Authority.machine_name) 'Machine identity'; Assert-EqualValue ([IO.Path]::GetFullPath([string]$Authority.target_root)) ([string]$Authority.target_root) 'Production target'
    Assert-Hash $ProtectedPayloadPath ([string]$Authority.payload_sha256) 'Protected payload'; Assert-Hash $ProtectedRuntimeArchive ([string]$Authority.runtime_sha256) 'Protected runtime archive'; Assert-Hash $ProtectedBundle ([string]$Authority.bundle_sha256) 'Protected deployment bundle'
    $runtime = [IO.Path]::Combine($StagingPath, 'runtime'); Set-ProtectedDirectory $runtime (Get-RoleSddl ([string]$Authority.service_sid) 'runtime')
    $runtimeFiles = Expand-SafeZip $ProtectedRuntimeArchive $runtime
    if (-not $runtimeFiles.ContainsKey('python.exe') -or -not $runtimeFiles.ContainsKey('python314.zip')) { throw 'Private runtime archive layout is incomplete' }
    Assert-ExactFiles $runtime $runtimeFiles 'Private runtime archive'
    $app = [IO.Path]::Combine($runtime, 'app'); Set-ProtectedDirectory $app (Get-RoleSddl ([string]$Authority.service_sid) 'runtime'); $bundleFiles = Expand-SafeZip $ProtectedBundle $app; Assert-BundleManifest $app $bundleFiles
    $pth = ".`r`npython314.zip`r`napp`r`n"; $pthPath = [IO.Path]::Combine($runtime, 'python314._pth'); [IO.File]::WriteAllText($pthPath, $pth, [Text.UTF8Encoding]::new($false)); $runtimeFiles['python314._pth'] = ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.UTF8Encoding]::new($false).GetBytes($pth)))).Replace('-', '').ToLowerInvariant()
    foreach ($name in $bundleFiles.Keys) { $runtimeFiles['app/' + $name] = $bundleFiles[$name] }; Assert-ExactFiles $runtime $runtimeFiles 'Final private runtime'
    if ([DateTime]::UtcNow -lt $authorityCreated -or [DateTime]::UtcNow -gt $authorityExpires) { throw 'D2 authority is not active before irreversible apply' }
    $phase = 'APPLY_BASELINE'
    Publish-TerminalEvidence $baselinePath 'INDETERMINATE' 'APPLY_LATCH_PENDING' $null 'APPLY_NOT_TERMINALLY_COMMITTED' 'No terminal commit index exists yet'
    $baselineSha256 = Get-BytesSha256 (Read-EvidenceBytes $baselinePath)
    $phase = 'APPLY_LATCH'
    Set-OneShotLatch $StagingPath $baselineSha256
    $applyConsumed = $true
    $python = [IO.Path]::Combine($runtime, 'python.exe'); if (-not [IO.File]::Exists($python)) { throw 'Private Python executable is absent' }
    $argv = @('-B', '-m', 'packages.deployment.provisioning', '--target-root', [string]$Authority.target_root, '--service-account', [string]$Authority.service_account, '--roles', 'releases', 'runtime', 'staging', '--apply')
    $unsafeArgument = $false; foreach ($argument in $argv) { if ($argument -match '[\s"]') { $unsafeArgument = $true } }; if ($unsafeArgument) { throw 'Frozen provisioner argv contains unsupported whitespace or quotes' }
    $phase = 'PROVISIONER_START'
    $contained = Start-ContainedProcess $python ([string]::Join(' ', $argv)) $runtime
    $phase = 'PROVISIONER_WAIT'
    $nativeExitCode = Wait-ContainedProcess $contained
    $phase = 'NATIVE_EXIT_PUBLICATION'
    Publish-NativeExitEvidence $StagingPath $nativeExitCode
    $phase = 'PROVISIONER_RESULT'
    if ($nativeExitCode -ne 0) { throw "Provisioner failed with native exit code $nativeExitCode; retry is forbidden" }
    $phase = 'POSTSTATE'
    Assert-PostState ([string]$Authority.target_root) @('releases', 'runtime', 'staging')
    $phase = 'TERMINAL_SUCCESS'
    $terminalPublicationAttempted = $true
    Publish-AuthoritativeTerminalEvidence $baselinePath $latchPath $terminalPath $indexPath 'SUCCESS' $phase $nativeExitCode 'NONE' ''
} catch {
    $failure = $_
    if ($applyConsumed) {
        if (-not $terminalPublicationAttempted) {
            $classification = Get-TerminalFailureClassification $phase $nativeExitCode
            $status = [string]$classification.status; $failureCode = [string]$classification.failure_code
            $terminalPublicationAttempted = $true
            try {
                Publish-AuthoritativeTerminalEvidence $baselinePath $latchPath $terminalPath $indexPath $status $phase $nativeExitCode $failureCode $failure.Exception.Message
            } catch {}
        }
    }
    throw $failure
}
