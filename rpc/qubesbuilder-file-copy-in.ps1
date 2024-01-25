class DecodeError : Exception {}

function Decode {
    param (
        [string]$part
    )

    if ($part -notmatch '^[a-zA-Z0-9._-]*$') {
        throw [DecodeError]'illegal characters found'
    }

    $ESCAPE_RE = [regex]::new('(--)|-([A-F0-9]{2})')

    # Check if no '-' remains outside of legal escape sequences.
    if ($part -contains ($ESCAPE_RE -replace '--|-([A-F0-9]{2})')) {
        throw [DecodeError]"'-' can be used only in '-HH' or '--'"
    }

    $decodedPart = $ESCAPE_RE.Replace($part, {
        param($m)
        if ($m.Groups[1].Success) {
            return '-'
        } else {
            $num = [Convert]::ToInt32($m.Groups[2].Value, 16)
            return [System.Text.Encoding]::ASCII.GetString($num)
        }
    })

    return $decodedPart
}


try {
    $decodedPart = Decode $args[0]

    # Get destination path and extract components
    $dstLeaf = Split-Path $decodedPart -Leaf
    $dstPath = Split-Path $decodedPart -Parent

    # Get user and group ID
    #$uid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    #$gid = [System.Security.Principal.WindowsIdentity]::GetCurrent().Groups[0].Value

    # Remove directory and ignore errors
    Remove-Item -Path "Q:\builder\incoming" -Recurse -ErrorAction SilentlyContinue

    # Recreate directory
    New-Item -ItemType Directory -Path "Q:\builder\incoming" | Out-Null

    $fileReceiver = $env:QUBES_TOOLS + "qubes-rpc-services\file-receiver.exe"
    Start-Process -FilePath $fileReceiver -ArgumentList "Q:\builder\incoming" -LoadUserProfile -NoNewWindow -Wait

    # Create destination directory
    New-Item -ItemType Directory -Path $dstPath -Force | Out-Null

    # Move incoming content to the destination directory
    $incomingPath = Join-Path "Q:\builder\incoming" $dstLeaf
    Move-Item -Force $incomingPath $dstPath
} catch [DecodeError] {
    Write-Output $_.Exception.Message
}
