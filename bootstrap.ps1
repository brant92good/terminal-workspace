param(
    [string]$InstallDir = '',
    [ValidatePattern('^(main|[a-f0-9]{40})$')][string]$Revision = 'main',
    [switch]$NoConfigure,
    [switch]$NoShortcuts
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1')
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if (-not $InstallDir) { $InstallDir = Join-Path $env:LOCALAPPDATA 'TerminalWorkspace\install' }
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
$marker = Join-Path $InstallDir '.workspace-installer'
if ((Test-Path -LiteralPath $InstallDir) -and -not (Test-Path -LiteralPath $marker) -and
    @(Get-ChildItem -LiteralPath $InstallDir -Force).Count) {
    throw "Choose an empty directory. $InstallDir contains files from another installation."
}
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
[IO.File]::WriteAllText($marker, 'terminal-workspace')

function Get-PublicGitHubJson {
    param([string]$Path)
    $headers = @{ 'User-Agent' = 'terminal-workspace-installer'; Accept = 'application/vnd.github+json' }
    $token = if ($env:GH_TOKEN) { $env:GH_TOKEN } else { $env:GITHUB_TOKEN }
    if ($token) { $headers.Authorization = 'Bearer ' + $token }
    Invoke-RestMethod -Uri ('https://api.github.com/repos/brant92good/' + $Path) -Headers $headers
}
function Get-SourceArchive {
    param([ValidateSet('terminal-workspace', 'port-forward-tui', 'ssh-session-tui')][string]$Repository,
          [ValidatePattern('^[a-f0-9]{40}$')][string]$Commit)
    $cache = Join-Path $InstallDir 'downloads'
    New-Item -ItemType Directory -Path $cache -Force | Out-Null
    $destination = Join-Path $cache "$Repository-$Commit"
    $done = Join-Path $destination '.download-complete'
    if (Test-Path -LiteralPath $done) { return $destination }
    # Each attempt has a new directory. A failed extraction is never reused.
    $attempt = Join-Path $cache ([Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $attempt | Out-Null
    $archive = Join-Path $attempt 'source.zip'
    Write-Host "Downloading $Repository..."
    Invoke-WebRequest -UseBasicParsing -Uri "https://codeload.github.com/brant92good/$Repository/zip/$Commit" -OutFile $archive
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($archive, $attempt)
    $extracted = Join-Path $attempt "$Repository-$Commit"
    if (-not (Test-Path -LiteralPath (Join-Path $extracted 'README.md'))) { throw 'Incomplete source download.' }
    # Copy into the deterministic cache location; do not move or delete user paths.
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Get-ChildItem -LiteralPath $extracted -Force | Copy-Item -Destination $destination -Recurse -Force
    [IO.File]::WriteAllText($done, $Commit)
    return $destination
}

Write-Host 'Preparing Terminal Workspace...'
$commit = (Get-PublicGitHubJson "terminal-workspace/commits/$Revision").sha
if ($commit -notmatch '^[a-f0-9]{40}$') { throw 'GitHub did not return a valid workspace revision.' }
$tree = (Get-PublicGitHubJson "terminal-workspace/git/trees/${commit}?recursive=1").tree
$workspace = Get-SourceArchive 'terminal-workspace' $commit
foreach ($app in @('port-forward-tui', 'ssh-session-tui')) {
    $pin = @($tree | Where-Object { $_.path -eq "apps/$app" -and $_.type -eq 'commit' })
    if ($pin.Count -ne 1) { throw "The release has no unique pin for $app." }
    $child = Get-SourceArchive $app $pin[0].sha
    $target = Join-Path $workspace "apps\$app"
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Get-ChildItem -LiteralPath $child -Force | Copy-Item -Destination $target -Recurse -Force
}
$currentFile = Join-Path $InstallDir 'current.json'
if ((Test-Path -LiteralPath $currentFile) -and -not (Test-Path -LiteralPath (Join-Path $workspace '.machine.json'))) {
    $previousPath = (Get-Content -LiteralPath $currentFile -Raw | ConvertFrom-Json).workspace
    $previousPath = [IO.Path]::GetFullPath($previousPath)
    $ownedPrefix = $InstallDir.TrimEnd('\') + '\'
    if (-not $previousPath.StartsWith($ownedPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Previous install path is outside this installation.' }
    $preferences = Join-Path $previousPath '.machine.json'
    if (Test-Path -LiteralPath $preferences) { Copy-Item -LiteralPath $preferences -Destination $workspace }
}
$settings = @{
    UV_UNMANAGED_INSTALL = (Join-Path $InstallDir 'uv')
    UV_PYTHON_INSTALL_DIR = (Join-Path $InstallDir 'python')
    UV_PYTHON_INSTALL_BIN = '0'; UV_PYTHON_INSTALL_REGISTRY = '0'; UV_NO_CONFIG = '1'
}
$savedEnvironment = @{}
try {
    foreach ($key in $settings.Keys) {
        $savedEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
        [Environment]::SetEnvironmentVariable($key, $settings[$key], 'Process')
    }
    $uvApp = Join-Path $InstallDir 'uv\uv.exe'
    if (-not (Test-Path -LiteralPath $uvApp)) {
        & ([scriptblock]::Create((Invoke-RestMethod 'https://astral.sh/uv/0.10.10/install.ps1')))
        if (-not (Test-Path -LiteralPath $uvApp)) { throw 'Could not prepare uv.' }
    }
    & $uvApp --no-config python install 3.12
    if ($LASTEXITCODE -ne 0) { throw 'Could not download the app Python runtime.' }
    $python = & $uvApp --no-config python find --managed-python 3.12
    if ($LASTEXITCODE -ne 0) { throw 'Could not find the downloaded Python runtime.' }
    $options = @{ Python = $python; NonInteractive = $true; NoShortcuts = $NoShortcuts; NoConfigure = $NoConfigure }
    if (-not (Test-Path -LiteralPath (Join-Path $workspace '.machine.json'))) {
        $options.IntegrationOnly = $true
        $options.SessionPicker = $true
    }
    & (Join-Path $workspace 'install.ps1') @options
    if (-not $NoConfigure) {
        @{ workspace = $workspace; commit = $commit } | ConvertTo-Json | Set-Content -LiteralPath $currentFile -Encoding UTF8
        Write-Host 'Ready. New Terminal tabs open SSH Sessions. Ctrl+Alt+N opens local PowerShell.'
    }
    Write-Output "Workspace files: $workspace"
} finally {
    foreach ($key in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($key, $savedEnvironment[$key], 'Process') }
}
