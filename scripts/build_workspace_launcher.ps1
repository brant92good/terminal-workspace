param([string]$OutputPath = '')
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path $PSScriptRoot -Parent
if (-not $OutputPath) { $OutputPath = Join-Path $workspaceRoot 'build\TerminalWorkspace.exe' }
$workspaceFramework = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319'
$workspaceReferences = @('System.Windows.Forms.dll', 'System.Core.dll') + @(
    (Join-Path $workspaceFramework 'WPF\UIAutomationClient.dll'),
    (Join-Path $workspaceFramework 'WPF\UIAutomationTypes.dll'),
    (Join-Path $workspaceFramework 'WPF\WindowsBase.dll')
)
$workspaceOptions = @('/nologo', '/target:winexe', '/platform:x64', "/out:$OutputPath",
    "/win32icon:$(Join-Path $workspaceRoot 'build\herdr.ico')")
$workspaceOptions += $workspaceReferences | ForEach-Object { "/reference:$_" }
& (Join-Path $workspaceFramework 'csc.exe') @workspaceOptions (Join-Path $PSScriptRoot 'WorkspaceLauncher.cs') (Join-Path $PSScriptRoot 'TaskbarIdentity.cs')
if ($LASTEXITCODE -ne 0) { throw 'Could not build the workspace launcher.' }
