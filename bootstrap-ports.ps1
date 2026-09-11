param(
    [Parameter(Mandatory=$true)][ValidatePattern('\A[a-f0-9]{40}\z')][string]$IntegrationRevision,
    [ValidateSet('stable','beta')][string]$Channel='stable',
    [ValidateSet('Plan','Status','Install','Import','AddProfile','RemoveProfile')][string]$Action='Plan',
    [string]$Version='', [string]$InstallDir='', [string]$DataDir='', [string]$FromDataDir='',
    [string]$WorkspaceRoot=(Join-Path $env:LOCALAPPDATA 'Programs\TerminalWorkspace'), [switch]$Json
)
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This Workspace bootstrap is Windows-only.' }
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$stage=Join-Path ([IO.Path]::GetTempPath()) ('workspace-ports-source-'+[Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory((Join-Path $stage 'scripts')) | Out-Null
[IO.Directory]::CreateDirectory((Join-Path $stage 'config')) | Out-Null
try {
    # Even Plan fetches pinned source here; only the local helper has zero-network Plan.
    foreach ($relative in @('ports-channel.ps1','scripts/ports-channel-common.ps1','config/ports-channels.json')) {
        Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/brant92good/terminal-workspace/$IntegrationRevision/$relative" -OutFile (Join-Path $stage $relative) -TimeoutSec 60
    }
    $forward=@{}; foreach ($key in $PSBoundParameters.Keys) { $forward[$key]=$PSBoundParameters[$key] }
    $forward.WorkspaceRoot=$WorkspaceRoot
    & (Join-Path $stage 'ports-channel.ps1') @forward
} finally {
    $full=[IO.Path]::GetFullPath($stage)
    if ([IO.Path]::GetDirectoryName($full) -cne [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') -or [IO.Path]::GetFileName($full) -notmatch '\Aworkspace-ports-source-[a-f0-9]{32}\z') { throw 'Unsafe bootstrap cleanup refused.' }
    Remove-Item -LiteralPath $full -Recurse -Force
}
