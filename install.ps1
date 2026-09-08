param(
    [string]$SshHost = '',
    [string]$Python = '',
    [string]$HerdrPath = '',
    [switch]$NoShortcuts,
    [switch]$SkipDependencies,
    [switch]$NonInteractive
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = $PSScriptRoot
$workspaceApp = Join-Path $workspaceRoot 'apps\port-forward-tui'
$workspaceGitPrompt = $env:GIT_TERMINAL_PROMPT
try {
    if ($NonInteractive) { $env:GIT_TERMINAL_PROMPT = '0' }
    & git -C $workspaceRoot submodule update --init apps/port-forward-tui
} finally { $env:GIT_TERMINAL_PROMPT = $workspaceGitPrompt }
if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the port app submodule.' }
foreach ($workspaceCommand in @('wt.exe', 'pwsh.exe', 'ssh.exe')) {
    if (-not (Get-Command $workspaceCommand -ErrorAction SilentlyContinue)) {
        $workspaceFix = switch ($workspaceCommand) {
            'wt.exe' { 'Install Windows Terminal from Microsoft Store.' }
            'pwsh.exe' { 'Install PowerShell 7 from Microsoft Store or run winget install --id Microsoft.PowerShell -e.' }
            'ssh.exe' { 'Install OpenSSH Client in Windows Settings > Optional features.' }
        }
        throw "Missing $workspaceCommand. $workspaceFix"
    }
}
. (Join-Path $workspaceApp 'python_bootstrap.ps1')
. (Join-Path $workspaceApp 'setup_helpers.ps1')
$SshHost = Get-SetupHost -Value $SshHost -SettingsPath (Join-Path $workspaceRoot '.machine.json') -Key 'ssh_host' -NonInteractive:$NonInteractive
$workspaceSavedHerdr = ''
if (Test-Path -LiteralPath (Join-Path $workspaceRoot '.machine.json')) {
    $workspaceSavedHerdr = (Get-Content -LiteralPath (Join-Path $workspaceRoot '.machine.json') -Raw -Encoding UTF8 | ConvertFrom-Json).herdr
}
if (-not $HerdrPath -and -not $workspaceSavedHerdr) {
    $herdrCommand = Get-Command herdr.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($herdrCommand) { $HerdrPath = $herdrCommand.Source }
}
Write-Host 'Preparing the app environment and the two-tab launcher...'
$workspacePython = Initialize-AppPython -Root $workspaceApp -Python $Python
if (-not $SkipDependencies) {
    & $workspacePython -E -s -m pip install --no-input -r (Join-Path $workspaceApp 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the port app dependencies.' }
}
& $workspacePython -E -s (Join-Path $workspaceApp 'build_focus_helper.py')
if ($LASTEXITCODE -ne 0) { throw 'Could not build the fast Herdr/Ports shortcut helper.' }
& $workspacePython -E -s (Join-Path $workspaceRoot 'scripts\build_icon.py')
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the Herdr icon.' }
$workspaceArguments = @((Join-Path $workspaceRoot 'scripts\configure.py'))
if ($SshHost) { $workspaceArguments += @('--ssh-host', $SshHost) }
if ($HerdrPath) { $workspaceArguments += @('--herdr', $HerdrPath) }
& $workspacePython -E -s @workspaceArguments
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
        $workspaceShortcut.Description = 'Open Herdr and Ports in one Terminal window, focused on Herdr'
        $workspaceShortcut.Save()
    }
}
Write-Output 'Ready. Open Terminal Workspace from Start or the desktop: Herdr opens first, Ports second.'
Write-Output 'In Ports, press A to add a connection. In Terminal, Ctrl+Alt+H/P returns to Herdr/Ports.'
Write-Output 'Setup help: .\doctor.ps1. Connection commands for agents: .\ports.ps1 --help.'
