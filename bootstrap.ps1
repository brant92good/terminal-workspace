param([string]$InstallDir = '', [string]$Version = '0.7.0', [switch]$NoConfigure, [switch]$NoShortcuts, [switch]$ExplorerPowerShell)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$workspaceInstaller = Invoke-RestMethod 'https://raw.githubusercontent.com/brant92good/terminal-workspace/main/scripts/install-native.ps1'
& ([scriptblock]::Create($workspaceInstaller)) @PSBoundParameters
