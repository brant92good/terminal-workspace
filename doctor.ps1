$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'bin\terminal-workspace.exe') doctor --root $PSScriptRoot @args
exit $LASTEXITCODE
