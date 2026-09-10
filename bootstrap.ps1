param([string]$InstallDir = '', [string]$Version = '0.8.0', [string]$LegacyInstallDir = '', [switch]$NoConfigure, [switch]$NoShortcuts, [switch]$ExplorerPowerShell)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if ($Version -notmatch '^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$') { throw 'Invalid release version.' }
$workspaceInstaller = Invoke-RestMethod "https://raw.githubusercontent.com/brant92good/terminal-workspace/v$Version/scripts/install-native.ps1"
& ([scriptblock]::Create($workspaceInstaller)) @PSBoundParameters
