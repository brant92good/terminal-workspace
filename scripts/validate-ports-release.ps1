# Build-only leaf archive validation. No executable is launched by this helper.
function Expand-WorkspacePortsRelease {
    param([Parameter(Mandatory=$true)][string]$Bundle,[Parameter(Mandatory=$true)][string]$Destination)
    $ErrorActionPreference = 'Stop'
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Destination = [IO.Path]::GetFullPath($Destination)
    if (Test-Path -LiteralPath $Destination) { throw 'Ports extraction destination already exists.' }
    $payloads = @('ports.exe','PortsFocus.exe','TerminalViews.exe','LICENSE.txt','THIRD_PARTY_NOTICES.txt')
    $expected = $payloads + @('SHA256SUMS')
    $zip = [IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($Bundle))
    try {
        $seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
        foreach ($entry in $zip.Entries) {
            if ($expected -cnotcontains $entry.FullName -or -not $seen.Add($entry.FullName)) { throw "Unexpected or duplicate Ports archive entry: $($entry.FullName)" }
            $unixType = ($entry.ExternalAttributes -shr 16) -band 0xf000
            if ($unixType -notin @(0,0x8000) -or ($entry.ExternalAttributes -band 0x410) -ne 0 -or $entry.Length -gt 67108864) { throw "Ports archive entry is not an ordinary bounded file: $($entry.FullName)" }
        }
        if ($seen.Count -ne $expected.Count) { throw 'Ports archive lacks a required payload or checksum index.' }
        $index = $zip.GetEntry('SHA256SUMS')
        if ($index.Length -gt 4096) { throw 'Ports checksum index is oversized.' }
        $reader = New-Object IO.StreamReader($index.Open())
        try { $lines = $reader.ReadToEnd().Replace("`r`n","`n").TrimEnd("`n") -split "`n" } finally { $reader.Dispose() }
        $hashes = New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
        foreach ($line in $lines) {
            if ($line -cnotmatch '^([a-f0-9]{64})  ([A-Za-z0-9_.-]+)$' -or $payloads -cnotcontains $Matches[2] -or $hashes.ContainsKey($Matches[2])) { throw 'Ports checksum index has an invalid or duplicate entry.' }
            $hashes.Add($Matches[2],$Matches[1])
        }
        if ($hashes.Count -ne $payloads.Count) { throw 'Ports checksum index lacks a required payload.' }
        foreach ($name in $payloads) {
            $stream = $zip.GetEntry($name).Open()
            $hasher = [Security.Cryptography.SHA256]::Create()
            try { $actual = ([BitConverter]::ToString($hasher.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
            finally { $stream.Dispose(); $hasher.Dispose() }
            if ($actual -cne $hashes[$name]) { throw "Invalid Ports payload hash: $name" }
        }
        # Validation finishes before extracting even the first payload.
        if (Test-Path -LiteralPath $Destination) { throw 'Ports extraction destination appeared during validation.' }
        [IO.Directory]::CreateDirectory($Destination) | Out-Null
        foreach ($entry in $zip.Entries) { [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,(Join-Path $Destination $entry.FullName),$false) }
    } finally { $zip.Dispose() }
}
