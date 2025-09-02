function QB-GenerateVersionHeader {
    param(
        [Parameter(Mandatory)] [string]$in,
        [Parameter(Mandatory)] [string]$out
    )
    $version = Get-Content $in
    # qubes version has 3 parts, windows needs 4
    $version += ".0"
    $version_str = "`"" + $version + "`""
    $version = %{$version -replace "\.", ","}
    $hdr = "#define QWT_FILEVERSION " + $version + "`n"
    $hdr += "#define QWT_FILEVERSION_STR " + $version_str + "`n"
    $hdr += "#define QWT_PRODUCTVERSION QWT_FILEVERSION`n"
    $hdr += "#define QWT_PRODUCTVERSION_STR QWT_FILEVERSION_STR`n"
    Set-Content -Path $out $hdr
}

QB-GenerateVersionHeader $args[0] $args[1]
