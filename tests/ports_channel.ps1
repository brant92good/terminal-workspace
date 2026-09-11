param()
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$fixture=Join-Path ([IO.Path]::GetTempPath()) ('ports-channel-test-'+[Guid]::NewGuid().ToString('N'))
$utf8=[Text.UTF8Encoding]::new($false)
$script:count=0
function Check([bool]$Value,[string]$Name) { if (-not $Value) { throw "FAIL: $Name" }; $script:count++; Write-Output "PASS: $Name" }
function Text([string]$Path,[string]$Value) { [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path)) | Out-Null; [IO.File]::WriteAllText($Path,$Value,$utf8) }
function Expect-Error([scriptblock]$Body,[string]$Pattern,[string]$Name) {
    $message=''; try { & $Body | Out-Null } catch { $message=$_.Exception.Message }
    if ($message -notmatch $Pattern) { throw "FAIL: $Name; expected $Pattern; observed: $message" }
    Check $true $Name
}
$savedLocal=$env:LOCALAPPDATA; $savedBundle=$env:PORTS_BUNDLE; $savedVersion=$env:PORTS_VERSION; $savedInstall=$env:PORTS_INSTALL_DIR
$savedFixture=$env:PORTS_CHANNEL_FIXTURE; $savedMode=$env:PORTS_CHANNEL_MODE
try {
    $workspace=Join-Path $fixture 'workspace'; [IO.Directory]::CreateDirectory($workspace) | Out-Null
    foreach ($relative in @('ports-channel.ps1','bootstrap-ports.ps1','scripts/ports-channel-common.ps1','config/ports-channels.json')) {
        $destination=Join-Path $workspace $relative
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)) | Out-Null
        Copy-Item -LiteralPath (Join-Path $root $relative) -Destination $destination
    }
    . (Join-Path $workspace 'scripts/ports-channel-common.ps1')
    $env:LOCALAPPDATA=Join-Path $fixture 'local'; $env:PORTS_CHANNEL_FIXTURE=$fixture
    $env:PORTS_BUNDLE='https://invalid.test/never'; $env:PORTS_VERSION='999'; $env:PORTS_INSTALL_DIR=Join-Path $fixture 'never'
    $helper=Join-Path $workspace 'ports-channel.ps1'; $contractPath=Join-Path $workspace 'config/ports-channels.json'
    $contract=Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
    # Exercise pending refusal independently of the checked-in release state.
    $contract.beta.qualification='pending'
    foreach ($field in @('source_commit','installer_sha256','archive_sha256','binary_sha256','release_record_sha256')) { $contract.beta.$field=$null }
    Text $contractPath ($contract | ConvertTo-Json -Depth 7)
    $version=$contract.beta.version; $revision='a'*40
    $arguments=@{Channel='beta';Version=$version;IntegrationRevision=$revision;Json=$true}
    $global:PortsChannelFixtureDownloads=[Collections.Generic.List[string]]::new()
    $global:PortsChannelFixtureServed=@{}
    function Invoke-WebRequest {
        param([switch]$UseBasicParsing,[string]$Uri,[string]$OutFile,[int]$TimeoutSec,[string]$ErrorAction)
        $global:PortsChannelFixtureDownloads.Add($Uri)
        if (-not $global:PortsChannelFixtureServed.ContainsKey($Uri)) { throw "Unexpected fixture network request: $Uri" }
        [IO.File]::Copy($global:PortsChannelFixtureServed[$Uri],$OutFile)
    }
    $before=@(Get-ChildItem -LiteralPath $fixture -Recurse -File).Count
    $plan=(& $helper @arguments | Out-String) | ConvertFrom-Json
    Check ($plan.qualification -eq 'pending' -and $global:PortsChannelFixtureDownloads.Count -eq 0 -and @(Get-ChildItem -LiteralPath $fixture -Recurse -File).Count -eq $before) 'local pending Plan has no downloads or writes'
    Check ($plan.install_dir -eq (Join-Path $env:LOCALAPPDATA 'Programs\PortsBeta') -and $plan.data_dir -eq (Join-Path $env:LOCALAPPDATA 'PortForwardTUI-Beta')) 'explicit beta defaults ignore polluted PORTS environment'
    Expect-Error { & $helper @arguments -Action Install } 'pending qualification' 'pending Install is refused before download'
    Expect-Error { & $helper -Channel beta -Version latest } 'exact beta Version' 'moving or unknown version is refused'
    Expect-Error { & $helper -Channel stable -Action Install } 'never modifies stable' 'stable mutation is refused'
    $stable=(& $helper -Action Status -Json | Out-String) | ConvertFrom-Json
    Check (-not $stable.runtime_launched -and -not $stable.binary_matches -and $global:PortsChannelFixtureDownloads.Count -eq 0) 'stable Status launches no runtime'
    foreach ($bad in @((Join-Path $workspace 'bin'),(Join-Path $env:LOCALAPPDATA 'PortForwardTUI'),(Join-Path $fixture 'alias.\beta'),(Join-Path $fixture '..\escape'))) {
        Expect-Error { & $helper @arguments -InstallDir $bad } 'overlap|traversal|aliases' 'unsafe beta path is refused'
    }
    Expect-Error { & $helper @arguments -InstallDir (Join-Path $fixture 'same') -DataDir (Join-Path $fixture 'same') } 'must be separate' 'program and data overlap is refused'
    Expect-Error { & $helper @arguments -InstallDir (Join-Path $fixture 'directory:stream') } 'Alternate data streams' 'alternate-stream path is refused'
    $longWorkspace=Join-Path $fixture 'Long Workspace Directory'
    [IO.Directory]::CreateDirectory($longWorkspace) | Out-Null
    $fso=New-Object -ComObject Scripting.FileSystemObject
    try { $shortWorkspace=$fso.GetFolder($longWorkspace).ShortPath }
    finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($fso) }
    if ($shortWorkspace.Equals($longWorkspace,[StringComparison]::OrdinalIgnoreCase)) {
        Write-Output 'SKIP: volume does not expose an 8.3 alias for the owned long directory'
    } else {
        Check ((Resolve-PortsChannelPath (Join-Path $shortWorkspace 'new-beta')) -ceq (Join-Path $longWorkspace 'new-beta')) 'existing short ancestors resolve before appending a missing suffix'
        Expect-Error { & $helper @arguments -WorkspaceRoot $longWorkspace -InstallDir (Join-Path $shortWorkspace 'new-beta') } 'overlap' 'short-name program descendant cannot bypass Workspace protection'
        Expect-Error { & $helper @arguments -WorkspaceRoot $shortWorkspace -DataDir (Join-Path $longWorkspace 'new-data') } 'overlap' 'short-name Workspace protects its long-name data descendant'
        Expect-Error { & $helper @arguments -InstallDir (Join-Path $longWorkspace 'new-beta') -DataDir (Join-Path $shortWorkspace 'new-beta\data') } 'must be separate' 'program and data aliases cannot bypass their mutual boundary'
        $aliasPlan=(& $helper @arguments -InstallDir (Join-Path $shortWorkspace 'program') -DataDir (Join-Path $longWorkspace 'data') | Out-String) | ConvertFrom-Json
        Check ($aliasPlan.install_dir -ceq (Join-Path $longWorkspace 'program') -and -not (Test-Path -LiteralPath (Join-Path $longWorkspace 'program'))) 'separate alias siblings remain usable and Plan creates nothing'
    }
    $linkedTarget=Join-Path $fixture 'link-target'; [IO.Directory]::CreateDirectory($linkedTarget) | Out-Null
    $junction=Join-Path $fixture 'junction'
    New-Item -ItemType Junction -Path $junction -Target $linkedTarget | Out-Null
    try { Expect-Error { & $helper @arguments -InstallDir (Join-Path $junction 'beta') } 'reparse points' 'junction ancestor is refused before writes' }
    finally { [IO.Directory]::Delete($junction) }
    $changed=$contract | ConvertTo-Json -Depth 7
    $contract.beta | Add-Member NoteProperty url 'https://invalid.test/execute'
    Text $contractPath ($contract | ConvertTo-Json -Depth 7)
    Expect-Error { & $helper @arguments } 'Unexpected channel contract fields' 'stray URL field cannot broaden download origin'
    Text $contractPath $changed; $contract=$changed | ConvertFrom-Json

    $source=@'
