param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$fixture=Join-Path $root ('artifacts\files-channel-test-'+[Guid]::NewGuid().ToString('N'))
$script:count=0
function Check([bool]$Value,[string]$Name) { if (-not $Value) { throw "FAIL: $Name" }; $script:count++; Write-Output "PASS: $Name" }
function Text([string]$Path,[string]$Value) { [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path)) | Out-Null; [IO.File]::WriteAllText($Path,$Value,[Text.UTF8Encoding]::new($false)) }
function Expect-Error([scriptblock]$Body,[string]$Pattern,[string]$Name) {
    $message=''; try { & $Body | Out-Null } catch { $message=$_.Exception.Message }
    if ($message -notmatch $Pattern) { throw "FAIL: $Name; expected $Pattern; observed: $message" }
    Check $true $Name
}
function Run-Profile([string]$Command) {
    $shell=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $prefix=(ConvertTo-FilesChannelArgument $shell)+' '
    if (-not $Command.StartsWith($prefix,[StringComparison]::Ordinal)) { throw 'Unexpected generated launcher.' }
    $start=[Diagnostics.ProcessStartInfo]::new(); $start.FileName=$shell; $start.Arguments=$Command.Substring($prefix.Length)
    # This child launches only our inert winexe, never a TUI or SSH process.
    $start.UseShellExecute=$false; $start.CreateNoWindow=$true; $start.RedirectStandardOutput=$true; $start.RedirectStandardError=$true
    $process=[Diagnostics.Process]::new(); $process.StartInfo=$start; $started=$false
    try {
        [void]$process.Start(); $started=$true
        $out=$process.StandardOutput.ReadToEndAsync(); $err=$process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(10000)) { throw 'Owned profile fixture timed out.' }
        if (-not $out.Wait(1000) -or -not $err.Wait(1000)) { throw 'Owned profile output did not close.' }
        return $process.ExitCode
    } finally {
        try { if ($started -and -not $process.HasExited) { $process.Kill(); if (-not $process.WaitForExit(3000)) { throw 'Owned profile fixture did not exit after cleanup.' } } }
        finally { $process.Dispose() }
    }
}
$names=@('LOCALAPPDATA','SSH_FILES_BIN','SSH_FILES_BETA_VERSION','SSH_FILES_BETA_INSTALL_DIR','SSH_FILES_BETA_BINARY','SSH_FILES_BETA_SHA256','FILES_CHANNEL_FIXTURE','FILES_CHANNEL_MODE','FILES_CHANNEL_KEEP')
$saved=@{}; foreach ($name in $names) { $saved[$name]=[Environment]::GetEnvironmentVariable($name) }
try {
    $workspace=Join-Path $fixture 'workspace'
    foreach ($relative in @('files-channel.ps1','scripts/files-channel-common.ps1','config/files-channels.json')) {
        $destination=Join-Path $workspace $relative
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)) | Out-Null
        Copy-Item -LiteralPath (Join-Path $root $relative) -Destination $destination
    }
    . (Join-Path $workspace 'scripts/files-channel-common.ps1')
    $helper=Join-Path $workspace 'files-channel.ps1'; $common=Join-Path $workspace 'scripts/files-channel-common.ps1'; $contractPath=Join-Path $workspace 'config/files-channels.json'
    function Pins { return @{IntegrationRevision=('a'*40);SourceSha256=(Get-FilesChannelHash $helper);CommonSha256=(Get-FilesChannelHash $common);ContractSha256=(Get-FilesChannelHash $contractPath)} }
    function Snapshot { return ((Get-ChildItem -LiteralPath $fixture -Recurse -File | Sort-Object FullName | ForEach-Object { $_.FullName+' '+(Get-FilesChannelHash $_.FullName) }) -join "`n") }
    $env:LOCALAPPDATA=Join-Path $fixture 'local'; $env:FILES_CHANNEL_FIXTURE=$fixture; $env:FILES_CHANNEL_KEEP='synthetic inherited value'
    $env:SSH_FILES_BIN='existing caller override'; $env:SSH_FILES_BETA_VERSION='999'
    $env:SSH_FILES_BETA_INSTALL_DIR=Join-Path $fixture 'never'; $env:SSH_FILES_BETA_BINARY='bad inherited source'; $env:SSH_FILES_BETA_SHA256='bad inherited hash'
    $shippingContractHash=Get-FilesChannelHash (Join-Path $root 'config/files-channels.json')
    $contract=(Read-FilesChannelUtf8 $contractPath) | ConvertFrom-Json; $version=$contract.beta.version
    # The shipping contract will become qualified after release. Exercise the
    # pending refusal cases only in this owned copy, independent of that state.
    $contract.beta.qualification='pending'
    foreach ($field in @('source_commit','installer_sha256','binary_sha256','sidecar_sha256','release_record_sha256')) { $contract.beta.$field=$null }
    Text $contractPath ($contract | ConvertTo-Json -Depth 8)
    $argsBase=@{Channel='beta';Version=$version;Json=$true;WorkspaceRoot=$workspace}
    $global:FilesFixtureDownloads=[Collections.Generic.List[string]]::new(); $global:FilesFixtureServed=@{}
    function Invoke-WebRequest {
        param([switch]$UseBasicParsing,[string]$Uri,[string]$OutFile,[int]$TimeoutSec,[string]$ErrorAction)
        $global:FilesFixtureDownloads.Add($Uri)
        if (-not $global:FilesFixtureServed.ContainsKey($Uri)) { throw "Unexpected network request: $Uri" }
        [IO.File]::Copy($global:FilesFixtureServed[$Uri],$OutFile)
    }
    $before=Snapshot
    $plan=(& $helper @argsBase | Out-String) | ConvertFrom-Json
    $status=(& $helper @argsBase -Action Status | Out-String) | ConvertFrom-Json
    Check ((Snapshot) -ceq $before -and $global:FilesFixtureDownloads.Count -eq 0 -and -not $plan.runtime_launched -and -not $status.runtime_launched) 'pending Plan and Status write no files and make no downloads'
    Check (-not $plan.catalog_available -and -not $plan.selector_matches -and $plan.qualification -eq 'pending') 'missing catalog and selector are reported without blocking Plan'
    Check ($plan.install_dir -ceq (Join-Path $env:LOCALAPPDATA 'Programs\SSHFilesBeta')) 'polluted leaf environment cannot choose helper paths'
    $pins=Pins
    Expect-Error { & $helper @argsBase @pins -Action Install } 'pending qualification' 'pending release cannot install'
    Expect-Error { & $helper @argsBase @pins -Action AddProfile } 'pending qualification' 'pending release cannot create profile'
    Expect-Error { & $helper @argsBase -Action Install } 'all three source hashes' 'mutations require reviewed source hashes'
    Expect-Error { & $helper -Channel beta -Version latest } 'exact beta Version' 'moving version refused'
    Expect-Error { & $helper -Channel stable -Action Install @pins } 'never modifies' 'stable mutation refused'
    Expect-Error { & $helper @argsBase -IntegrationRevision ('a'*39) } 'full lowercase commit' 'short source pin refused'
    Expect-Error { & $helper @argsBase -SourceSha256 ('a'*64) } 'checksum mismatch' 'partial source hash set refused'
    $commonText=Read-FilesChannelUtf8 $common
    Text $common ($commonText+"`n[IO.File]::WriteAllText((Join-Path `$env:FILES_CHANNEL_FIXTURE 'common.executed'),'bad')`n")
    Expect-Error { & $helper @argsBase @pins } 'checksum mismatch' 'common hash checked before changed code executes'
    Check (-not [IO.File]::Exists((Join-Path $fixture 'common.executed'))) 'unreviewed common code never executes'
    Text $common $commonText
    $contractText=Read-FilesChannelUtf8 $contractPath; Text $contractPath ($contractText+' ')
    Expect-Error { & $helper @argsBase @pins } 'checksum mismatch' 'contract source pin detects drift'
    Text $contractPath $contractText
    foreach ($path in @($workspace,($workspace+'\nested'),(Join-Path $env:LOCALAPPDATA 'Programs\SSHFiles'))) { Expect-Error { & $helper @argsBase -InstallDir $path } 'overlap' 'stable path overlap refused' }
    Expect-Error { & $helper @argsBase -InstallDir ($workspace+':stream') } 'streams' 'alternate stream refused'
    Expect-Error { & $helper @argsBase -InstallDir ($workspace+'\..\other') } 'traversal|aliases' 'dot path alias refused'
    $long=Join-Path $fixture 'Owned long directory for alias'; [IO.Directory]::CreateDirectory($long) | Out-Null
    $fso=New-Object -ComObject Scripting.FileSystemObject
    try { $short=$fso.GetFolder($long).ShortPath } finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($fso) }
    $resolved=Resolve-FilesChannelPath $short
    Write-Output "8.3 fixture: long=[$long]; short=[$short]; resolved=[$resolved]"
    if ($short.Equals($long,[StringComparison]::OrdinalIgnoreCase)) {
        Write-Output 'SKIP: volume does not expose an 8.3 alias for the owned long directory'
    } else {
        Check ($resolved -ceq $long) 'actual 8.3 alias resolves to stored long directory'
    }
    $junction=Join-Path $fixture 'owned-junction'; New-Item -ItemType Junction -Path $junction -Target $long | Out-Null
    Expect-Error { Resolve-FilesChannelPath ($junction+'\missing') } 'reparse' 'junction ancestor refused'
    [IO.Directory]::Delete($junction)
    $source=@'
