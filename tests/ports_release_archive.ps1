param([Parameter(Mandatory=$true)][string]$FixtureRoot)
$ErrorActionPreference='Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts/validate-ports-release.ps1')
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$names=@('ports.exe','PortsFocus.exe','TerminalViews.exe','LICENSE.txt','THIRD_PARTY_NOTICES.txt')
$data=@{}; $lines=@()
foreach($name in $names) {
    $data[$name]=[Text.Encoding]::UTF8.GetBytes('owned fixture '+$name)
    $hasher=[Security.Cryptography.SHA256]::Create()
    try { $hash=([BitConverter]::ToString($hasher.ComputeHash($data[$name]))).Replace('-','').ToLowerInvariant() } finally {$hasher.Dispose()}
    $lines+=($hash+'  '+$name)
}
function Add-FixtureEntry($Zip,[string]$Name,[byte[]]$Bytes,[int]$Attributes=0) {
    $entry=$Zip.CreateEntry($Name); $entry.ExternalAttributes=$Attributes
    $stream=$entry.Open();try{$stream.Write($Bytes,0,$Bytes.Length)}finally{$stream.Dispose()}
}
foreach($mode in @('valid','missing','tampered','bad-hash','duplicate','unexpected','traversal','case','symlink','directory','duplicate-index','missing-index','unexpected-index')) {
    $archive=Join-Path $FixtureRoot ($mode+'.zip');$destination=Join-Path $FixtureRoot ($mode+'-out')
    $zip=[IO.Compression.ZipFile]::Open($archive,[IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach($name in $names) {
            if($mode -eq 'missing' -and $name -eq 'THIRD_PARTY_NOTICES.txt'){continue}
            $entryName=$name; $bytes=$data[$name];$attributes=0
            if($name -eq 'ports.exe') {
                if($mode -eq 'tampered'){$bytes=[byte[]]@(0)}
                if($mode -eq 'traversal'){$entryName='../ports.exe'}
                if($mode -eq 'case'){$entryName='Ports.exe'}
                if($mode -eq 'symlink'){$attributes=-1610612736}
                if($mode -eq 'directory'){$attributes=16}
            }
            Add-FixtureEntry $zip $entryName $bytes $attributes
        }
        if($mode -eq 'duplicate'){Add-FixtureEntry $zip 'ports.exe' $data['ports.exe']}
        if($mode -eq 'unexpected'){Add-FixtureEntry $zip 'extra.txt' ([byte[]]@(0))}
        $indexLines=@($lines)
        if($mode -eq 'bad-hash'){$indexLines[0]=('0'*64)+'  ports.exe'}
        if($mode -eq 'duplicate-index'){$indexLines+= $lines[0]}
        if($mode -eq 'unexpected-index'){$indexLines+= ('0'*64)+'  extra.txt'}
        if($mode -ne 'missing-index'){Add-FixtureEntry $zip 'SHA256SUMS' ([Text.Encoding]::UTF8.GetBytes(($indexLines -join "`n")+"`n"))}
    }finally{$zip.Dispose()}
    $accepted=$false
    try { Expand-WorkspacePortsRelease -Bundle $archive -Destination $destination; $accepted=$true }catch{ if($mode -eq 'valid'){throw} }
    if($accepted -ne ($mode -eq 'valid')){throw "Incorrect archive acceptance: $mode"}
    if($mode -eq 'valid') {
        foreach($name in $names){if([Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $destination $name))) -cne [Convert]::ToBase64String($data[$name])){throw "Changed bytes: $name"}}
    }elseif(Test-Path -LiteralPath $destination){throw "Invalid archive created its destination: $mode"}
    Write-Output "PASS $mode"
}
