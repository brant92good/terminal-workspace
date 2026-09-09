param(
    [string]$SshHost = '',
    [string]$Python = '',
    [string]$HerdrPath = '',
    [ValidateSet('', 'ssh', 'herdr')][string]$RemoteClient = '',
    [switch]$LocalHerdr,
    [switch]$NoLocalHerdr,
    [switch]$SessionPicker,
    [switch]$NoSessionPicker,
    [string]$SessionCatalog = '',
    [ValidateSet('', 'ctrl+n', 'ctrl+t', 'none')][string]$NewTabShortcut = '',
    [switch]$NoShortcuts,
    [switch]$NoConfigure,
    [switch]$SkipDependencies,
    [switch]$NonInteractive,
    [switch]$IntegrationOnly,
    [switch]$ApplySharedSettings
)
$ErrorActionPreference = 'Stop'
if ($IntegrationOnly -and $ApplySharedSettings) {
    throw 'Choose -IntegrationOnly or -ApplySharedSettings, not both.'
}
if ($LocalHerdr -and $NoLocalHerdr) { throw 'Choose -LocalHerdr or -NoLocalHerdr, not both.' }
if ($SessionPicker -and $NoSessionPicker) { throw 'Choose -SessionPicker or -NoSessionPicker, not both.' }
$workspaceRoot = $PSScriptRoot
$workspaceApp = Join-Path $workspaceRoot 'apps\port-forward-tui'
if (Test-Path -LiteralPath (Join-Path $workspaceRoot '.git')) {
    $workspaceGitPrompt = $env:GIT_TERMINAL_PROMPT
    try {
        if ($NonInteractive) { $env:GIT_TERMINAL_PROMPT = '0' }
        & git -C $workspaceRoot submodule update --init apps/port-forward-tui apps/ssh-session-tui
    } finally { $env:GIT_TERMINAL_PROMPT = $workspaceGitPrompt }
    if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the app submodules.' }
} elseif (-not (Test-Path -LiteralPath (Join-Path $workspaceApp 'app.py')) -or
          -not (Test-Path -LiteralPath (Join-Path $workspaceRoot 'apps\ssh-session-tui\app.py'))) {
    throw 'The source bundle is incomplete. Run the README bootstrap command to download the pinned apps.'
}
foreach ($workspaceCommand in $(if ($NoConfigure) { @() } else { @('wt.exe', 'pwsh.exe', 'ssh.exe') })) {
    if (-not (Get-Command $workspaceCommand -ErrorAction SilentlyContinue)) {
        $workspaceFix = switch ($workspaceCommand) {
            'wt.exe' { 'Install Windows Terminal from Microsoft Store.' }
            'pwsh.exe' { 'Install PowerShell 7 from Microsoft Store or run winget install --id Microsoft.PowerShell -e.' }
            'ssh.exe' { 'Install OpenSSH Client in Windows Settings > Optional features.' }
        }
        throw "Missing $workspaceCommand. $workspaceFix"
    }
}
. (Join-Path $workspaceApp 'scripts\python_bootstrap.ps1')
. (Join-Path $workspaceApp 'scripts\setup_helpers.ps1')
$SshHost = Get-SetupHost -Value $SshHost -SettingsPath (Join-Path $workspaceRoot '.machine.json') -Key 'ssh_host' -NonInteractive:$NonInteractive
$workspaceSavedHerdr = ''
if (Test-Path -LiteralPath (Join-Path $workspaceRoot '.machine.json')) {
    $workspaceSavedHerdr = (Get-Content -LiteralPath (Join-Path $workspaceRoot '.machine.json') -Raw -Encoding UTF8 | ConvertFrom-Json).herdr
}
if (-not $HerdrPath -and -not $workspaceSavedHerdr) {
    $herdrCommand = Get-Command herdr.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($herdrCommand) { $HerdrPath = $herdrCommand.Source }
}
Write-Host 'Preparing the app environment and workspace launcher...'
$workspacePython = Initialize-AppPython -Root $workspaceApp -Python $Python
if (-not $SkipDependencies) {
    & $workspacePython -E -s -X utf8 -m pip install --no-input --disable-pip-version-check -q -r (Join-Path $workspaceApp 'requirements.txt') -r (Join-Path $workspaceRoot 'apps\ssh-session-tui\requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the port app dependencies.' }
}
& $workspacePython -E -s -X utf8 (Join-Path $workspaceApp 'port_forward_tui\build_focus_helper.py')
if ($LASTEXITCODE -ne 0) { throw 'Could not build the fast return-shortcut helper.' }
& $workspacePython -E -s -X utf8 (Join-Path $workspaceRoot 'scripts\build_icon.py')
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the Herdr icon.' }
if ($NoConfigure) {
    Write-Output 'App runtime and helpers are ready. Terminal settings and shortcuts were not applied.'
    return
}
$workspaceArguments = @((Join-Path $workspaceRoot 'scripts\configure.py'))
if ($SshHost) { $workspaceArguments += @('--ssh-host', $SshHost) }
if ($HerdrPath) { $workspaceArguments += @('--herdr', $HerdrPath) }
if ($RemoteClient) { $workspaceArguments += @('--remote-client', $RemoteClient) }
if ($LocalHerdr) { $workspaceArguments += '--local-herdr' }
if ($NoLocalHerdr) { $workspaceArguments += '--no-local-herdr' }
if ($SessionPicker) { $workspaceArguments += '--session-picker' }
if ($NoSessionPicker) { $workspaceArguments += '--no-session-picker' }
if ($SessionCatalog) { $workspaceArguments += @('--session-catalog', $SessionCatalog) }
if ($NewTabShortcut) { $workspaceArguments += @('--new-tab-shortcut', $NewTabShortcut) }
if ($IntegrationOnly) { $workspaceArguments += '--integration-only' }
if ($ApplySharedSettings) { $workspaceArguments += '--apply-shared-settings' }
& $workspacePython -E -s -X utf8 @workspaceArguments
if ($LASTEXITCODE -ne 0) { throw 'Terminal settings were not applied.' }
$workspaceCompiler = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$workspaceLauncher = Join-Path $workspaceRoot 'build\TerminalWorkspace.exe'
& $workspaceCompiler /nologo /target:winexe /reference:System.Windows.Forms.dll "/out:$workspaceLauncher" "/win32icon:$(Join-Path $workspaceRoot 'build\herdr.ico')" (Join-Path $workspaceRoot 'scripts\WorkspaceLauncher.cs')
if ($LASTEXITCODE -ne 0) { throw 'Could not build the taskbar launcher.' }
if (-not $NoShortcuts) {
    $workspaceShell = New-Object -ComObject WScript.Shell
    foreach ($workspaceLocation in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
        $workspaceShortcut = $workspaceShell.CreateShortcut((Join-Path $workspaceLocation 'Terminal Workspace.lnk'))
        $workspaceShortcut.TargetPath = $workspaceLauncher
        $workspaceShortcut.WorkingDirectory = $workspaceRoot
        $workspaceShortcut.IconLocation = "$workspaceLauncher,0"
        $workspaceShortcut.Description = 'Open the configured remote workspace and Ports, with the remote tab selected'
        $workspaceShortcut.Save()
    }
}
Write-Output 'Ready. Open Terminal Workspace from Start: choose a machine, then use its remote and Ports tabs.'
Write-Output 'H in Ports changes machines. Installation does not require choosing a host.'
Write-Output 'Setup help: .\doctor.ps1. Connection commands for agents: .\ports.ps1 --help.'
