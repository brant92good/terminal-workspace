param([Parameter(Mandatory=$true)][string]$PortsBundle, [Parameter(Mandatory=$true)][string]$PortsSha256, [Parameter(Mandatory=$true)][string]$SessionsBinary, [Parameter(Mandatory=$true)][string]$SessionsSha256, [string]$Version = '0.7.1', [string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path $PSScriptRoot -Parent
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $workspaceRoot 'artifacts\release' }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
function Get-PackageHash([string]$Path) {
    $workspaceHasher = [Security.Cryptography.SHA256]::Create(); $workspaceInput = [IO.File]::OpenRead($Path)
    try { ([BitConverter]::ToString($workspaceHasher.ComputeHash($workspaceInput))).Replace('-','').ToLowerInvariant() }
    finally { $workspaceInput.Dispose(); $workspaceHasher.Dispose() }
}
if ((Get-PackageHash $PortsBundle) -ne $PortsSha256 -or (Get-PackageHash $SessionsBinary) -ne $SessionsSha256) { throw 'Leaf release checksum mismatch.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$workspacePorts = Join-Path $OutputDirectory ('ports-' + [Guid]::NewGuid().ToString('N'))
[IO.Compression.ZipFile]::ExtractToDirectory([IO.Path]::GetFullPath($PortsBundle),$workspacePorts)
foreach ($workspaceName in @('ports.exe','PortsFocus.exe','TerminalViews.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $workspacePorts $workspaceName) -PathType Leaf)) { throw "Ports release lacks $workspaceName." }
}
$workspaceBuildRoot = Join-Path $OutputDirectory ('compiled-' + [Guid]::NewGuid().ToString('N'))
& (Join-Path $PSScriptRoot 'build_native.ps1') -PortsBinary (Join-Path $workspacePorts 'ports.exe') -SessionsBinary $SessionsBinary -OutputDirectory $workspaceBuildRoot
# Use the exact released leaf helpers; the build script also compiles them for
# development checks, but production packaging must carry the released bytes.
foreach ($workspaceName in @('PortsFocus.exe','TerminalViews.exe')) { [IO.File]::Copy((Join-Path $workspacePorts $workspaceName),(Join-Path $workspaceBuildRoot ('bin\' + $workspaceName)),$true) }
$workspacePackage = Join-Path $OutputDirectory ('package-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $workspacePackage | Out-Null
$workspaceFiles = @('bin/terminal-workspace.exe','bin/ports.exe','bin/ssh-sessions.exe','bin/PortsFocus.exe','bin/TerminalViews.exe','build/TerminalWorkspace.exe','build/herdr.ico','config/terminal.json','scripts/explorer.ps1','scripts/install-native.ps1','scripts/invoke-native.ps1','install.ps1','bootstrap.ps1','doctor.ps1','ports.ps1','sessions.ps1','sync.ps1','open.ps1','LICENSE','NOTICE')
$workspaceHashes = [ordered]@{}
foreach ($workspaceFile in $workspaceFiles) {
    $workspaceDestination = Join-Path $workspacePackage $workspaceFile
    New-Item -ItemType Directory -Path (Split-Path $workspaceDestination -Parent) -Force | Out-Null
    $workspaceSourceRoot = if ($workspaceFile -match '^(bin/|build/)') { $workspaceBuildRoot } else { $workspaceRoot }
    [IO.File]::Copy((Join-Path $workspaceSourceRoot $workspaceFile),$workspaceDestination)
    $workspaceHashes[$workspaceFile] = Get-PackageHash $workspaceDestination
}
$workspaceManifest = [ordered]@{
    schema_version=1;version=$Version;platform='x86_64-pc-windows-msvc';
    dependencies=[ordered]@{
        ports=@{version='0.7.2';url='https://github.com/brant92good/port-forward-tui/releases/download/v0.7.2/ports-x86_64-pc-windows-msvc.zip';sha256=$PortsSha256;binary_sha256=$workspaceHashes['bin/ports.exe']}
        ssh_sessions=@{version='0.6.0';url='https://github.com/brant92good/ssh-session-tui/releases/download/v0.6.0/ssh-sessions-x86_64-pc-windows-msvc.exe';sha256=$SessionsSha256}
    };files=$workspaceHashes
}
[IO.File]::WriteAllText((Join-Path $workspacePackage 'release.json'),($workspaceManifest | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
$workspaceArchive = Join-Path $OutputDirectory 'terminal-workspace-x86_64-pc-windows-msvc.zip'
if (Test-Path -LiteralPath $workspaceArchive) { throw 'Archive exists. Use a new output directory; release bytes must not be silently replaced.' }
[IO.Compression.ZipFile]::CreateFromDirectory($workspacePackage,$workspaceArchive)
[IO.File]::WriteAllText(($workspaceArchive + '.sha256'),((Get-PackageHash $workspaceArchive) + '  ' + [IO.Path]::GetFileName($workspaceArchive) + "`n"))
Write-Output $workspaceArchive
