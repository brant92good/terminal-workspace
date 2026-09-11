param(
    [ValidateSet('stable','beta')][string]$Channel='stable',
    [ValidateSet('Plan','Status','Install','Import','AddProfile','RemoveProfile')][string]$Action='Plan',
    [string]$Version='', [string]$InstallDir='', [string]$DataDir='', [string]$FromDataDir='',
    [string]$WorkspaceRoot=$PSScriptRoot, [string]$IntegrationRevision='', [switch]$Json
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'The Workspace channel helper is Windows-only. Use the portable leaf installer on Linux/macOS.' }
. (Join-Path $PSScriptRoot 'scripts\ports-channel-common.ps1')
$contract=Read-PortsChannelContract (Join-Path $PSScriptRoot 'config\ports-channels.json')
if ($IntegrationRevision -and $IntegrationRevision -cnotmatch '\A[a-f0-9]{40}\z') { throw 'IntegrationRevision must be a full commit hash.' }
$workspace=Resolve-PortsChannelPath $WorkspaceRoot
if ($Channel -eq 'stable') {
    if ($Version -and $Version -cne $contract.stable.version) { throw 'The stable workspace pins Ports 0.9.1.' }
    if ($Action -notin @('Plan','Status')) { throw 'This helper never modifies stable. Use the ordinary Workspace installer for stable installation.' }
    $binary=Join-Path $workspace 'bin\ports.exe'
    $result=[ordered]@{channel='stable';action=$Action;version=$contract.stable.version;workspace_version=$contract.stable.workspace_version;binary=$binary;runtime_launched=$false}
    if ($Action -eq 'Status') { $result.binary_matches=([IO.File]::Exists($binary) -and (Get-PortsChannelHash $binary) -ceq $contract.stable.binary_sha256) }
} else {
    if (-not $Version -or $Version -cne $contract.beta.version) { throw 'Select the exact beta Version recorded by this integration commit.' }
    if (-not $InstallDir) { $InstallDir=Join-Path $env:LOCALAPPDATA 'Programs\PortsBeta' }
    if (-not $DataDir) { $DataDir=Join-Path $env:LOCALAPPDATA 'PortForwardTUI-Beta' }
    $InstallDir=Resolve-PortsChannelPath $InstallDir; $DataDir=Resolve-PortsChannelPath $DataDir
    $protected=@($workspace,(Resolve-PortsChannelPath (Join-Path $env:LOCALAPPDATA 'Programs\Ports')),(Resolve-PortsChannelPath (Join-Path $env:LOCALAPPDATA 'PortForwardTUI')))
    foreach ($path in @($InstallDir,$DataDir)) { foreach ($stable in $protected) { if (Test-PortsChannelOverlap $path $stable) { throw 'Beta paths must not overlap the stable workspace, program or data paths.' } } }
    if (Test-PortsChannelOverlap $InstallDir $DataDir) { throw 'Beta program and data paths must be separate.' }
    if ($FromDataDir -and $Action -notin @('Plan','Import')) { throw 'FromDataDir is only accepted for explicit Import or its Plan.' }
    if ($FromDataDir) {
        $FromDataDir=Resolve-PortsChannelPath $FromDataDir
        if ((Test-PortsChannelOverlap $FromDataDir $DataDir) -or (Test-PortsChannelOverlap $FromDataDir $InstallDir)) { throw 'Import source must be separate from both beta directories.' }
    }
    $binary=Join-Path $InstallDir 'bin\ports-beta.exe'
    $fragmentDirectory=Resolve-PortsChannelPath (Join-Path $env:LOCALAPPDATA 'Microsoft\Windows Terminal\Fragments\TerminalWorkspace.PortsBeta')
    $command=(ConvertTo-PortsChannelArgument $binary)+' --data-dir '+(ConvertTo-PortsChannelArgument $DataDir)
    $tag=$contract.beta.tag
    $releaseUrl="https://github.com/brant92good/port-forward-tui/releases/download/$tag"
    $installerUrl="https://raw.githubusercontent.com/brant92good/port-forward-tui/$tag/install.ps1"
    $archiveName='ports-x86_64-pc-windows-msvc.zip'
    $result=[ordered]@{channel='beta';action=$Action;version=$Version;qualification=$contract.beta.qualification;install_dir=$InstallDir;data_dir=$DataDir;from_data_dir=$FromDataDir;binary=$binary;fragment_directory=$fragmentDirectory;commandline=$command;caller_integration_revision=$IntegrationRevision;runtime_launched=$false;stable_write_requested=$false}
    $result.leaf_tag=$tag; $result.leaf_source_commit=$contract.beta.source_commit
    $result.expected_archive_sha256=$contract.beta.archive_sha256; $result.expected_binary_sha256=$contract.beta.binary_sha256
    $result.integration_files=[ordered]@{}
    foreach ($relative in @('ports-channel.ps1','scripts/ports-channel-common.ps1','config/ports-channels.json')) { $result.integration_files[$relative]=Get-PortsChannelHash (Join-Path $PSScriptRoot $relative) }
    if ($Action -eq 'Plan') {
        $result.installer_url=$installerUrl; $result.archive_url="$releaseUrl/$archiveName"
        $result.note='Install adds programs only. Import and AddProfile are separate explicit actions. No forward is started.'
    } elseif ($Action -eq 'Status') {
        $result.binary_matches=($contract.beta.qualification -eq 'qualified' -and [IO.File]::Exists($binary) -and (Get-PortsChannelHash $binary) -ceq $contract.beta.binary_sha256)
        $result.data_exists=[IO.Directory]::Exists($DataDir)
        $result.fragment_exists=[IO.File]::Exists((Join-Path $fragmentDirectory 'ports-beta.json'))
        $result.profile_visibility='not_observed'
    } else {
        if ($Action -ne 'RemoveProfile' -and $contract.beta.qualification -ne 'qualified') { throw 'This beta release is pending qualification. No installation, import or profile write was performed.' }
        if (-not $IntegrationRevision) { throw 'Mutation requires the full integration revision for the installation receipt.' }
        switch ($Action) {
            'Install' {
                $stage=Join-Path ([IO.Path]::GetTempPath()) ('workspace-ports-beta-'+[Guid]::NewGuid().ToString('N'))
                [IO.Directory]::CreateDirectory($stage) | Out-Null
                try {
                    foreach ($item in @(@($installerUrl,'install.ps1',$contract.beta.installer_sha256),@("$releaseUrl/$archiveName",$archiveName,$contract.beta.archive_sha256),@("$releaseUrl/release-record.json",'release-record.json',$contract.beta.release_record_sha256))) {
                        $destination=Join-Path $stage $item[1]
                        Get-PortsChannelDownload $item[0] $destination
                        if ((Get-PortsChannelHash $destination) -cne $item[2]) { throw 'Pinned release download checksum mismatch; destination is unchanged.' }
                    }
                    $record=[IO.File]::ReadAllText((Join-Path $stage 'release-record.json')) | ConvertFrom-Json
                    if ($record.schema_version -ne 1 -or $record.version -cne $Version -or $record.channel -cne 'beta' -or $record.tag -cne $tag -or $record.source_commit -cne $contract.beta.source_commit -or $record.artifacts.$archiveName -cne $contract.beta.archive_sha256) { throw 'The frozen release record disagrees with the integration contract.' }
                    $global:LASTEXITCODE=0
                    & (Join-Path $stage 'install.ps1') -Channel beta -Version $Version -InstallDir $InstallDir -Bundle (Join-Path $stage $archiveName) -Sha256 $contract.beta.archive_sha256 -NoPath | ForEach-Object { Write-Verbose $_ }
                    if ($LASTEXITCODE -ne 0) { throw 'The beta installer failed; inspect its result before retrying.' }
                    $binary=Assert-PortsChannelBinary $InstallDir $contract.beta
                    $result.version_output=(Invoke-PortsChannelMetadata $binary @('--version') 10000).Trim()
                    if ($result.version_output -cne ('ports '+$Version)) { throw 'Installed beta returned a different version.' }
                    $result.state='installed_verified'; $result.runtime_launched=$true
                } finally {
                    $full=[IO.Path]::GetFullPath($stage)
                    if ([IO.Path]::GetDirectoryName($full) -cne [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') -or [IO.Path]::GetFileName($full) -notmatch '\Aworkspace-ports-beta-[a-f0-9]{32}\z') { throw 'Unsafe stage cleanup refused.' }
                    Remove-Item -LiteralPath $full -Recurse -Force
                }
            }
            'Import' {
                if (-not $FromDataDir) { throw 'Import requires an explicit FromDataDir.' }
                if (Test-Path -LiteralPath $DataDir) { throw 'Import requires a nonexistent beta destination; existing data is preserved.' }
                $binary=Assert-PortsChannelBinary $InstallDir $contract.beta
                $result.import_result=(Invoke-PortsChannelMetadata $binary @('--data-dir',$DataDir,'import-stable','--from',$FromDataDir,'--json') | ConvertFrom-Json)
                if ($result.import_result.ok -ne $true) { throw 'The metadata import did not report success.' }
                $result.state='metadata_imported'; $result.runtime_launched=$true
            }
            'AddProfile' {
                [void](Assert-PortsChannelBinary $InstallDir $contract.beta)
                $result.state=Update-PortsChannelProfile $fragmentDirectory $command $Action
                $result.fragment_sha256=Get-PortsChannelHash (Join-Path $fragmentDirectory 'ports-beta.json')
                $result.profile_visibility='not_observed; custom menus or disabled fragment sources may hide the profile'
            }
            'RemoveProfile' { $result.state=Update-PortsChannelProfile $fragmentDirectory $command $Action }
        }
    }
}
if ($Json) { $result | ConvertTo-Json -Depth 12 }
else { $result | Format-List }