using System;
using System.IO;
class FilesFixture {
    static int Main(string[] args) {
        string root=Environment.GetEnvironmentVariable("FILES_CHANNEL_FIXTURE");
        File.WriteAllLines(Path.Combine(root,"child.argv"),args);
        File.WriteAllLines(Path.Combine(root,"child.env"),new[]{Environment.CurrentDirectory,Environment.GetEnvironmentVariable("SSH_FILES_BIN"),Environment.GetEnvironmentVariable("FILES_CHANNEL_KEEP")});
        return Environment.GetEnvironmentVariable("FILES_CHANNEL_MODE")=="error" ? 7 : 0;
    }
}
'@
    Text (Join-Path $fixture 'child.cs') $source; $fake=Join-Path $fixture 'child.exe'
    & (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe') /nologo /target:winexe ('/out:'+$fake) (Join-Path $fixture 'child.cs')
    if ($LASTEXITCODE -ne 0) { throw 'Owned child fixture did not compile.' }
    $installer=Join-Path $fixture 'installer.ps1'
    Text $installer @'
param([string]$Version,[string]$InstallDir,[string]$WorkspaceRoot,[string]$Binary,[string]$Sha256)
if ($Version -cne '0.4.0-beta.1' -or -not [IO.File]::Exists($Binary) -or $Binary -ceq $env:SSH_FILES_BETA_BINARY -or $Sha256 -cnotmatch '\A[a-f0-9]{64}\z' -or -not $WorkspaceRoot) { throw 'Incorrect leaf installer arguments.' }
[IO.File]::WriteAllText((Join-Path $env:FILES_CHANNEL_FIXTURE 'installer.called'),$Binary)
if ($env:FILES_CHANNEL_MODE -eq 'install-error') { throw 'owned installer failure' }
[IO.Directory]::CreateDirectory((Join-Path $InstallDir 'bin')) | Out-Null
[IO.File]::Copy($Binary,(Join-Path $InstallDir 'bin\ssh-files-beta.exe'),$true)
[IO.File]::WriteAllText((Join-Path $InstallDir '.ssh-files-beta-installer'),"ssh-files-beta`n")
[IO.File]::WriteAllText((Join-Path $InstallDir 'version'),$Version+"`n")
'@
    $asset='ssh-files-x86_64-pc-windows-msvc.exe'; $sidecar=Join-Path $fixture ($asset+'.sha256'); $recordPath=Join-Path $fixture 'release-record.json'
    $contract.beta.qualification='qualified'; $contract.beta.source_commit='b'*40
    $contract.beta.binary_sha256=Get-FilesChannelHash $fake; $contract.beta.installer_sha256=Get-FilesChannelHash $installer; $contract.stable.selector_sha256=Get-FilesChannelHash $fake
    Text $sidecar ($contract.beta.binary_sha256+'  '+$asset+"`n"); $contract.beta.sidecar_sha256=Get-FilesChannelHash $sidecar
    $record=@{schema_version=1;version=$version;tag=('v'+$version);channel='beta';source_commit=('b'*40);stable_default='0.3.0';artifacts=@{};installers=@{'install-beta.ps1'=$contract.beta.installer_sha256}}
    $record.artifacts[$asset]=$contract.beta.binary_sha256
    Text $recordPath ($record | ConvertTo-Json -Depth 8); $contract.beta.release_record_sha256=Get-FilesChannelHash $recordPath
    Text $contractPath ($contract | ConvertTo-Json -Depth 8); $pins=Pins
    $release='https://github.com/brant92good/ssh-files/releases/download/v'+$version
    $global:FilesFixtureServed['https://raw.githubusercontent.com/brant92good/ssh-files/v'+$version+'/install-beta.ps1']=$installer
    $global:FilesFixtureServed[$release+'/'+$asset]=$fake; $global:FilesFixtureServed[$release+'/'+$asset+'.sha256']=$sidecar; $global:FilesFixtureServed[$release+'/release-record.json']=$recordPath
    $sidecarText=Read-FilesChannelUtf8 $sidecar; Text $sidecar 'tampered'
    Expect-Error { & $helper @argsBase @pins -Action Install } 'checksum mismatch' 'tampered download refused before installer'
    Check (-not [IO.File]::Exists((Join-Path $fixture 'installer.called'))) 'failed release gate invokes no installer'
    Text $sidecar $sidecarText
    $recordText=Read-FilesChannelUtf8 $recordPath; $record.source_commit='c'*40; Text $recordPath ($record | ConvertTo-Json -Depth 8)
    $contract.beta.release_record_sha256=Get-FilesChannelHash $recordPath; Text $contractPath ($contract | ConvertTo-Json -Depth 8); $pins=Pins
    Expect-Error { & $helper @argsBase @pins -Action Install } 'record disagrees' 'hash-valid wrong-source record refused'
    Text $recordPath $recordText; $contract.beta.release_record_sha256=Get-FilesChannelHash $recordPath; Text $contractPath ($contract | ConvertTo-Json -Depth 8); $pins=Pins
    $env:FILES_CHANNEL_MODE='install-error'
    Expect-Error { & $helper @argsBase @pins -Action Install } 'owned installer failure' 'installer failure propagates without retry'
    $env:FILES_CHANNEL_MODE=''
    $installed=(& $helper @argsBase @pins -Action Install | Out-String) | ConvertFrom-Json
    Check ($installed.state -ceq 'installed_verified' -and -not $installed.catalog_available -and -not $installed.selector_matches) 'Install succeeds without host catalog or installed selector'
    Check (-not [IO.File]::Exists((Join-Path $fixture 'child.argv'))) 'setup does not launch selector or SSH'
    Expect-Error { & $helper @argsBase @pins -Action AddProfile } 'existing Catalog' 'profile requires existing catalog'
    $catalog=Join-Path $fixture ('catalog ; $literal `& '+[char]0x958b+'.json'); Text $catalog '{"version":2,"machines":[]}'
    $stateDir=Join-Path $fixture 'missing state directory'; $local=Join-Path $fixture ('local ; $literal `& '+[char]0x958b); [IO.Directory]::CreateDirectory($local) | Out-Null
    $interactive=@{Channel='beta';Version=$version;WorkspaceRoot=$workspace;Catalog=$catalog;StateDir=$stateDir;LocalDirectory=$local}
    Expect-Error { & $helper @interactive @pins -Action Launch } 'selector checksum' 'missing selector refuses before launch'
    [IO.Directory]::CreateDirectory((Join-Path $workspace 'bin')) | Out-Null; [IO.File]::Copy($fake,(Join-Path $workspace 'bin\ssh-sessions.exe'))
    $before=Snapshot
    & $helper @argsBase @pins -Action Plan | Out-Null
    & $helper @argsBase @pins -Action Status | Out-Null
    Check ((Snapshot) -ceq $before -and -not [IO.File]::Exists((Join-Path $fixture 'child.argv'))) 'qualified Plan and Status do not execute an available native selector'
    $held=[IO.File]::Open($catalog,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    try { Expect-Error { & $helper @interactive @pins -Action Launch } 'another process|being used|OpenRead' 'unreadable catalog refuses before selector launch' } finally { $held.Dispose() }
    $before=Snapshot
    & $helper @interactive @pins -Action Launch
    $argv=[IO.File]::ReadAllLines((Join-Path $fixture 'child.argv')); $environment=[IO.File]::ReadAllLines((Join-Path $fixture 'child.env'))
    Check (($argv -join '|') -ceq (@('--catalog',$catalog,'--state-dir',$stateDir,'files') -join '|')) 'inert native child receives exact Unicode metacharacter chooser argv'
    Check ($environment[0] -ceq $local -and $environment[1] -ceq $installed.binary -and $environment[2] -ceq $env:FILES_CHANNEL_KEEP) 'child cwd and other environment preserved with only Files override'
    Check ($env:SSH_FILES_BIN -ceq 'existing caller override' -and -not [IO.Directory]::Exists($stateDir)) 'launch leaves parent override and absent state directory untouched'
    [IO.File]::Delete((Join-Path $fixture 'child.argv')); [IO.File]::Delete((Join-Path $fixture 'child.env'))
    Check ((Snapshot) -ceq $before) 'launch wrapper preserves all source catalog and installation files'
    $env:FILES_CHANNEL_MODE='error'
    Expect-Error { & $helper @interactive @pins -Action Launch } 'exit 7.*no fallback' 'nonzero child exit propagates without fallback'
    Check ($env:SSH_FILES_BIN -ceq 'existing caller override') 'failed child leaves parent environment unchanged'
    $env:FILES_CHANNEL_MODE=''
    $selector=Join-Path $workspace 'bin\ssh-sessions.exe'; $selectorBytes=[IO.File]::ReadAllBytes($selector); [IO.File]::WriteAllBytes($selector,[byte[]](1,2,3))
    Expect-Error { & $helper @interactive @pins -Action Launch } 'selector checksum' 'tampered selector refuses'
    [IO.File]::WriteAllBytes($selector,$selectorBytes)
    $betaBytes=[IO.File]::ReadAllBytes($installed.binary); [IO.File]::WriteAllBytes($installed.binary,[byte[]](4,5,6))
    Expect-Error { & $helper @interactive @pins -Action Launch } 'digest mismatch' 'tampered beta refuses'
    [IO.File]::WriteAllBytes($installed.binary,$betaBytes)
    $profile=(& $helper @interactive @pins -Action AddProfile -Json | Out-String) | ConvertFrom-Json
    Check ($profile.state -eq 'added' -and $profile.profile_visibility -match 'not_observed') 'owned fragment created without menu visibility claim'
    $fragment=Join-Path $profile.fragment_directory 'files-beta.json'; $fragmentHash=Get-FilesChannelHash $fragment; $parsed=(Read-FilesChannelUtf8 $fragment) | ConvertFrom-Json
    Check ($parsed.profiles[0].commandline.Contains($pins.SourceSha256) -and $parsed.profiles[0].commandline.Contains($pins.CommonSha256) -and $parsed.profiles[0].commandline.Contains($pins.ContractSha256)) 'profile pins launcher common and contract source'
    Check ((Run-Profile $parsed.profiles[0].commandline) -eq 0) 'generated profile command runs exact inert selector without a window'
    Check (([IO.File]::ReadAllLines((Join-Path $fixture 'child.argv')) -join '|') -ceq (@('--catalog',$catalog,'--state-dir',$stateDir,'files') -join '|')) 'generated profile retains literal catalog and state arguments'
    [IO.File]::Delete((Join-Path $fixture 'child.argv'))
    Text $common ($commonText+"`nthrow 'changed common must not execute'`n")
    Check ((Run-Profile $parsed.profiles[0].commandline) -ne 0 -and -not [IO.File]::Exists((Join-Path $fixture 'child.argv'))) 'installed profile rejects later source drift before selector starts'
    Text $common $commonText
    $again=(& $helper @interactive @pins -Action AddProfile -Json | Out-String) | ConvertFrom-Json
    Check ($again.state -ceq 'unchanged' -and (Get-FilesChannelHash $fragment) -ceq $fragmentHash) 'repeat preserves original profile bytes'
    $opposite=if ($PSVersionTable.PSVersion.Major -eq 5) { (Get-Command pwsh.exe).Source } else { Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe' }
    $parameters=@('-NoProfile','-ExecutionPolicy','Bypass','-File',$helper,'-Channel','beta','-Version',$version,'-WorkspaceRoot',$workspace,'-Catalog',$catalog,'-StateDir',$stateDir,'-LocalDirectory',$local,'-Action','AddProfile','-Json')
    foreach ($key in $pins.Keys) { $parameters+=@(('-'+$key),$pins[$key]) }
    $cross=(& $opposite @parameters | Out-String) | ConvertFrom-Json
    Check ($LASTEXITCODE -eq 0 -and $cross.state -ceq 'unchanged' -and (Get-FilesChannelHash $fragment) -ceq $fragmentHash) 'opposite PowerShell version preserves owned profile bytes'
    $original=Read-FilesChannelUtf8 $fragment; Text $fragment ($original+' ')
    Expect-Error { & $helper @argsBase @pins -Action RemoveProfile } 'changed outside' 'edited fragment retained on removal'
    Text $fragment $original
    $removed=(& $helper @argsBase @pins -Action RemoveProfile | Out-String) | ConvertFrom-Json
    Check ($removed.state -ceq 'removed' -and -not [IO.File]::Exists($fragment)) 'owned profile removal needs no catalog'
    Check ($env:SSH_FILES_BETA_VERSION -ceq '999' -and $env:SSH_FILES_BIN -ceq 'existing caller override') 'helper preserves caller overrides'
    Check ((Get-FilesChannelHash (Join-Path $root 'config/files-channels.json')) -ceq $shippingContractHash) 'fixture pending and qualified cases preserve the source release contract'
    Write-Output "PASS: $script:count Files helper cases"
} finally {
    foreach ($name in $names) { if ($null -eq $saved[$name]) { Remove-Item -LiteralPath ('Env:\'+$name) -ErrorAction SilentlyContinue } else { [Environment]::SetEnvironmentVariable($name,$saved[$name]) } }
    $full=[IO.Path]::GetFullPath($fixture)
    if ([IO.Path]::GetDirectoryName($full) -cne (Join-Path $root 'artifacts') -or [IO.Path]::GetFileName($full) -notmatch '\Afiles-channel-test-[a-f0-9]{32}\z') { throw 'Unsafe fixture cleanup refused.' }
    if ([IO.Directory]::Exists($full)) { Remove-Item -LiteralPath $full -Recurse -Force }
}
