$ErrorActionPreference = 'Stop'
$doctorApp = Join-Path $PSScriptRoot 'apps\port-forward-tui'
if (-not (Test-Path -LiteralPath (Join-Path $doctorApp 'diagnostics.py'))) {
    throw 'The included port app is missing or too old. Run git submodule update --init --recursive from this folder.'
}
. (Join-Path $doctorApp 'python_bootstrap.ps1')
$doctorPython = Join-Path $doctorApp '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $doctorPython)) { $doctorPython = (Resolve-AppPython).executable }
& $doctorPython -E -s (Join-Path $PSScriptRoot 'scripts\doctor.py') @args
exit $LASTEXITCODE
