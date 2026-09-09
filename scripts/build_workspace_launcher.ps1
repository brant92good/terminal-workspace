param([string]$OutputPath = '', [string]$IconPath = '')
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path $PSScriptRoot -Parent
if (-not $OutputPath) { $OutputPath = Join-Path $workspaceRoot 'artifacts\native-launcher\TerminalWorkspace.exe' }
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
if ($OutputPath -eq [IO.Path]::GetFullPath((Join-Path $workspaceRoot 'build\TerminalWorkspace.exe'))) { throw 'Build output cannot replace the live launcher. Use the installer for production replacement.' }
[IO.Directory]::CreateDirectory((Split-Path $OutputPath -Parent)) | Out-Null
if (-not $IconPath) { $IconPath = Join-Path $workspaceRoot 'build\herdr.ico' }
$workspaceFramework = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319'
$workspaceReferences = @('System.Windows.Forms.dll', 'System.Core.dll') + @(
    (Join-Path $workspaceFramework 'WPF\UIAutomationClient.dll'),
    (Join-Path $workspaceFramework 'WPF\UIAutomationTypes.dll'),
    (Join-Path $workspaceFramework 'WPF\WindowsBase.dll')
)
$workspaceOptions = @('/nologo', '/target:winexe', '/platform:x64', "/out:$OutputPath",
    "/win32icon:$IconPath")
$workspaceOptions += $workspaceReferences | ForEach-Object { "/reference:$_" }
& (Join-Path $workspaceFramework 'csc.exe') @workspaceOptions (Join-Path $PSScriptRoot 'WorkspaceLauncher.cs') (Join-Path $PSScriptRoot 'TaskbarIdentity.cs') (Join-Path $PSScriptRoot 'WorkspaceShortcut.cs')
if ($LASTEXITCODE -ne 0) { throw 'Could not build the workspace launcher.' }
