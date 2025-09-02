param(
    [string]$cert, # public cert
    [string]$binary # binary to sign
)

# Sign the target.
# The corresponding private key must reside in the OS certificate store.
# THIS SCRIPT IS MEANT TO BE USED ONLY FOR LOCAL TEST BUILDS.

$ErrorActionPreference = 'Stop'

$ts_url = "http://timestamp.digicert.com"

if ($env:EWDK_PATH -eq $null) {
    Write-Error "[!] EWDK_PATH variable not set"
}

if ($env:EnterpriseWDK -eq $null) {
    Write-Error "[!] EWDK environment not initialized"
}

$signtool = "$env:EWDK_PATH\Program Files\Windows Kits\10\bin\$env:Version_Number\x64\signtool.exe"
if (! (Test-Path $signtool)) {
    Write-Error "[!] $signtool not found"
    break
}

$cert_path = Resolve-Path $cert
if (! (Test-Path $cert_path)) {
    Write-Error "[!] $cert_path not found"
    exit 1
}
$sha1 = (Get-FileHash $cert_path -Algorithm SHA1).Hash

$target = Resolve-Path $binary

Start-Process -FilePath $signtool -Wait -NoNewWindow -ArgumentList "sign /sha1 $sha1 /fd sha256 /td sha256 /tr $ts_url $target"
