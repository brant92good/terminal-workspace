. (Join-Path $PSScriptRoot 'scripts\invoke-native.ps1')
$result = Invoke-WorkspaceNative (Join-Path $PSScriptRoot 'bin\terminal-workspace.exe') (@('doctor','--root',$PSScriptRoot) + $args) -CaptureOutput
if ($result.output) { Write-WorkspaceNativeOutput $result.output }
exit $result.code
