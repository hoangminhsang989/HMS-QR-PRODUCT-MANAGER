$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell

foreach ($entry in @(
    @{ Name = 'HMS QR Desktop'; Script = 'toggle-hms-qr-desktop.ps1'; Icon = 167 },
    @{ Name = 'HMS QR Server'; Script = 'toggle-hms-qr-server.ps1'; Icon = 13 }
)) {
    $shortcut = $shell.CreateShortcut((Join-Path $desktop ($entry.Name + '.lnk')))
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot $entry.Script) + '"'
    $shortcut.WorkingDirectory = $repoRoot
    $shortcut.Description = 'Bấm để bật/tắt ' + $entry.Name
    $shortcut.IconLocation = (Join-Path $env:SystemRoot 'System32\shell32.dll') + ',' + $entry.Icon
    $shortcut.Save()
}

Write-Output "Đã tạo hai nút Desktop trong $desktop"
