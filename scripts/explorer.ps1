param([switch]$Remove, [switch]$Plan, [string]$TerminalPath = 'wt.exe', [string]$PowerShellPath = 'pwsh.exe')
$ErrorActionPreference = 'Stop'
$workspaceOwner = 'TerminalWorkspace.Explorer.PowerShell.v1'
$workspaceProfile = '{574e775e-4f2a-5b96-ac1e-a2962a402336}'
foreach ($workspaceExecutable in @($TerminalPath,$PowerShellPath)) {
    if ($workspaceExecutable.Contains('"') -or $workspaceExecutable.Contains("`r") -or $workspaceExecutable.Contains("`n")) { throw 'Invalid executable path.' }
}
# The suffix keeps a drive root's trailing slash away from the closing quote.
# Windows resolves C:\folder\. to that same directory.
$workspaceCommand = '"' + $TerminalPath + '" -p "' + $workspaceProfile + '" -d "%V\." "' + $PowerShellPath + '" -NoLogo'
$workspaceKeys = @('Software\Classes\Directory\shell\TerminalWorkspace.PowerShell',
    'Software\Classes\Directory\Background\shell\TerminalWorkspace.PowerShell',
    'Software\Classes\Drive\shell\TerminalWorkspace.PowerShell')
if ($Plan) {
    [ordered]@{ operation=$(if($Remove){'remove'}else{'install'}); owner=$workspaceOwner; keys=$workspaceKeys; command=$workspaceCommand; label='Open PowerShell here'; modernBuiltInChanged=$false } | ConvertTo-Json -Depth 5
    return
}
if (-not $Remove) {
    foreach ($workspaceExecutable in @($TerminalPath,$PowerShellPath)) {
        if (-not (Get-Command $workspaceExecutable -CommandType Application -ErrorAction SilentlyContinue)) { throw "Missing $workspaceExecutable. Install Windows Terminal and PowerShell 7 first." }
    }
}
# Check every key before any mutation. A same-named entry from another owner
# is never overwritten. Normal Windows Terminal Explorer keys are untouched.
foreach ($workspaceKeyPath in $workspaceKeys) {
    $workspaceKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($workspaceKeyPath)
    try {
        if ($workspaceKey -and $workspaceKey.GetValue('WorkspaceOwner') -ne $workspaceOwner) { throw "The Explorer key $workspaceKeyPath belongs to another setup; no changes were made." }
    } finally { if ($workspaceKey) { $workspaceKey.Dispose() } }
}
foreach ($workspaceKeyPath in $workspaceKeys) {
    if ($Remove) { [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($workspaceKeyPath,$false); continue }
    $workspaceKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($workspaceKeyPath)
    try {
        $workspaceKey.SetValue('', 'Open PowerShell here')
        $workspaceKey.SetValue('WorkspaceOwner',$workspaceOwner)
        $workspaceKey.SetValue('Icon',$PowerShellPath)
        $workspaceSubkey = $workspaceKey.CreateSubKey('command')
        try { $workspaceSubkey.SetValue('',$workspaceCommand) } finally { $workspaceSubkey.Dispose() }
    } finally { $workspaceKey.Dispose() }
}
Write-Output $(if ($Remove) { 'Removed the workspace-owned Open PowerShell here entries.' } else { 'Added Open PowerShell here. On Windows 11 it is in Show more options; the built-in Open in Terminal entry still uses the SSH picker.' })
