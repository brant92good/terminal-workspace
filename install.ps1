param(
    [string]$SshHost = '', [string]$HerdrPath = '',
    [ValidateSet('', 'ssh', 'herdr')][string]$RemoteClient = '',
    [switch]$LocalHerdr, [switch]$NoLocalHerdr,
    [switch]$SessionPicker, [switch]$NoSessionPicker,
    [string]$SessionCatalog = '',
    [ValidateSet('', 'ctrl+n', 'ctrl+t', 'none')][string]$NewTabShortcut = '',
    [switch]$NoShortcuts, [switch]$NoConfigure, [switch]$SkipDependencies,
    [switch]$NonInteractive, [switch]$IntegrationOnly, [switch]$ApplySharedSettings,
    [switch]$ExplorerPowerShell, [switch]$NoExplorerPowerShell,
    [string]$Version = '0.8.0', [string]$Bundle = '', [string]$Sha256 = ''
)
$ErrorActionPreference = 'Stop'
if ($IntegrationOnly -and $ApplySharedSettings) { throw 'Choose IntegrationOnly or ApplySharedSettings.' }
if ($LocalHerdr -and $NoLocalHerdr) { throw 'Choose LocalHerdr or NoLocalHerdr.' }
if ($SessionPicker -and $NoSessionPicker) { throw 'Choose SessionPicker or NoSessionPicker.' }
if ($ExplorerPowerShell -and $NoExplorerPowerShell) { throw 'Choose ExplorerPowerShell or NoExplorerPowerShell.' }
$workspaceRoot = $PSScriptRoot
if (-not $SkipDependencies) {
    $workspacePrepare = @{InstallDir=$workspaceRoot;Version=$Version;NoConfigure=$true;NoShortcuts=$true}
    if (Test-Path -LiteralPath (Join-Path $workspaceRoot '.git')) { $workspacePrepare.SourceCheckout = $true }
    if ($Bundle) { $workspacePrepare.Bundle = $Bundle }
    if ($Sha256) { $workspacePrepare.Sha256 = $Sha256 }
    & (Join-Path $workspaceRoot 'scripts\install-native.ps1') @workspacePrepare
}
$workspaceNative = Join-Path $workspaceRoot 'bin\terminal-workspace.exe'
if (-not (Test-Path -LiteralPath $workspaceNative)) { throw 'The compiled workspace is missing. Run the installer without SkipDependencies.' }
if ($NoConfigure) { Write-Output 'Compiled apps are ready. Terminal settings and shortcuts were not applied.'; return }
foreach ($workspaceCommand in @('wt.exe','pwsh.exe','ssh.exe')) {
    if (-not (Get-Command $workspaceCommand -CommandType Application -ErrorAction SilentlyContinue)) { throw "Missing $workspaceCommand. Install Windows Terminal, PowerShell 7 and OpenSSH Client first." }
}
$workspaceArguments = @('configure','--root',$workspaceRoot)
foreach ($workspacePair in @(@('--ssh-host',$SshHost),@('--herdr',$HerdrPath),@('--remote-client',$RemoteClient),@('--session-catalog',$SessionCatalog),@('--new-tab-shortcut',$NewTabShortcut))) {
    if ($workspacePair[1]) { $workspaceArguments += $workspacePair }
}
foreach ($workspacePair in @(@('--local-herdr',$LocalHerdr),@('--no-local-herdr',$NoLocalHerdr),@('--session-picker',$SessionPicker),@('--no-session-picker',$NoSessionPicker),@('--integration-only',$IntegrationOnly),@('--apply-shared-settings',$ApplySharedSettings))) {
    if ($workspacePair[1]) { $workspaceArguments += $workspacePair[0] }
}
if (-not (Test-Path -LiteralPath (Join-Path $workspaceRoot '.machine.json'))) {
    if (-not $ApplySharedSettings -and -not $IntegrationOnly) { $workspaceArguments += '--integration-only' }
    if (-not $SessionPicker -and -not $NoSessionPicker) { $workspaceArguments += '--session-picker' }
}
& $workspaceNative @workspaceArguments
if ($LASTEXITCODE -ne 0) { throw 'Terminal settings were not applied.' }
if (-not $NoShortcuts) {
    $workspaceLauncher = Join-Path $workspaceRoot 'build\TerminalWorkspace.exe'
    foreach ($workspaceLocation in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('Programs'))) {
        $workspaceResult = Start-Process -FilePath $workspaceLauncher -ArgumentList @('--create-shortcut',('"' + (Join-Path $workspaceLocation 'Terminal Workspace.lnk') + '"')) -WindowStyle Hidden -Wait -PassThru
        if ($workspaceResult.ExitCode -ne 0) { throw 'Could not create the workspace shortcut.' }
    }
    $workspacePins = Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar'
    $workspaceResult = Start-Process -FilePath $workspaceLauncher -ArgumentList @('--register-pins',('"' + $workspacePins + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($workspaceResult.ExitCode -ne 0) { Write-Warning 'Re-pin Terminal Workspace from Start to refresh its identity.' }
}
if ($ExplorerPowerShell) { & (Join-Path $workspaceRoot 'scripts\explorer.ps1') }
if ($NoExplorerPowerShell) { & (Join-Path $workspaceRoot 'scripts\explorer.ps1') -Remove }
Write-Output 'Ready. Open Terminal Workspace from Start to choose a machine. New tabs keep your saved picker preference.'
