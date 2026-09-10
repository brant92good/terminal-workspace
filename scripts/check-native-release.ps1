param([string]$Version = '0.7.2')
# Developer/release qualification only. All writes stay in this owned fixture.
$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$') { throw 'Invalid release version.' }
$workspaceTempParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$workspaceFixture = Join-Path $workspaceTempParent ('workspace-release-' + [Guid]::NewGuid().ToString('N'))
$workspaceDestination = Join-Path $workspaceFixture "space unicode-$([char]0x6e2c)$([char]0x8a66) O'Brien"
$workspaceSavedLocal = $env:LOCALAPPDATA
try {
    New-Item -ItemType Directory -Path $workspaceFixture | Out-Null
    $env:LOCALAPPDATA = Join-Path $workspaceFixture 'local-data'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $workspaceSource = Invoke-RestMethod "https://raw.githubusercontent.com/brant92good/terminal-workspace/v$Version/bootstrap.ps1"
    $workspaceBootstrap = [scriptblock]::Create($workspaceSource)
    # No Bundle/SHA override: exercise the released bootstrap, versioned installer
    # and real GitHub release ZIP/checksum URL on both installation and update.
    & $workspaceBootstrap -Version $Version -InstallDir $workspaceDestination -NoConfigure -NoShortcuts
    $workspaceBinary = Join-Path $workspaceDestination 'bin\terminal-workspace.exe'
    $workspaceResult = & $workspaceBinary --version
    if ($LASTEXITCODE -ne 0 -or $workspaceResult -ne "terminal-workspace $Version") { throw 'Installed version differs from the requested release.' }
    $workspaceSettings = Join-Path $workspaceFixture 'terminal-settings.json'
    [IO.File]::WriteAllText($workspaceSettings,'{"theme":"light","profiles":{"list":[]}}')
    $workspaceConfigured = & $workspaceBinary configure --root $workspaceDestination --settings $workspaceSettings --integration-only --session-picker --new-tab-shortcut ctrl+n --json
    if ($LASTEXITCODE -ne 0 -or ($workspaceConfigured | ConvertFrom-Json).ok -ne $true) { throw 'Installed configure command failed in the fixture.' }
    $workspaceBefore = [IO.File]::ReadAllText((Join-Path $workspaceDestination '.machine.json'))
    & $workspaceBootstrap -Version $Version -InstallDir $workspaceDestination -NoConfigure -NoShortcuts
    if ([IO.File]::ReadAllText((Join-Path $workspaceDestination '.machine.json')) -cne $workspaceBefore) { throw 'Update changed personal preferences.' }
    $workspaceRendered = [IO.File]::ReadAllText($workspaceSettings) | ConvertFrom-Json
    if ($workspaceRendered.defaultProfile -ne '{2ab64c44-ef5c-48d2-8f4d-678473aae748}' -or $workspaceRendered.theme -ne 'light') { throw 'New-tab or existing-theme contract failed.' }
    if ([IO.File]::ReadAllText($workspaceSettings) -match 'python(\.exe)?') { throw 'A profile still uses Python.' }
    [PSCustomObject]@{ok=$true;version=$Version;checks=@('real HTTPS bootstrap','versioned installer','released ZIP/checksums','fresh install','update','saved preferences','fixture configure');desktop_changed=$false} | ConvertTo-Json -Depth 4
} finally {
    $env:LOCALAPPDATA = $workspaceSavedLocal
    $workspaceResolved = [IO.Path]::GetFullPath($workspaceFixture)
    if ((Split-Path $workspaceResolved -Parent) -eq $workspaceTempParent -and (Split-Path $workspaceResolved -Leaf) -match '^workspace-release-[a-f0-9]{32}$') {
        Remove-Item -LiteralPath $workspaceResolved -Recurse -Force -ErrorAction SilentlyContinue
    }
}
