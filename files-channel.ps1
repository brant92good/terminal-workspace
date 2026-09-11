param(
    [ValidateSet('stable','beta')][string]$Channel='stable',
    [ValidateSet('Plan','Status','Install','AddProfile','RemoveProfile','Launch')][string]$Action='Plan',
    [string]$Version='', [string]$WorkspaceRoot=$PSScriptRoot, [string]$InstallDir='',
    [string]$Catalog='', [string]$StateDir='', [string]$LocalDirectory='',
    [string]$IntegrationRevision='', [string]$SourceSha256='', [string]$CommonSha256='', [string]$ContractSha256='',
    [switch]$Json
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'This optional Files helper is Windows-only.' }
# Validate the complete expected source set BEFORE executing the common script.
# The caller establishes that these reviewed bytes belong to IntegrationRevision;
# runtime does not invoke Git or modify its index. This is not a same-user sandbox.
$readOnly=$Action -in @('Plan','Status')
if ($IntegrationRevision -and $IntegrationRevision -cnotmatch '\A[a-f0-9]{40}\z') { throw 'IntegrationRevision must be a full lowercase commit hash.' }
$sourceFiles=@($PSCommandPath,(Join-Path $PSScriptRoot 'scripts\files-channel-common.ps1'),(Join-Path $PSScriptRoot 'config\files-channels.json'))
$expected=@($SourceSha256,$CommonSha256,$ContractSha256)
$hasPins=@($expected | Where-Object { $_ }).Count -gt 0
if (-not $readOnly -and (-not $IntegrationRevision -or -not $hasPins)) { throw 'Mutation/Launch requires a reviewed integration revision and all three source hashes.' }
$observed=@()
for ($i=0;$i -lt $sourceFiles.Count;$i++) {
    $inspect=$sourceFiles[$i]
    while ($inspect) {
        if ([IO.File]::GetAttributes($inspect) -band [IO.FileAttributes]::ReparsePoint) { throw 'Files helper source must not traverse reparse points.' }
        $inspect=[IO.Path]::GetDirectoryName($inspect)
    }
    $algorithm=[Security.Cryptography.SHA256]::Create(); $stream=$null
    try { $stream=[IO.File]::OpenRead($sourceFiles[$i]); $digest=[BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { if ($stream) { $stream.Dispose() }; $algorithm.Dispose() }
    if ($hasPins -and ($expected[$i] -cnotmatch '\A[a-f0-9]{64}\z' -or $digest -cne $expected[$i])) { throw 'Reviewed Files helper source checksum mismatch; no action performed.' }
    $observed+=$digest
}
. $sourceFiles[1]
$contract=Read-FilesChannelContract $sourceFiles[2]
$workspace=Resolve-FilesChannelPath $WorkspaceRoot
if ($Channel -eq 'stable') {
    if (-not $readOnly) { throw 'This helper never modifies or launches stable. Use the ordinary Workspace entry.' }
    if ($Version -and $Version -cne $contract.stable.version) { throw 'Stable Files remains 0.3.0.' }
    $binary=Join-Path $workspace 'bin\ssh-files.exe'
    $result=[ordered]@{channel='stable';action=$Action;version=$contract.stable.version;binary=$binary;runtime_launched=$false;stable_write_requested=$false}
    if ($Action -eq 'Status') { $result.binary_matches=([IO.File]::Exists($binary) -and (Get-FilesChannelHash $binary) -ceq $contract.stable.binary_sha256) }
} else {
    if (-not $Version -or $Version -cne $contract.beta.version) { throw 'Select the exact beta Version recorded by this integration.' }
    if (-not $InstallDir) { $InstallDir=Join-Path $env:LOCALAPPDATA 'Programs\SSHFilesBeta' }
    $install=Resolve-FilesChannelPath $InstallDir
    foreach ($protected in @($workspace,(Resolve-FilesChannelPath (Join-Path $env:LOCALAPPDATA 'Programs\SSHFiles')),(Resolve-FilesChannelPath (Join-Path $env:LOCALAPPDATA 'Programs\TerminalWorkspace')))) {
        if (Test-FilesChannelOverlap $install $protected) { throw 'Beta install must not overlap the stable Workspace or Files directories.' }
    }
    $catalogPath=if ($Catalog) { Resolve-FilesChannelPath $Catalog } else { '' }
    $statePath=if ($StateDir) { Resolve-FilesChannelPath $StateDir } else { '' }
    $localPath=if ($LocalDirectory) { Resolve-FilesChannelPath $LocalDirectory } else { Resolve-FilesChannelPath ([Environment]::GetFolderPath('UserProfile')) }
    $selector=Resolve-FilesChannelPath (Join-Path $workspace 'bin\ssh-sessions.exe')
    $binary=Resolve-FilesChannelPath (Join-Path $install 'bin\ssh-files-beta.exe')
    $fragmentDir=Resolve-FilesChannelPath (Join-Path $env:LOCALAPPDATA 'Microsoft\Windows Terminal\Fragments\TerminalWorkspace.FilesBeta')
    $result=[ordered]@{channel='beta';action=$Action;version=$Version;qualification=$contract.beta.qualification;install_dir=$install;binary=$binary;selector=$selector;catalog=$catalogPath;state_dir=$statePath;local_directory=$localPath;fragment_directory=$fragmentDir;caller_integration_revision=$IntegrationRevision;runtime_launched=$false;stable_write_requested=$false;source_sha256=$observed[0];common_sha256=$observed[1];contract_sha256=$observed[2]}
    $result.catalog_available=($catalogPath -and [IO.File]::Exists($catalogPath)) -as [bool]
    $result.local_directory_available=[IO.Directory]::Exists($localPath)
    $result.selector_matches=([IO.File]::Exists($selector) -and (Get-FilesChannelHash $selector) -ceq $contract.stable.selector_sha256)
    $result.leaf_tag=$contract.beta.tag; $result.leaf_source_commit=$contract.beta.source_commit
    $result.expected_binary_sha256=$contract.beta.binary_sha256
    $releaseUrl='https://github.com/brant92good/ssh-files/releases/download/'+$contract.beta.tag
    $installerUrl='https://raw.githubusercontent.com/brant92good/ssh-files/'+$contract.beta.tag+'/install-beta.ps1'
    $asset='ssh-files-x86_64-pc-windows-msvc.exe'
    if ($readOnly) {
        $result.installer_url=$installerUrl; $result.binary_url=$releaseUrl+'/'+$asset
        $result.note='Install needs no catalog. AddProfile/Launch need an existing catalog and verified selector; no new catalog or connection is created by setup.'
        if ($Action -eq 'Status') {
            $result.binary_matches=($contract.beta.qualification -eq 'qualified' -and [IO.File]::Exists($binary) -and (Get-FilesChannelHash $binary) -ceq $contract.beta.binary_sha256)
            $result.fragment_exists=[IO.File]::Exists((Join-Path $fragmentDir 'files-beta.json'))
            $result.profile_visibility='not_observed'
        }
    } else {
        if ($Action -ne 'RemoveProfile' -and $contract.beta.qualification -ne 'qualified') { throw 'Files beta is pending qualification; no installation, profile or launch action performed.' }
        if ($Action -in @('AddProfile','Launch')) {
            if (-not $result.catalog_available) { throw 'An existing Catalog is required for AddProfile/Launch.' }
            $catalogHandle=[IO.File]::OpenRead($catalogPath); $catalogHandle.Dispose()
            if (-not $result.local_directory_available) { throw 'An existing local directory is required for AddProfile/Launch.' }
            if (-not $result.selector_matches) { throw 'Stable SSH Sessions selector checksum mismatch or missing binary.' }
            $binary=Assert-FilesChannelBinary $install $contract.beta
        }
        switch ($Action) {
            'Install' {
                $stage=Join-Path ([IO.Path]::GetTempPath()) ('workspace-files-beta-'+[Guid]::NewGuid().ToString('N'))
                [IO.Directory]::CreateDirectory($stage) | Out-Null
                try {
                    foreach ($item in @(@($installerUrl,'install-beta.ps1',$contract.beta.installer_sha256),@("$releaseUrl/$asset",$asset,$contract.beta.binary_sha256),@("$releaseUrl/$asset.sha256",($asset+'.sha256'),$contract.beta.sidecar_sha256),@("$releaseUrl/release-record.json",'release-record.json',$contract.beta.release_record_sha256))) {
                        $destination=Join-Path $stage $item[1]
                        Get-FilesChannelDownload $item[0] $destination
                        if ((Get-FilesChannelHash $destination) -cne $item[2]) { throw 'Pinned Files release download checksum mismatch; install destination unchanged.' }
                    }
                    if ((Read-FilesChannelUtf8 (Join-Path $stage ($asset+'.sha256'))).TrimEnd("`r","`n") -cne ($contract.beta.binary_sha256+'  '+$asset)) { throw 'Invalid exact Files checksum sidecar.' }
                    $record=(Read-FilesChannelUtf8 (Join-Path $stage 'release-record.json')) | ConvertFrom-Json
                    if ($record.schema_version -ne 1 -or $record.version -cne $Version -or $record.tag -cne $contract.beta.tag -or $record.channel -cne 'beta' -or
                        $record.source_commit -cne $contract.beta.source_commit -or $record.stable_default -cne '0.3.0' -or
                        $record.artifacts.$asset -cne $contract.beta.binary_sha256 -or $record.installers.'install-beta.ps1' -cne $contract.beta.installer_sha256) { throw 'Frozen Files release record disagrees with integration contract.' }
                    $global:LASTEXITCODE=0
                    & (Join-Path $stage 'install-beta.ps1') -Version $Version -InstallDir $install -WorkspaceRoot $workspace -Binary (Join-Path $stage $asset) -Sha256 $contract.beta.binary_sha256 | ForEach-Object { Write-Verbose $_ }
                    if ($LASTEXITCODE -ne 0) { throw 'Files beta installer failed; inspect its result before retrying.' }
                    $result.binary=Assert-FilesChannelBinary $install $contract.beta
                    $result.runtime_launched=$true
                    $result.state='installed_verified'; $result.metadata_execution='leaf installer performs its bounded version check; no chooser launched'
                } finally {
                    $full=[IO.Path]::GetFullPath($stage)
                    if ([IO.Path]::GetDirectoryName($full) -cne [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') -or [IO.Path]::GetFileName($full) -notmatch '\Aworkspace-files-beta-[a-f0-9]{32}\z') { throw 'Unsafe Files stage cleanup refused.' }
                    Remove-Item -LiteralPath $full -Recurse -Force
                }
            }
            'AddProfile' {
                $sourceRoot=Resolve-FilesChannelPath $PSScriptRoot
                if (Test-FilesChannelOverlap $sourceRoot (Resolve-FilesChannelPath ([IO.Path]::GetTempPath()))) { throw 'Profile requires a persistent source checkout outside temporary storage.' }
                $shell=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
                if (-not [IO.File]::Exists($shell)) { throw 'Windows PowerShell is unavailable for the persistent launcher.' }
                $launchArgs=@('-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-Channel','beta','-Action','Launch','-Version',$Version,'-WorkspaceRoot',$workspace,'-InstallDir',$install,'-Catalog',$catalogPath,'-LocalDirectory',$localPath,'-IntegrationRevision',$IntegrationRevision,'-SourceSha256',$observed[0],'-CommonSha256',$observed[1],'-ContractSha256',$observed[2])
                if ($statePath) { $launchArgs+=@('-StateDir',$statePath) }
                $command=(ConvertTo-FilesChannelArgument $shell)+' '+(($launchArgs | ForEach-Object { ConvertTo-FilesChannelArgument $_ }) -join ' ')
                $result.state=Update-FilesChannelProfile $fragmentDir $command $localPath $Action
                $result.commandline=$command; $result.fragment_sha256=Get-FilesChannelHash (Join-Path $fragmentDir 'files-beta.json')
                $result.profile_visibility='not_observed; custom menus or disabled fragment sources may hide it'
            }
            'RemoveProfile' { $result.state=Update-FilesChannelProfile $fragmentDir '' '' $Action }
            'Launch' {
                if ($Json) { throw 'Launch is interactive; use Plan/Status for JSON.' }
                Start-FilesChannelChooser $selector $binary $catalogPath $statePath $localPath
                $result.runtime_launched=$true; $result.state='chooser_closed'
            }
        }
    }
}
if ($Json) { $result | ConvertTo-Json -Depth 8 } elseif ($Action -ne 'Launch') { $result | Format-List }
