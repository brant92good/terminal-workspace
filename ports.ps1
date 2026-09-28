. (Join-Path $PSScriptRoot 'scripts\invoke-native.ps1')
$capture = @($args | Where-Object { $_ -in @('--json','--help','-h','--version','-V') }).Count -gt 0
$result = Invoke-WorkspaceNative (Join-Path $PSScriptRoot 'bin\terminal-workspace.exe') (@('ports','--') + $args) -CaptureOutput:$capture
if ($result.output) { Write-WorkspaceNativeOutput $result.output }
exit $result.code
