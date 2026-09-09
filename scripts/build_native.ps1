param([switch]$SkipRust, [string]$PortsBinary = '', [string]$SessionsBinary = '', [string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path $PSScriptRoot -Parent
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $workspaceRoot 'artifacts\native-build' }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
if ($OutputDirectory.TrimEnd('\') -eq $workspaceRoot.TrimEnd('\')) { throw 'Build output cannot be the live checkout. Use the installer for production replacement.' }
$workspaceBuild = Join-Path $OutputDirectory 'build'
$workspaceBin = Join-Path $OutputDirectory 'bin'
New-Item -ItemType Directory -Path $workspaceBuild,$workspaceBin -Force | Out-Null
# The original Herdr PNG is embedded unchanged in an ICO container.
$workspacePng = [IO.File]::ReadAllBytes((Join-Path $workspaceRoot 'assets\herdr.png'))
$workspaceWidth = [int]$workspacePng[19] + 256 * [int]$workspacePng[18]
$workspaceHeight = [int]$workspacePng[23] + 256 * [int]$workspacePng[22]
if ($workspaceWidth -lt 1 -or $workspaceWidth -gt 256 -or $workspaceHeight -lt 1 -or $workspaceHeight -gt 256) { throw 'Herdr icon must be 1-256 pixels.' }
$workspaceStream = New-Object IO.MemoryStream
$workspaceWriter = New-Object IO.BinaryWriter($workspaceStream)
try {
    $workspaceWriter.Write([uint16]0); $workspaceWriter.Write([uint16]1); $workspaceWriter.Write([uint16]1)
    $workspaceWriter.Write([byte]($workspaceWidth % 256)); $workspaceWriter.Write([byte]($workspaceHeight % 256))
    $workspaceWriter.Write([uint16]0); $workspaceWriter.Write([uint16]1); $workspaceWriter.Write([uint16]32)
    $workspaceWriter.Write([uint32]$workspacePng.Length); $workspaceWriter.Write([uint32]22); $workspaceWriter.Write($workspacePng)
    [IO.File]::WriteAllBytes((Join-Path $workspaceBuild 'herdr.ico'),$workspaceStream.ToArray())
} finally { $workspaceWriter.Dispose(); $workspaceStream.Dispose() }
& (Join-Path $PSScriptRoot 'build_workspace_launcher.ps1') -OutputPath (Join-Path $workspaceBuild 'TerminalWorkspace.exe') -IconPath (Join-Path $workspaceBuild 'herdr.ico')
$workspaceFramework = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319'
$workspaceCsc = Join-Path $workspaceFramework 'csc.exe'
$workspaceReferences = @('System.dll','System.Core.dll','System.Web.Extensions.dll') + @(
    (Join-Path $workspaceFramework 'WPF\UIAutomationClient.dll'),
    (Join-Path $workspaceFramework 'WPF\UIAutomationTypes.dll'),
    (Join-Path $workspaceFramework 'WPF\WindowsBase.dll')
)
$workspaceReferenceArguments = $workspaceReferences | ForEach-Object { "/reference:$_" }
& $workspaceCsc /nologo /target:exe /platform:x64 "/out:$(Join-Path $workspaceBin 'TerminalViews.exe')" @workspaceReferenceArguments (Join-Path $PSScriptRoot 'TerminalViews.cs') (Join-Path $PSScriptRoot 'TerminalViewsMain.cs')
if ($LASTEXITCODE -ne 0) { throw 'Could not compile TerminalViews.' }
& $workspaceCsc /nologo /target:exe /platform:x64 "/out:$(Join-Path $workspaceBin 'PortsFocus.exe')" @workspaceReferenceArguments (Join-Path $workspaceRoot 'apps\port-forward-tui\native\FocusHelper.cs')
if ($LASTEXITCODE -ne 0) { throw 'Could not compile PortsFocus.' }
if (-not $SkipRust) {
    $workspaceRustFlags = $env:RUSTFLAGS
    try {
        $env:RUSTFLAGS = '-C target-feature=+crt-static'
        Push-Location $workspaceRoot
        try { & cargo build --release --locked --target x86_64-pc-windows-msvc } finally { Pop-Location }
        if ($LASTEXITCODE -ne 0) { throw 'Could not build the native workspace.' }
        Copy-Item -LiteralPath (Join-Path $workspaceRoot 'target\x86_64-pc-windows-msvc\release\terminal-workspace.exe') -Destination $workspaceBin -Force
    } finally { $env:RUSTFLAGS = $workspaceRustFlags }
}
if ($PortsBinary) { Copy-Item -LiteralPath $PortsBinary -Destination (Join-Path $workspaceBin 'ports.exe') -Force }
if ($SessionsBinary) { Copy-Item -LiteralPath $SessionsBinary -Destination (Join-Path $workspaceBin 'ssh-sessions.exe') -Force }
