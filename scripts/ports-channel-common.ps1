Set-StrictMode -Version Latest

function Get-PortsChannelHash([string]$Path) {
    # PS5 can inherit a PS7 module search path where Get-FileHash is unavailable.
    # Hash with the built-in runtime, independent of optional script modules.
    $algorithm=[Security.Cryptography.SHA256]::Create()
    $stream=$null
    try {
        $stream=[IO.File]::OpenRead($Path)
        return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant()
    } finally {
        if ($stream) { $stream.Dispose() }
        $algorithm.Dispose()
    }
}
function Get-PortsChannelTextHash([string]$Text) {
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes($Text))).Replace('-','').ToLowerInvariant() }
    finally { $algorithm.Dispose() }
}
function Read-PortsChannelUtf8([string]$Path) {
    return [Text.UTF8Encoding]::new($false,$true).GetString([IO.File]::ReadAllBytes($Path))
}
function Resolve-PortsChannelPath([string]$Path) {
    if (-not $Path -or $Path -match '[\x00-\x1f]' -or $Path -match '[<>"|?*]') { throw 'A valid local Windows path is required.' }
    if (($Path -replace '\A[A-Za-z]:','').Contains(':')) { throw 'Alternate data streams are not channel paths.' }
    foreach ($part in ($Path -split '[\\/]')) {
        if ($part -eq '..' -or $part -match '[. ]$') { throw 'Path traversal and trailing dot/space aliases are not allowed.' }
    }
    $full=[IO.Path]::GetFullPath($Path).TrimEnd('\','/')
    if ($full -notmatch '\A[A-Za-z]:\\.+') { throw 'Use a directory on a local Windows drive, not a drive root or network path.' }
    $drive=[IO.Path]::GetPathRoot($full)
    $parts=$full.Substring($drive.Length) -split '\\'
    $resolved=$drive; $missing=$false
    if ([IO.File]::GetAttributes($resolved) -band [IO.FileAttributes]::ReparsePoint) { throw 'Channel paths must not traverse reparse points.' }
    foreach ($part in $parts) {
        $entry=$null
        if (-not $missing) {
            # A literal Windows directory search matches an existing 8.3 alias
            # but returns the stored long name. Resolve each ancestor before
            # appending a nonexistent suffix, without loading a native helper.
            $iterator=[IO.Directory]::EnumerateFileSystemEntries($resolved,$part).GetEnumerator()
            try {
                if ($iterator.MoveNext()) { $entry=$iterator.Current }
                if ($iterator.MoveNext()) { throw 'Ambiguous channel path component.' }
            } finally { $iterator.Dispose() }
        }
        if ($null -ne $entry) {
            $resolved=$entry
            if ([IO.File]::GetAttributes($resolved) -band [IO.FileAttributes]::ReparsePoint) { throw 'Channel paths must not traverse reparse points.' }
        } else {
            $missing=$true
            $resolved=[IO.Path]::Combine($resolved,$part)
        }
    }
    return $resolved
}
function Test-PortsChannelOverlap([string]$Left,[string]$Right) {
    return $Left.Equals($Right,[StringComparison]::OrdinalIgnoreCase) -or
        $Left.StartsWith($Right+'\',[StringComparison]::OrdinalIgnoreCase) -or
        $Right.StartsWith($Left+'\',[StringComparison]::OrdinalIgnoreCase)
}
function ConvertTo-PortsChannelArgument([string]$Value) {
    $text=[Text.StringBuilder]::new(); [void]$text.Append('"'); $slashes=0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') { $slashes++; continue }
        if ($character -eq '"') { [void]$text.Append(('\' * ($slashes * 2 + 1))) }
        else { [void]$text.Append(('\' * $slashes)) }
        $slashes=0; [void]$text.Append($character)
    }
    [void]$text.Append(('\' * ($slashes * 2))); [void]$text.Append('"')
    return $text.ToString()
}
function Invoke-PortsChannelMetadata([string]$Executable,[string[]]$Arguments,[int]$TimeoutMs=30000) {
    # Only the verified --version/import CLI uses this runner; never a TUI/daemon.
    $start=[Diagnostics.ProcessStartInfo]::new()
    $start.FileName=$Executable
    $start.Arguments=(($Arguments | ForEach-Object { ConvertTo-PortsChannelArgument $_ }) -join ' ')
    $start.UseShellExecute=$false; $start.CreateNoWindow=$true
    $start.RedirectStandardOutput=$true; $start.RedirectStandardError=$true
    $start.RedirectStandardInput=$true
    $start.StandardOutputEncoding=[Text.UTF8Encoding]::new($false)
    $start.StandardErrorEncoding=[Text.UTF8Encoding]::new($false)
    $process=[Diagnostics.Process]::new(); $process.StartInfo=$start; $started=$false
    try {
        if (-not $process.Start()) { throw 'The owned metadata command could not start.' }
        $started=$true
        $process.StandardInput.Close()
        $stdout=$process.StandardOutput.ReadToEndAsync(); $stderr=$process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutMs)) {
            try { $process.Kill() } catch { }
            if (-not $process.WaitForExit(3000)) { throw "Metadata command timed out; owned PID $($process.Id) has not confirmed exit." }
            throw 'Metadata command timed out; the owned child exited. Inspect the beta destination before retrying.'
        }
        if (-not $stdout.Wait(1000) -or -not $stderr.Wait(1000)) { throw 'Metadata output did not close after child exit.' }
        if ($process.ExitCode -ne 0) { throw "Metadata command failed ($($process.ExitCode)): $($stderr.Result) $($stdout.Result)" }
        return $stdout.Result
    } finally {
        try {
            if ($started -and -not $process.HasExited) {
                try { $process.Kill() } catch { }
                if (-not $process.WaitForExit(3000)) { throw "Owned metadata PID $($process.Id) has not confirmed exit; retain its fixture for inspection." }
            }
        } finally { $process.Dispose() }
    }
}
function Get-PortsChannelDownload([string]$Url,[string]$Destination) {
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Destination -TimeoutSec 60 -ErrorAction Stop
}
function Assert-PortsChannelKeys($Value,[string[]]$Names) {
    if ($null -eq $Value -or $Value -isnot [pscustomobject]) { throw 'Expected a channel contract object.' }
    $actual=@($Value.PSObject.Properties.Name)
    if ($actual.Count -ne $Names.Count -or @($actual | Where-Object { $_ -cnotin $Names }).Count) { throw 'Unexpected channel contract fields.' }
}
function Read-PortsChannelContract([string]$Path) {
    $contract=[IO.File]::ReadAllText($Path) | ConvertFrom-Json
    Assert-PortsChannelKeys $contract @('schema_version','app','stable','beta')
    Assert-PortsChannelKeys $contract.stable @('workspace_version','version','source_commit','binary_sha256')
    Assert-PortsChannelKeys $contract.beta @('version','tag','qualification','source_commit','installer_sha256','archive_sha256','binary_sha256','release_record_sha256')
    if ($contract.schema_version -ne 1 -or $contract.app -cne 'ports' -or
        $contract.stable.workspace_version -cne '0.10.0' -or $contract.stable.version -cne '0.9.1' -or
        $contract.stable.source_commit -cnotmatch '\A[a-f0-9]{40}\z' -or $contract.stable.binary_sha256 -cnotmatch '\A[a-f0-9]{64}\z' -or
        $contract.beta.version -cnotmatch '\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-beta\.[1-9][0-9]*\z' -or
        $contract.beta.tag -cne ('v'+$contract.beta.version) -or $contract.beta.qualification -cnotin @('pending','qualified')) { throw 'Invalid channel contract identity.' }
    foreach ($name in @('source_commit','installer_sha256','archive_sha256','binary_sha256','release_record_sha256')) {
        $value=$contract.beta.$name
        if ($contract.beta.qualification -eq 'pending') {
            if ($null -ne $value) { throw 'A pending beta must not contain release identity claims.' }
        } elseif ($value -isnot [string] -or $value -cnotmatch $(if ($name -eq 'source_commit') { '\A[a-f0-9]{40}\z' } else { '\A[a-f0-9]{64}\z' })) {
            throw 'A qualified beta requires exact source and asset hashes.'
        }
    }
    return $contract
}
function Assert-PortsChannelBinary([string]$InstallDir,$Beta) {
    $marker=Resolve-PortsChannelPath (Join-Path $InstallDir '.ports-installer')
    $binary=Resolve-PortsChannelPath (Join-Path $InstallDir 'bin\ports-beta.exe')
    $version=Resolve-PortsChannelPath (Join-Path $InstallDir 'version')
    if ([IO.File]::ReadAllText($marker).Trim() -cne 'port-forward-tui-beta' -or
        [IO.File]::ReadAllText($version).Trim() -cne $Beta.version -or
        (Get-PortsChannelHash $binary) -cne $Beta.binary_sha256) { throw 'Installed beta ownership, version or binary hash does not match the qualified contract.' }
    return $binary
}
function Update-PortsChannelProfile([string]$Directory,[string]$Command,[string]$Action) {
    $directory=Resolve-PortsChannelPath $Directory
    $fragment=Join-Path $directory 'ports-beta.json'
    $owner=Join-Path $directory '.workspace-owner'
    foreach ($path in @($fragment,$owner,(Join-Path $directory '.operation.lock'))) { [void](Resolve-PortsChannelPath $path) }
    $guid='{a0a5a34a-f486-4ca7-9471-54c66d7a697b}'
    $text=(@{profiles=@(@{guid=$guid;name='Ports (BETA)';tabTitle='Ports BETA';commandline=$Command;hidden=$false})} | ConvertTo-Json -Depth 5)+"`n"
    $digest=Get-PortsChannelTextHash $text
    $marker='terminal-workspace-ports-beta-v1 '+$digest+"`n"
    $existingFragment=if ([IO.File]::Exists($fragment)) { Read-PortsChannelUtf8 $fragment } else { $null }
    $existingOwner=if ([IO.File]::Exists($owner)) { Read-PortsChannelUtf8 $owner } else { $null }
    if (($null -eq $existingFragment) -ne ($null -eq $existingOwner)) { throw 'Incomplete profile ownership; retain files for inspection.' }
    if ($null -ne $existingFragment) {
        if ($existingOwner -cne ('terminal-workspace-ports-beta-v1 '+(Get-PortsChannelHash $fragment)+"`n")) { throw 'The beta fragment was changed outside this helper; retain it for inspection.' }
        $parsed=$existingFragment | ConvertFrom-Json
        if (@($parsed.profiles).Count -ne 1 -or $parsed.profiles[0].guid -cne $guid) { throw 'The existing fragment does not have the owned profile identity.' }
    } elseif (Test-Path -LiteralPath $directory) {
        if (@(Get-ChildItem -LiteralPath $directory -Force).Count) { throw 'Choose the empty owned fragment directory; unknown files were retained.' }
    }
    if ($Action -eq 'RemoveProfile' -and $null -eq $existingFragment) { return 'absent' }
    if ($Action -eq 'AddProfile' -and $null -ne $existingFragment) {
        # PS5 and PS7 serialize the same JSON with different whitespace/escaping.
        # Ownership still checks the exact existing bytes; idempotence compares
        # the five generated values and retains those bytes without rewriting.
        Assert-PortsChannelKeys $parsed @('profiles')
        if ($parsed.profiles -isnot [array]) { throw 'The owned profile list must be an array.' }
        $profile=$parsed.profiles[0]
        Assert-PortsChannelKeys $profile @('guid','name','tabTitle','commandline','hidden')
        foreach ($key in @('guid','name','tabTitle','commandline')) {
            if ($profile.$key -isnot [string]) { throw 'The owned profile values must be strings.' }
        }
        if ($profile.guid -cne $guid -or $profile.name -cne 'Ports (BETA)' -or
            $profile.tabTitle -cne 'Ports BETA' -or $profile.commandline -cne $Command -or
            $profile.hidden -isnot [bool] -or $profile.hidden) { throw 'The owned profile uses different paths or values. Remove it explicitly before adding new paths.' }
    }
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $lock=$null
    try {
        $lock=[IO.File]::Open((Join-Path $directory '.operation.lock'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        $currentFragment=if ([IO.File]::Exists($fragment)) { Read-PortsChannelUtf8 $fragment } else { $null }
        $currentOwner=if ([IO.File]::Exists($owner)) { Read-PortsChannelUtf8 $owner } else { $null }
        if ($currentFragment -cne $existingFragment -or $currentOwner -cne $existingOwner) { throw 'Profile changed during preparation; no update was applied.' }
        if ($Action -eq 'RemoveProfile') {
            [IO.File]::Delete($fragment); [IO.File]::Delete($owner)
            return 'removed'
        }
        if ($null -ne $existingFragment) { return 'unchanged' }
        $utf8=[Text.UTF8Encoding]::new($false)
        $stage=Join-Path $directory ('.profile-'+[Guid]::NewGuid().ToString('N'))
        try {
            [IO.File]::WriteAllText($stage,$text,$utf8)
            # Publish without replacing an existing file. Owner is written last;
            # interruption leaves an inspect-only partial state, never guessed ownership.
            [IO.File]::Move($stage,$fragment)
            try {
                $stream=[IO.File]::Open($owner,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
                try { $bytes=$utf8.GetBytes($marker); $stream.Write($bytes,0,$bytes.Length); $stream.Flush() } finally { $stream.Dispose() }
            } catch {
                if ((Read-PortsChannelUtf8 $fragment) -ceq $text) { [IO.File]::Delete($fragment) }
                throw
            }
        } finally { if ([IO.File]::Exists($stage)) { [IO.File]::Delete($stage) } }
        if ((Read-PortsChannelUtf8 $fragment) -cne $text -or (Read-PortsChannelUtf8 $owner) -cne $marker) { throw 'Fragment readback failed; inspect the owned files.' }
        return 'added'
    } finally {
        if ($lock) { $lock.Dispose(); [IO.File]::Delete((Join-Path $directory '.operation.lock')) }
    }
}
