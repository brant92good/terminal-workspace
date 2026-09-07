param([switch]$Publish)
$ErrorActionPreference = 'Stop'
$workspaceRoot = $PSScriptRoot
$workspacePython = Join-Path $workspaceRoot 'apps\port-forward-tui\.venv\Scripts\python.exe'
if ($Publish) {
    & $workspacePython (Join-Path $workspaceRoot 'scripts\configure.py') --export
    if ($LASTEXITCODE -ne 0) { throw 'Export failed.' }
    & git -C $workspaceRoot diff --quiet -- config/terminal.json
    if ($LASTEXITCODE -eq 1) {
        & git -C $workspaceRoot add config/terminal.json
        & git -C $workspaceRoot commit --only config/terminal.json -m 'Sync portable Windows Terminal preferences'
        if ($LASTEXITCODE -ne 0) { throw 'Commit failed.' }
    } elseif ($LASTEXITCODE -ne 0) { throw 'Could not inspect preferences.' }
    & git -C $workspaceRoot push origin HEAD:main
    if ($LASTEXITCODE -ne 0) { throw 'Push failed. Reconcile remote changes before retrying.' }
} else {
    & git -C $workspaceRoot status --porcelain | ForEach-Object { throw 'Commit or stash local changes before syncing.' }
    & git -C $workspaceRoot pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Pull failed. Reconcile local changes before retrying.' }
    & (Join-Path $workspaceRoot 'install.ps1')
}
