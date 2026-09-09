. (Join-Path $PSScriptRoot 'scripts\invoke-native.ps1')
$capture = @($args | Where-Object { $_ -in @('--json','--help','-h','--version','-V') }).Count -gt 0
$result = Invoke-WorkspaceNative (Join-Path $PSScriptRoot 'bin\ports.exe') $args -CaptureOutput:$capture
if ($result.output) { Write-WorkspaceNativeOutput $result.output }
exit $result.code
