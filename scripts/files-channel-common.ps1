Set-StrictMode -Version Latest

function Get-FilesChannelHash([string]$Path) {
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
function Get-FilesChannelTextHash([string]$Text) {
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes($Text))).Replace('-','').ToLowerInvariant() }
    finally { $algorithm.Dispose() }
}
function Read-FilesChannelUtf8([string]$Path) {
    return [Text.UTF8Encoding]::new($false,$true).GetString([IO.File]::ReadAllBytes($Path))
}
function Resolve-FilesChannelPath([string]$Path) {
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
function Test-FilesChannelOverlap([string]$Left,[string]$Right) {
    return $Left.Equals($Right,[StringComparison]::OrdinalIgnoreCase) -or
        $Left.StartsWith($Right+'\',[StringComparison]::OrdinalIgnoreCase) -or
        $Right.StartsWith($Left+'\',[StringComparison]::OrdinalIgnoreCase)
}
function ConvertTo-FilesChannelArgument([string]$Value) {
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

function Assert-FilesChannelKeys($Value,[string[]]$Names) {
    if ($null -eq $Value -or $Value -isnot [pscustomobject]) { throw 'Expected a Files contract object.' }
    $actual=@($Value.PSObject.Properties.Name)
    if ($actual.Count -ne $Names.Count -or @($actual | Where-Object { $_ -cnotin $Names }).Count) { throw 'Unexpected Files contract fields.' }
}
function Read-FilesChannelContract([string]$Path) {
    if (([IO.FileInfo]$Path).Length -gt 65536) { throw 'Oversized Files contract.' }
    $value=(Read-FilesChannelUtf8 $Path) | ConvertFrom-Json
    Assert-FilesChannelKeys $value @('schema_version','app','stable','beta')
    Assert-FilesChannelKeys $value.stable @('workspace_version','version','binary_sha256','selector_version','selector_sha256')
    Assert-FilesChannelKeys $value.beta @('version','tag','qualification','source_commit','installer_sha256','binary_sha256','sidecar_sha256','release_record_sha256')
    if ($value.schema_version -ne 1 -or $value.app -cne 'ssh-files' -or $value.stable.workspace_version -cne '0.10.0' -or
        $value.stable.version -cne '0.3.0' -or $value.stable.selector_version -cne '0.8.0' -or
        $value.stable.binary_sha256 -cnotmatch '\A[a-f0-9]{64}\z' -or $value.stable.selector_sha256 -cnotmatch '\A[a-f0-9]{64}\z' -or
        $value.beta.version -cnotmatch '\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-beta\.[1-9][0-9]*\z' -or
        $value.beta.tag -cne ('v'+$value.beta.version) -or $value.beta.qualification -cnotin @('pending','qualified')) { throw 'Invalid Files contract identity.' }
    foreach ($field in @('source_commit','installer_sha256','binary_sha256','sidecar_sha256','release_record_sha256')) {
        $item=$value.beta.$field
        if ($value.beta.qualification -eq 'pending') {
            if ($null -ne $item) { throw 'Pending Files release hashes must remain null.' }
        } elseif ($item -isnot [string] -or $item -cnotmatch $(if ($field -eq 'source_commit') {'\A[a-f0-9]{40}\z'} else {'\A[a-f0-9]{64}\z'})) {
            throw 'Qualified Files release requires exact source and hashes.'
        }
    }
    return $value
}
function Assert-FilesChannelBinary([string]$Directory,$Beta) {
    $marker=Resolve-FilesChannelPath (Join-Path $Directory '.ssh-files-beta-installer')
    $binary=Resolve-FilesChannelPath (Join-Path $Directory 'bin\ssh-files-beta.exe')
    $version=Resolve-FilesChannelPath (Join-Path $Directory 'version')
    if ([IO.File]::ReadAllText($marker) -cne "ssh-files-beta`n" -or [IO.File]::ReadAllText($version) -cne ($Beta.version+"`n") -or
        (Get-FilesChannelHash $binary) -cne $Beta.binary_sha256) { throw 'Installed Files beta ownership, version or digest mismatch.' }
    return $binary
}
function Get-FilesChannelDownload([string]$Url,[string]$Destination) {
    $previous=[Net.ServicePointManager]::SecurityProtocol
    try {
        [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Destination -TimeoutSec 60 -ErrorAction Stop
    } finally { [Net.ServicePointManager]::SecurityProtocol=$previous }
}
function Start-FilesChannelChooser([string]$Selector,[string]$Binary,[string]$Catalog,[string]$StateDir,[string]$LocalDirectory) {
    $arguments=@('--catalog',$Catalog)
    if ($StateDir) { $arguments+=@('--state-dir',$StateDir) }
    $arguments+='files'
    $start=[Diagnostics.ProcessStartInfo]::new()
    $start.FileName=$Selector
    $start.Arguments=(($arguments | ForEach-Object { ConvertTo-FilesChannelArgument $_ }) -join ' ')
    $start.WorkingDirectory=$LocalDirectory
    $start.UseShellExecute=$false
    # Inherit the existing terminal. Never capture a TUI's input/output or set
    # the parent process/user/machine environment for this optional launch.
    $start.EnvironmentVariables['SSH_FILES_BIN']=$Binary
    $process=[Diagnostics.Process]::new(); $process.StartInfo=$start
    try {
        if (-not $process.Start()) { throw 'Could not start the Files chooser.' }
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) { throw "Files chooser failed (exit $($process.ExitCode)); no fallback was attempted." }
    } finally { $process.Dispose() }
}
function Update-FilesChannelProfile([string]$Directory,[string]$Command,[string]$LocalDirectory,[string]$Action) {
    $directory=Resolve-FilesChannelPath $Directory
    $fragment=Join-Path $directory 'files-beta.json'; $owner=Join-Path $directory '.workspace-owner'
    foreach ($path in @($fragment,$owner,(Join-Path $directory '.operation.lock'))) { [void](Resolve-FilesChannelPath $path) }
    $guid='{9bec2de7-dd77-41cb-bd5f-e02a2a19083f}'
    $text=(@{profiles=@(@{guid=$guid;name='Files (BETA)';tabTitle='Files BETA';commandline=$Command;startingDirectory=$LocalDirectory;hidden=$false})} | ConvertTo-Json -Depth 5)+"`n"
    $marker='terminal-workspace-files-beta-v1 '+(Get-FilesChannelTextHash $text)+"`n"
    $existing=if ([IO.File]::Exists($fragment)) { Read-FilesChannelUtf8 $fragment } else { $null }
    $previousOwner=if ([IO.File]::Exists($owner)) { Read-FilesChannelUtf8 $owner } else { $null }
    if (($null -eq $existing) -ne ($null -eq $previousOwner)) { throw 'Incomplete Files profile ownership; retain files for inspection.' }
    if ($null -ne $existing) {
        if ($previousOwner -cne ('terminal-workspace-files-beta-v1 '+(Get-FilesChannelHash $fragment)+"`n")) { throw 'Files profile changed outside this helper; retain it for inspection.' }
        $parsed=$existing | ConvertFrom-Json
        Assert-FilesChannelKeys $parsed @('profiles')
        if ($parsed.profiles -isnot [array] -or $parsed.profiles.Count -ne 1) { throw 'Invalid owned Files profile list.' }
        $profile=$parsed.profiles[0]
        Assert-FilesChannelKeys $profile @('guid','name','tabTitle','commandline','startingDirectory','hidden')
        if ($profile.guid -cne $guid -or $profile.name -cne 'Files (BETA)' -or $profile.tabTitle -cne 'Files BETA' -or
            $profile.commandline -isnot [string] -or $profile.startingDirectory -isnot [string] -or $profile.hidden -isnot [bool] -or $profile.hidden) { throw 'Invalid owned Files profile identity.' }
        if ($Action -eq 'AddProfile' -and ($profile.commandline -cne $Command -or $profile.startingDirectory -cne $LocalDirectory)) { throw 'Owned profile uses different source or paths; remove it explicitly first.' }
    } elseif (Test-Path -LiteralPath $directory) {
        if (@(Get-ChildItem -LiteralPath $directory -Force).Count) { throw 'Unknown files in Files fragment directory; inspect before continuing.' }
    }
    if ($Action -eq 'RemoveProfile' -and $null -eq $existing) { return 'absent' }
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $lock=$null
    try {
        $lock=[IO.File]::Open((Join-Path $directory '.operation.lock'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        $current=if ([IO.File]::Exists($fragment)) { Read-FilesChannelUtf8 $fragment } else { $null }
        $currentOwner=if ([IO.File]::Exists($owner)) { Read-FilesChannelUtf8 $owner } else { $null }
        if ($current -cne $existing -or $currentOwner -cne $previousOwner) { throw 'Files fragment changed during preparation.' }
        if ($Action -eq 'RemoveProfile') { [IO.File]::Delete($fragment); [IO.File]::Delete($owner); return 'removed' }
        if ($null -ne $existing) { return 'unchanged' }
        $stage=Join-Path $directory ('.profile-'+[Guid]::NewGuid().ToString('N'))
        try {
            [IO.File]::WriteAllText($stage,$text,[Text.UTF8Encoding]::new($false))
            [IO.File]::Move($stage,$fragment)
            try {
                $stream=[IO.File]::Open($owner,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
                try { $bytes=[Text.UTF8Encoding]::new($false).GetBytes($marker); $stream.Write($bytes,0,$bytes.Length); $stream.Flush() } finally { $stream.Dispose() }
            } catch {
                if ((Read-FilesChannelUtf8 $fragment) -ceq $text) { [IO.File]::Delete($fragment) }
                throw
            }
        } finally { if ([IO.File]::Exists($stage)) { [IO.File]::Delete($stage) } }
        if ((Read-FilesChannelUtf8 $fragment) -cne $text -or (Read-FilesChannelUtf8 $owner) -cne $marker) { throw 'Files profile readback failed; inspect the owned files.' }
        return 'added'
    } finally { if ($lock) { $lock.Dispose(); [IO.File]::Delete((Join-Path $directory '.operation.lock')) } }
}
