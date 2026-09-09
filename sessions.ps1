. (Join-Path $PSScriptRoot 'scripts\invoke-native.ps1')
$sessionArguments = @()
$sessionSettings = Join-Path $PSScriptRoot '.machine.json'
if (Test-Path -LiteralPath $sessionSettings) {
    $sessionMachine = [IO.File]::ReadAllText($sessionSettings) | ConvertFrom-Json
    if ($sessionMachine.session_catalog) { $sessionArguments += @('--catalog', $sessionMachine.session_catalog) }
}
$capture = @($args | Where-Object { $_ -in @('--json','--help','-h','--version','-V') }).Count -gt 0
$result = Invoke-WorkspaceNative (Join-Path $PSScriptRoot 'bin\ssh-sessions.exe') ($sessionArguments + $args) -CaptureOutput:$capture
if ($result.output) { Write-WorkspaceNativeOutput $result.output }
exit $result.code
