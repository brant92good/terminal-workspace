$ErrorActionPreference = 'Stop'
$sessionArguments = @()
$sessionSettings = Join-Path $PSScriptRoot '.machine.json'
if (Test-Path -LiteralPath $sessionSettings) {
    $sessionMachine = [IO.File]::ReadAllText($sessionSettings) | ConvertFrom-Json
    if ($sessionMachine.session_catalog) { $sessionArguments += @('--catalog', $sessionMachine.session_catalog) }
}
& (Join-Path $PSScriptRoot 'bin\ssh-sessions.exe') @sessionArguments @args
exit $LASTEXITCODE
