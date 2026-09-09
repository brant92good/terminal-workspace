param([Parameter(Mandatory=$true)][string]$Bundle)
# Compile under Cargo, then execute after Cargo has released its process job.
# The test uses only an extracted bundle, temporary metadata and a stopped rule.
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path $PSScriptRoot -Parent
$workspaceBundle = [IO.Path]::GetFullPath($Bundle)
$workspacePreviousBundle = $env:WORKSPACE_TEST_BUNDLE
Push-Location $workspaceRoot
try {
    $workspaceBuild = & cargo test --locked --test native_capture --no-run --message-format=json
    if ($LASTEXITCODE -ne 0) { throw 'Could not compile the captured-CLI bundle regression.' }
    $workspaceTest = @($workspaceBuild | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object { $_.reason -eq 'compiler-artifact' -and $_.target.name -eq 'native_capture' -and $_.executable })
    if ($workspaceTest.Count -ne 1) { throw 'Expected exactly one captured-CLI test executable.' }
    $env:WORKSPACE_TEST_BUNDLE = $workspaceBundle
    & $workspaceTest[0].executable --ignored
    if ($LASTEXITCODE -ne 0) { throw 'Captured first-save/restart bundle qualification failed.' }
} finally { $env:WORKSPACE_TEST_BUNDLE = $workspacePreviousBundle; Pop-Location }
