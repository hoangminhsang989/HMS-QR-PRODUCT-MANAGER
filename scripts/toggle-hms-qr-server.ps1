$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$dataRoot = 'D:\HMS-QR-PROD'
$python = (py -3.14 -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()

if (-not $python -or -not (Test-Path -LiteralPath $python)) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show('Cần cài Python 3.14 x64 để chạy HMS QR Server.', 'HMS QR Server') | Out-Null
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $dataRoot 'server-tool-secrets.json'))) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show('Chưa tìm thấy cấu hình Server tại D:\HMS-QR-PROD. Hãy hoàn tất thiết lập bằng Server Tool trước.', 'HMS QR Server') | Out-Null
    exit 1
}

$env:PYTHONPATH = $repoRoot
$env:PYTHONDONTWRITEBYTECODE = '1'
Start-Process -FilePath $python -ArgumentList '-m','apps.server.tool' -WorkingDirectory $repoRoot
