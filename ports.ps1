$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'bin\ports.exe') @args
exit $LASTEXITCODE