using System;
using System.IO;
using System.Threading;
class MetadataFixture {
    static int Main(string[] args) {
        string root=Environment.GetEnvironmentVariable("PORTS_CHANNEL_FIXTURE");
        File.WriteAllLines(Path.Combine(root,"metadata.argv"),args);
        string mode=Environment.GetEnvironmentVariable("PORTS_CHANNEL_MODE");
        if(mode=="timeout") { File.WriteAllText(Path.Combine(root,"metadata.pid"),System.Diagnostics.Process.GetCurrentProcess().Id.ToString()); Thread.Sleep(30000); }
        if(mode=="error") { Console.Error.WriteLine("owned metadata refusal"); return 7; }
        if(args.Length==1 && args[0]=="--version") { Console.WriteLine("ports 0.10.0-beta.1"); return 0; }
        Console.WriteLine("{\"ok\":true,\"notice\":\"inert fixture only\"}");
        return 0;
    }
}
'@
    Text (Join-Path $fixture 'metadata.cs') $source
    $binary=Join-Path $fixture 'metadata.exe'
    & (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe') /nologo /target:exe ("/out:"+$binary) (Join-Path $fixture 'metadata.cs')
    if ($LASTEXITCODE -ne 0) { throw 'Owned metadata fixture did not compile.' }
    $payload=Join-Path $fixture 'archive.zip'; Text $payload 'inert archive; installer fixture validates arguments only'
    $installer=Join-Path $fixture 'installer.ps1'
    Text $installer @'
param([string]$Channel,[string]$Version,[string]$InstallDir,[string]$Bundle,[string]$Sha256,[switch]$NoPath)
if($Channel -cne 'beta' -or $Version -cne '0.10.0-beta.1' -or -not $NoPath -or -not [IO.File]::Exists($Bundle) -or $Bundle -eq $env:PORTS_BUNDLE) { throw 'Incorrect installer argument contract' }
[IO.Directory]::CreateDirectory((Join-Path $InstallDir 'bin')) | Out-Null
[IO.File]::Copy((Join-Path $env:PORTS_CHANNEL_FIXTURE 'metadata.exe'),(Join-Path $InstallDir 'bin/ports-beta.exe'),$true)
[IO.File]::WriteAllText((Join-Path $InstallDir '.ports-installer'),'port-forward-tui-beta')
[IO.File]::WriteAllText((Join-Path $InstallDir 'version'),$Version)
[IO.File]::WriteAllText((Join-Path $env:PORTS_CHANNEL_FIXTURE 'installer.called'),$Bundle)
'@
    $contract.beta.qualification='qualified'; $contract.beta.source_commit='b'*40
    $contract.beta.installer_sha256=Get-PortsChannelHash $installer
    $contract.beta.archive_sha256=Get-PortsChannelHash $payload
    $contract.beta.binary_sha256=Get-PortsChannelHash $binary
    $release=Join-Path $fixture 'release-record.json'
    Text $release (@{schema_version=1;version=$version;channel='beta';tag=('v'+$version);source_commit=('b'*40);artifacts=@{'ports-x86_64-pc-windows-msvc.zip'=$contract.beta.archive_sha256}} | ConvertTo-Json -Depth 5)
    $contract.beta.release_record_sha256=Get-PortsChannelHash $release
    Text $contractPath ($contract | ConvertTo-Json -Depth 7)
    $releaseUrl='https://github.com/brant92good/port-forward-tui/releases/download/v'+$version
    $global:PortsChannelFixtureServed['https://raw.githubusercontent.com/brant92good/port-forward-tui/v'+$version+'/install.ps1']=$installer
    $global:PortsChannelFixtureServed[$releaseUrl+'/ports-x86_64-pc-windows-msvc.zip']=$payload
    $global:PortsChannelFixtureServed[$releaseUrl+'/release-record.json']=$release
    $originalHash=Get-PortsChannelHash $payload
    Text $payload 'tampered'
    Expect-Error { & $helper @arguments -Action Install } 'checksum mismatch' 'download tampering refuses before installer invocation'
    Check (-not [IO.File]::Exists((Join-Path $fixture 'installer.called'))) 'failed verification leaves installer uncalled'
    Text $payload 'inert archive; installer fixture validates arguments only'
    Check ((Get-PortsChannelHash $payload) -ceq $originalHash) 'exact archive fixture restored'
    $installed=(& $helper @arguments -Action Install | Out-String) | ConvertFrom-Json
    Check ($installed.state -eq 'installed_verified' -and [IO.File]::Exists((Join-Path $fixture 'installer.called'))) 'qualified exact inputs invoke installer and verify owned binary'
    Check (-not [IO.Directory]::Exists($installed.data_dir)) 'Install creates neither metadata nor beta controller'
    $from=Join-Path $fixture ("stable space O'Neil "+[char]0x958b+[char]0x767c); [IO.Directory]::CreateDirectory($from) | Out-Null
    $import=(& $helper @arguments -Action Import -FromDataDir $from | Out-String) | ConvertFrom-Json
    $argv=[IO.File]::ReadAllLines((Join-Path $fixture 'metadata.argv'))
    Check ($import.state -eq 'metadata_imported' -and ($argv -join '|') -ceq (@('--data-dir',$installed.data_dir,'import-stable','--from',$from,'--json') -join '|')) 'Import sends exact frozen Unicode/path argv to the metadata CLI'
    [IO.Directory]::CreateDirectory($installed.data_dir) | Out-Null
    Expect-Error { & $helper @arguments -Action Import -FromDataDir $from } 'nonexistent beta destination' 'existing beta data is never replaced by import'
    $special=@('literal"quote','trailing\',([string][char]0x7a7a+' '+[char]0x767d),'')
    Invoke-PortsChannelMetadata $binary $special | Out-Null
    Check (([IO.File]::ReadAllLines((Join-Path $fixture 'metadata.argv')) -join '|') -ceq ($special -join '|')) 'bounded runner preserves quotes trailing slash Unicode and empty argv'
    $env:PORTS_CHANNEL_MODE='error'
    Expect-Error { Invoke-PortsChannelMetadata $binary @('probe') } 'failed \(7\)' 'nonzero metadata exit is reported'
    $env:PORTS_CHANNEL_MODE='timeout'
    Expect-Error { Invoke-PortsChannelMetadata $binary @('probe') 150 } 'timed out' 'owned metadata timeout is bounded'
    $childId=[int][IO.File]::ReadAllText((Join-Path $fixture 'metadata.pid'))
    Check (-not (Get-Process -Id $childId -ErrorAction SilentlyContinue)) 'timed-out owned child was reaped'
    $env:PORTS_CHANNEL_MODE=''
    $settings=Join-Path $env:LOCALAPPDATA 'Microsoft\Windows Terminal\settings.json'
    Text $settings '{"defaultProfile":"unchanged","newTabMenu":[{"type":"profile","profile":"stable"}],"keybindings":[{"keys":"ctrl+n","command":"ssh"}]}'
    $settingsHash=Get-PortsChannelHash $settings
    $profile=(& $helper @arguments -Action AddProfile | Out-String) | ConvertFrom-Json
    $fragment=Join-Path $profile.fragment_directory 'ports-beta.json'
    $fragmentData=[IO.File]::ReadAllText($fragment) | ConvertFrom-Json
    Check (@($fragmentData.profiles).Count -eq 1 -and $fragmentData.profiles[0].name -ceq 'Ports (BETA)' -and $fragmentData.profiles[0].commandline -ceq $profile.commandline) 'single optional beta fragment has the exact commandline'
    Check ((Get-PortsChannelHash $settings) -ceq $settingsHash -and $profile.profile_visibility -match 'not_observed') 'custom menu default and hotkeys remain byte-identical with no UI claim'
    $repeat=(& $helper @arguments -Action AddProfile | Out-String) | ConvertFrom-Json
    Check ($repeat.state -eq 'unchanged') 'repeated AddProfile is idempotent'
    $original=[IO.File]::ReadAllText($fragment); Text $fragment ($original+' ')
    Expect-Error { & $helper @arguments -Action RemoveProfile } 'changed outside' 'edited fragment is retained on removal'
    Check ([IO.File]::Exists($fragment)) 'refused removal preserves edited fragment'
    Text $fragment $original
    [IO.File]::WriteAllText($fragment,$original,[Text.UTF8Encoding]::new($true))
    Expect-Error { & $helper @arguments -Action RemoveProfile } 'changed outside' 'encoding-only fragment edits also require inspection'
    Text $fragment $original
    $lockFile=Join-Path $profile.fragment_directory '.operation.lock'
    Text $lockFile 'other owner'
    Expect-Error { & $helper @arguments -Action RemoveProfile } 'already exists|exist' 'concurrent profile operation is refused'
    Check ([IO.File]::ReadAllText($lockFile) -ceq 'other owner') 'another operation lock is preserved'
    [IO.File]::Delete($lockFile)
    $removed=(& $helper @arguments -Action RemoveProfile | Out-String) | ConvertFrom-Json
    Check ($removed.state -eq 'removed' -and -not [IO.File]::Exists($fragment) -and (Get-PortsChannelHash $settings) -ceq $settingsHash) 'owned fragment removal leaves settings unchanged'
    $sourcePrefix='https://raw.githubusercontent.com/brant92good/terminal-workspace/'+$revision+'/'
    foreach ($relative in @('ports-channel.ps1','scripts/ports-channel-common.ps1','config/ports-channels.json')) { $global:PortsChannelFixtureServed[$sourcePrefix+$relative]=Join-Path $workspace $relative }
    $start=$global:PortsChannelFixtureDownloads.Count
    $remote=(& (Join-Path $workspace 'bootstrap-ports.ps1') @arguments -WorkspaceRoot $workspace | Out-String) | ConvertFrom-Json
    Check ($global:PortsChannelFixtureDownloads.Count -eq $start+3 -and $remote.action -eq 'Plan') 'remote Plan fetches exactly three same-commit source files without leaf download'
    Write-Output "$script:count Ports channel checks passed on PowerShell $($PSVersionTable.PSVersion). No real install, SSH or GUI occurred."
} finally {
    $env:LOCALAPPDATA=$savedLocal; $env:PORTS_BUNDLE=$savedBundle; $env:PORTS_VERSION=$savedVersion; $env:PORTS_INSTALL_DIR=$savedInstall
    $env:PORTS_CHANNEL_FIXTURE=$savedFixture; $env:PORTS_CHANNEL_MODE=$savedMode
    $full=[IO.Path]::GetFullPath($fixture)
    if ([IO.Path]::GetDirectoryName($full) -cne [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') -or [IO.Path]::GetFileName($full) -notmatch '\Aports-channel-test-[a-f0-9]{32}\z') { throw 'Unsafe fixture cleanup refused' }
    Remove-Item -LiteralPath $full -Recurse -Force
}
