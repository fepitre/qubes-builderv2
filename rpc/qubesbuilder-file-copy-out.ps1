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
    $fileSender = Join-Path $env:QUBES_TOOLS "qubes-rpc-services\file-sender.exe"
    Start-Process -FilePath $fileSender -ArgumentList "$decodedPart" -LoadUserProfile -NoNewWindow -Wait
} catch [DecodeError] {
    Write-Output $_.Exception.Message
}
