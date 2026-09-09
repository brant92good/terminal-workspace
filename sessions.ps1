$ErrorActionPreference = 'Stop'
$sessionPython = Join-Path $PSScriptRoot 'apps\port-forward-tui\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $sessionPython)) { throw 'Run install.ps1 first.' }
$sessionArguments = @((Join-Path $PSScriptRoot 'apps\ssh-session-tui\app.py'))
$sessionSettings = Join-Path $PSScriptRoot '.machine.json'
if (Test-Path -LiteralPath $sessionSettings) {
    $sessionMachine = Get-Content -LiteralPath $sessionSettings -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($sessionMachine.session_catalog) { $sessionArguments += @('--catalog', $sessionMachine.session_catalog) }
}
& $sessionPython -E -s @sessionArguments @args
exit $LASTEXITCODE
