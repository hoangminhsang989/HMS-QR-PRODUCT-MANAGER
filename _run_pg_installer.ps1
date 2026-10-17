param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$OptionFile,
    [Parameter(Mandatory=$true)][string]$StatusFile
)
$code = 1
try {
    & $Installer --optionfile $OptionFile
    $code = $LASTEXITCODE
} catch {
    $_ | Out-String | Write-Error
    $code = 1
} finally {
    Set-Content -LiteralPath $StatusFile -Value $code -Encoding ascii
}
exit $code
