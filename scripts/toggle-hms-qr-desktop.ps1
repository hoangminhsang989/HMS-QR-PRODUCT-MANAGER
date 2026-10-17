$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = (py -3.14 -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
if (-not $python -or -not (Test-Path -LiteralPath $python)) {
    [System.Windows.Forms.MessageBox]::Show('Cần cài Python 3.14 x64 để chạy HMS QR Desktop.', 'HMS QR Desktop') | Out-Null
    exit 1
}

$matches = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match '(?:^|\s)-m\s+apps\.desktop(?:\s|$)'
})
if ($matches.Count -gt 0) {
    foreach ($process in $matches) { Stop-Process -Id $process.ProcessId -Force }
    exit 0
}

Start-Process -FilePath $python -ArgumentList '-m','apps.desktop' -WorkingDirectory $repoRoot
