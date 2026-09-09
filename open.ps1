. (Join-Path $PSScriptRoot 'scripts\invoke-native.ps1')
$workspaceLauncher = Join-Path $PSScriptRoot 'build\TerminalWorkspace.exe'
if (-not (Test-Path -LiteralPath $workspaceLauncher)) { throw 'Run .\install.ps1 first, then .\open.ps1.' }
$result = Invoke-WorkspaceNative $workspaceLauncher $args
exit $result.code
