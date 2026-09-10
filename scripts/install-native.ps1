param(
    [string]$InstallDir = '', [string]$Version = '0.9.0',
    [string]$Bundle = '', [string]$Sha256 = '', [string]$LegacyInstallDir = '',
    [switch]$NoConfigure, [switch]$NoShortcuts, [switch]$SourceCheckout,
    [switch]$ExplorerPowerShell
)
$ErrorActionPreference = 'Stop'
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Terminal Workspace requires 64-bit Windows.' }
if ($Version -notmatch '^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$') { throw 'Invalid release version.' }
if (-not $InstallDir) { $InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\TerminalWorkspace' }
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
$workspaceMarker = Join-Path $InstallDir '.workspace-installer'
$workspaceMarkerValue = 'terminal-workspace-native-v1'
if (Test-Path -LiteralPath $workspaceMarker) {
    if ([IO.File]::ReadAllText($workspaceMarker).Trim() -ne $workspaceMarkerValue) { throw 'The destination is not a native Terminal Workspace installation.' }
} elseif (Test-Path -LiteralPath $InstallDir) {
    $workspaceOwnedCheckout = $SourceCheckout -and (Test-Path -LiteralPath (Join-Path $InstallDir '.git')) -and (Test-Path -LiteralPath (Join-Path $InstallDir 'Cargo.toml')) -and ([IO.File]::ReadAllText((Join-Path $InstallDir 'Cargo.toml')) -match 'name = "terminal-workspace"')
    if (@(Get-ChildItem -LiteralPath $InstallDir -Force).Count -and -not $workspaceOwnedCheckout) { throw 'Choose an empty directory or an existing native Terminal Workspace installation.' }
}
function Get-WorkspaceHash([string]$Path) {
    $workspaceHasher = [Security.Cryptography.SHA256]::Create()
    $workspaceInput = [IO.File]::OpenRead($Path)
    try { return ([BitConverter]::ToString($workspaceHasher.ComputeHash($workspaceInput))).Replace('-','').ToLowerInvariant() }
    finally { $workspaceInput.Dispose(); $workspaceHasher.Dispose() }
}
function Get-WorkspaceDownload([string]$Source,[string]$Destination) {
    if ($Source -match '^https://') {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $Source -OutFile $Destination
    } elseif (Test-Path -LiteralPath $Source -PathType Leaf) { [IO.File]::Copy([IO.Path]::GetFullPath($Source),$Destination) }
    else { throw 'Bundle must be an HTTPS URL or an existing local file.' }
}
function Assert-WorkspaceOrdinaryPath([string]$Path) {
    # Legacy metadata must not redirect reads through a junction or symlink.
    $workspaceInspect = [IO.Path]::GetFullPath($Path)
    while ($workspaceInspect) {
        if (Test-Path -LiteralPath $workspaceInspect) {
            $workspaceInfo = Get-Item -LiteralPath $workspaceInspect -Force
            if (($workspaceInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Legacy installation paths must not contain junctions or symbolic links.' }
        }
        $workspaceParent = [IO.Directory]::GetParent($workspaceInspect)
        $workspaceInspect = if ($workspaceParent) { $workspaceParent.FullName } else { $null }
    }
}
function Read-WorkspaceLegacyFile([string]$Path) {
    Assert-WorkspaceOrdinaryPath $Path
    $workspaceInfo = Get-Item -LiteralPath $Path -Force
    if ($workspaceInfo.PSIsContainer -or $workspaceInfo.Length -gt 2097152) { throw 'Invalid legacy settings file.' }
    return ,([IO.File]::ReadAllBytes($Path))
}
$workspaceTempParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$workspaceStage = Join-Path $workspaceTempParent ('terminal-workspace-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $workspaceStage | Out-Null
try {
    if (-not $Bundle) { $Bundle = "https://github.com/brant92good/terminal-workspace/releases/download/v$Version/terminal-workspace-x86_64-pc-windows-msvc.zip" }
    $workspaceArchive = Join-Path $workspaceStage 'bundle.zip'
    Get-WorkspaceDownload $Bundle $workspaceArchive
    if (-not $Sha256) {
        $workspaceChecksum = Join-Path $workspaceStage 'checksum.txt'
        Get-WorkspaceDownload ($Bundle + '.sha256') $workspaceChecksum
        $Sha256 = ([IO.File]::ReadAllText($workspaceChecksum).Trim() -split '\s+')[0]
    }
    if ($Sha256 -notmatch '^[a-fA-F0-9]{64}$' -or (Get-WorkspaceHash $workspaceArchive) -ne $Sha256.ToLowerInvariant()) { throw 'Release checksum verification failed; installation was left unchanged.' }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $workspaceExtract = Join-Path $workspaceStage 'package'
    New-Item -ItemType Directory -Path $workspaceExtract | Out-Null
    $workspaceZip = [IO.Compression.ZipFile]::OpenRead($workspaceArchive)
    try {
        foreach ($workspaceEntry in $workspaceZip.Entries) {
            $workspaceResolved = [IO.Path]::GetFullPath((Join-Path $workspaceExtract $workspaceEntry.FullName))
            if (-not $workspaceResolved.StartsWith($workspaceExtract + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Release contains an invalid archive path.' }
        }
    } finally { $workspaceZip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($workspaceArchive,$workspaceExtract)
    $workspaceManifest = [IO.File]::ReadAllText((Join-Path $workspaceExtract 'release.json')) | ConvertFrom-Json
    if ($workspaceManifest.schema_version -ne 1 -or $workspaceManifest.version -ne $Version) { throw 'Unexpected bundle version.' }
    $workspaceLicenses = @('licenses/ports-LICENSE.txt','licenses/ssh-sessions-LICENSE.txt','licenses/ssh-files-LICENSE.txt','licenses/ssh-files-THIRD_PARTY_NOTICES.txt')
    $workspaceRequired = @('bin/terminal-workspace.exe','bin/ports.exe','bin/ssh-sessions.exe','bin/ssh-files.exe','bin/PortsFocus.exe','bin/TerminalViews.exe','build/TerminalWorkspace.exe','build/herdr.ico','config/terminal.json','scripts/explorer.ps1','scripts/invoke-native.ps1','doctor.ps1','ports.ps1','sessions.ps1','open.ps1') + $workspaceLicenses
    foreach ($workspaceName in $workspaceRequired) {
        if (-not ($workspaceManifest.files.PSObject.Properties.Name -contains $workspaceName)) { throw "Bundle is missing $workspaceName." }
    }
    foreach ($workspaceProperty in $workspaceManifest.files.PSObject.Properties) {
        $workspaceName = $workspaceProperty.Name
        if ($workspaceName -notmatch '^(bin/[A-Za-z0-9._-]+|build/[A-Za-z0-9._-]+|scripts/[A-Za-z0-9._-]+|config/terminal\.json|doctor\.ps1|ports\.ps1|sessions\.ps1|sync\.ps1|open\.ps1|install\.ps1|bootstrap\.ps1|LICENSE|NOTICE)$' -and $workspaceLicenses -cnotcontains $workspaceName) { throw "Unexpected bundle file $workspaceName." }
        if ($workspaceProperty.Value -notmatch '^[a-f0-9]{64}$' -or (Get-WorkspaceHash (Join-Path $workspaceExtract $workspaceName)) -ne $workspaceProperty.Value) { throw "Invalid bundled file: $workspaceName." }
    }
    foreach ($workspaceApp in @(@('terminal-workspace',$Version),@('ssh-sessions','0.7.0'),@('ports','0.8.0'),@('ssh-files','0.1.0'))) {
        $workspaceResult = & (Join-Path $workspaceExtract ('bin\' + $workspaceApp[0] + '.exe')) --version
        if ($LASTEXITCODE -ne 0 -or ($workspaceResult -join "`n") -notmatch ('(^|\s)' + [regex]::Escape($workspaceApp[1]) + '(\s|$)')) { throw "The bundled $($workspaceApp[0]) executable did not pass its version check." }
    }
    $workspaceMigration = New-Object Collections.Generic.List[object]
    # Read only the exact layout created by the previous public bootstrap. A
    # configured native installation always wins over a discovered old copy.
    if (-not (Test-Path -LiteralPath (Join-Path $InstallDir '.machine.json'))) {
        $workspaceExplicitLegacy = -not [string]::IsNullOrEmpty($LegacyInstallDir)
        if (-not $LegacyInstallDir) { $LegacyInstallDir = Join-Path $env:LOCALAPPDATA 'TerminalWorkspace\install' }
        $LegacyInstallDir = [IO.Path]::GetFullPath($LegacyInstallDir)
        $workspaceLegacyCurrent = Join-Path $LegacyInstallDir 'current.json'
        if ($workspaceExplicitLegacy -or (Test-Path -LiteralPath $workspaceLegacyCurrent)) {
            $workspaceLegacyMarker = Join-Path $LegacyInstallDir '.workspace-installer'
            $workspaceMarkerBytes = Read-WorkspaceLegacyFile $workspaceLegacyMarker
            if ([Text.Encoding]::UTF8.GetString($workspaceMarkerBytes).Trim() -ne 'terminal-workspace') { throw 'Legacy directory is not owned by the previous Terminal Workspace bootstrap.' }
            $workspaceCurrentBytes = Read-WorkspaceLegacyFile $workspaceLegacyCurrent
            $workspaceCurrent = [Text.Encoding]::UTF8.GetString($workspaceCurrentBytes).TrimStart([char]0xfeff) | ConvertFrom-Json
            if ($workspaceCurrent.commit -isnot [string] -or $workspaceCurrent.commit -notmatch '^[a-f0-9]{40}$' -or $workspaceCurrent.workspace -isnot [string]) { throw 'Legacy current.json has an invalid workspace revision.' }
            $workspaceLegacySource = Join-Path $LegacyInstallDir ('downloads\terminal-workspace-' + $workspaceCurrent.commit)
            if (-not [IO.Path]::GetFullPath($workspaceCurrent.workspace).Equals([IO.Path]::GetFullPath($workspaceLegacySource),[StringComparison]::OrdinalIgnoreCase)) { throw 'Legacy current.json points outside its recorded source download.' }
            $workspaceDone = Read-WorkspaceLegacyFile (Join-Path $workspaceLegacySource '.download-complete')
            if ([Text.Encoding]::UTF8.GetString($workspaceDone).Trim() -ne $workspaceCurrent.commit) { throw 'Legacy source download is incomplete.' }
            $workspaceLegacyPreferences = Join-Path $workspaceLegacySource '.machine.json'
            if (-not (Test-Path -LiteralPath $workspaceLegacyPreferences)) { throw 'Legacy installation has no saved preferences to migrate.' }
            $workspaceMigrationInput = Join-Path $workspaceStage 'migration-input'
            New-Item -ItemType Directory -Path (Join-Path $workspaceMigrationInput 'config') -Force | Out-Null
            $workspacePreferenceBytes = Read-WorkspaceLegacyFile $workspaceLegacyPreferences
            [IO.File]::WriteAllBytes((Join-Path $workspaceMigrationInput '.machine.json'),$workspacePreferenceBytes)
            $workspaceSharedSource = Join-Path $workspaceLegacySource 'config\terminal.json'
            $workspaceSharedBytes = if (Test-Path -LiteralPath $workspaceSharedSource) { Read-WorkspaceLegacyFile $workspaceSharedSource } else { [IO.File]::ReadAllBytes((Join-Path $workspaceExtract 'config\terminal.json')) }
            # Preserve a customized native shared file if the destination has one.
            $workspaceSharedDestination = Join-Path $InstallDir 'config\terminal.json'
            $workspaceEffectiveShared = if (Test-Path -LiteralPath $workspaceSharedDestination) { [IO.File]::ReadAllBytes($workspaceSharedDestination) } else { $workspaceSharedBytes }
            [IO.File]::WriteAllBytes((Join-Path $workspaceMigrationInput 'config\terminal.json'),$workspaceEffectiveShared)
            $workspaceValidation = & (Join-Path $workspaceExtract 'bin\terminal-workspace.exe') configure --root $workspaceMigrationInput --settings (Join-Path $workspaceStage 'empty-settings.json') --dry-run --json
            if ($LASTEXITCODE -ne 0) { throw ('Legacy preferences could not be validated. Originals were preserved. ' + ($workspaceValidation -join "`n")) }
            $workspaceBackup = 'migration\legacy-' + [Guid]::NewGuid().ToString('N')
            $workspaceMigration.Add(@{path='.machine.json';bytes=$workspacePreferenceBytes})
            if (-not (Test-Path -LiteralPath $workspaceSharedDestination)) { $workspaceMigration.Add(@{path='config\terminal.json';bytes=$workspaceSharedBytes}) }
            $workspaceMigration.Add(@{path=($workspaceBackup + '\current.json');bytes=$workspaceCurrentBytes})
            $workspaceMigration.Add(@{path=($workspaceBackup + '\.machine.json');bytes=$workspacePreferenceBytes})
            $workspaceMigration.Add(@{path=($workspaceBackup + '\terminal.json');bytes=$workspaceSharedBytes})
            $workspaceMigration.Add(@{path=($workspaceBackup + '\migration.json');bytes=[Text.Encoding]::UTF8.GetBytes((@{schema_version=1;source=$workspaceLegacySource;commit=$workspaceCurrent.commit;version=$Version} | ConvertTo-Json))})
        }
    }
    # All downloads, hashes and launches passed before changing destination files.
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    $workspaceTransaction = [Guid]::NewGuid().ToString('N')
    $workspaceReplaced = New-Object Collections.Generic.List[object]
    try {
        foreach ($workspaceProperty in $workspaceManifest.files.PSObject.Properties) {
            $workspaceName = $workspaceProperty.Name
            # Source checkouts retain their code/config; generated runtimes and
            # their corresponding bundled license notices are installed together.
            if ($SourceCheckout -and $workspaceName -notmatch '^(bin/|build/|licenses/)') { continue }
            if ($workspaceName -eq 'config/terminal.json' -and (Test-Path -LiteralPath (Join-Path $InstallDir $workspaceName))) { continue }
            $workspaceDestination = Join-Path $InstallDir $workspaceName
            New-Item -ItemType Directory -Path (Split-Path $workspaceDestination -Parent) -Force | Out-Null
            $workspacePrevious = $null
            if (Test-Path -LiteralPath $workspaceDestination) {
                $workspacePrevious = $workspaceDestination + '.previous-' + $workspaceTransaction
                Move-Item -LiteralPath $workspaceDestination -Destination $workspacePrevious
            }
            $workspaceReplaced.Add(@{path=$workspaceDestination;previous=$workspacePrevious})
            [IO.File]::Copy((Join-Path $workspaceExtract $workspaceName),$workspaceDestination)
        }
        foreach ($workspaceItem in $workspaceMigration) {
            $workspaceDestination = Join-Path $InstallDir $workspaceItem.path
            New-Item -ItemType Directory -Path (Split-Path $workspaceDestination -Parent) -Force | Out-Null
            # The package config may have been copied above; its transaction entry
            # already restores any original during rollback.
            if (-not @($workspaceReplaced | Where-Object { $_.path -eq $workspaceDestination }).Count) {
                $workspaceReplaced.Add(@{path=$workspaceDestination;previous=$null})
            }
            [IO.File]::WriteAllBytes($workspaceDestination,$workspaceItem.bytes)
        }
        [IO.File]::Copy((Join-Path $workspaceExtract 'release.json'),(Join-Path $InstallDir 'release.json'),$true)
        [IO.File]::WriteAllText($workspaceMarker,$workspaceMarkerValue)
    } catch {
        for ($workspaceIndex=$workspaceReplaced.Count-1; $workspaceIndex -ge 0; $workspaceIndex--) {
            $workspaceItem = $workspaceReplaced[$workspaceIndex]
            if (Test-Path -LiteralPath $workspaceItem.path) { Remove-Item -LiteralPath $workspaceItem.path -Force }
            if ($workspaceItem.previous) { Move-Item -LiteralPath $workspaceItem.previous -Destination $workspaceItem.path }
        }
        throw
    }
    if (-not $NoConfigure) {
        foreach ($workspaceCommand in @('wt.exe','pwsh.exe','ssh.exe')) {
            if (-not (Get-Command $workspaceCommand -CommandType Application -ErrorAction SilentlyContinue)) { throw "Binaries are ready. Install $workspaceCommand before configuring Terminal." }
        }
        $workspaceArguments = @('configure','--root',$InstallDir)
        if (-not (Test-Path -LiteralPath (Join-Path $InstallDir '.machine.json'))) { $workspaceArguments += @('--integration-only','--session-picker') }
        & (Join-Path $InstallDir 'bin\terminal-workspace.exe') @workspaceArguments
        if ($LASTEXITCODE -ne 0) { throw 'Binaries are ready, but Terminal settings were not applied. Run install.ps1 after fixing the reported issue.' }
        if (-not $NoShortcuts) {
            foreach ($workspaceLocation in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('Programs'))) {
                $workspaceProcess = Start-Process -FilePath (Join-Path $InstallDir 'build\TerminalWorkspace.exe') -ArgumentList @('--create-shortcut',('"' + (Join-Path $workspaceLocation 'Terminal Workspace.lnk') + '"')) -WindowStyle Hidden -Wait -PassThru
                if ($workspaceProcess.ExitCode -ne 0) { throw 'Could not create the workspace shortcut.' }
            }
            $workspacePins = Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar'
            $workspaceProcess = Start-Process -FilePath (Join-Path $InstallDir 'build\TerminalWorkspace.exe') -ArgumentList @('--register-pins',('"' + $workspacePins + '"')) -WindowStyle Hidden -Wait -PassThru
            if ($workspaceProcess.ExitCode -ne 0) { Write-Warning 'Re-pin Terminal Workspace from Start to refresh its identity.' }
        }
        if ($ExplorerPowerShell) { & (Join-Path $InstallDir 'scripts\explorer.ps1') }
    }
    Write-Output "Terminal Workspace $Version is ready in $InstallDir"
} finally {
    $workspaceResolvedStage = [IO.Path]::GetFullPath($workspaceStage)
    if ((Split-Path $workspaceResolvedStage -Parent) -eq $workspaceTempParent -and (Split-Path $workspaceResolvedStage -Leaf) -match '^terminal-workspace-[a-f0-9]{32}$') { Remove-Item -LiteralPath $workspaceResolvedStage -Recurse -Force }
}
