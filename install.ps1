param(
    [string]$SshHost = '',
    [string]$Python = 'python',
    [string]$HerdrPath = '',
    [switch]$NoShortcuts,
    [switch]$SkipDependencies
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = $PSScriptRoot
$workspaceApp = Join-Path $workspaceRoot 'apps\port-forward-tui'
& git -C $workspaceRoot submodule update --init apps/port-forward-tui
if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the port app submodule.' }
foreach ($workspaceCommand in @('wt.exe', 'pwsh.exe', 'ssh.exe')) {
    if (-not (Get-Command $workspaceCommand -ErrorAction SilentlyContinue)) {
        throw "Missing $workspaceCommand. See README prerequisites."
    }
}
$workspacePython = Join-Path $workspaceApp '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $workspacePython)) {
    & $Python -m venv (Join-Path $workspaceApp '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required.' }
}
if (-not $SkipDependencies) {
    & $workspacePython -m pip install -r (Join-Path $workspaceApp 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the port app dependencies.' }
}
& $workspacePython (Join-Path $workspaceRoot 'scripts\build_icon.py')
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the Herdr icon.' }
$workspaceArguments = @((Join-Path $workspaceRoot 'scripts\configure.py'))
if ($SshHost) { $workspaceArguments += @('--ssh-host', $SshHost) }
if ($HerdrPath) { $workspaceArguments += @('--herdr', $HerdrPath) }
& $workspacePython @workspaceArguments
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
Write-Output 'Ready. Terminal Workspace opens Herdr first and Ports second, with Herdr selected.'
