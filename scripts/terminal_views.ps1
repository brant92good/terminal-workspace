param(
    [ValidateSet('List', 'State', 'Activate', 'CloseTestWindow', 'Track', 'Focus', 'Probe')][string]$Mode = 'List',
    [string]$RecordPath,
    [string]$InitialTitle,
    [string]$RuntimeId,
    [int]$OwnerPid,
    [string]$RecordsBase64,
    [ValidateSet('all', 'window')][string]$Scope = 'all',
    [string]$OriginTitle = '',
    [int]$AfterPid = 0,
    [long]$InvokeWindow = 0,
    [long]$WindowHandle = 0
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
try {
    Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, WindowsBase, System.Web.Extensions
    Add-Type -Path (Join-Path $PSScriptRoot 'TerminalViews.cs') -ReferencedAssemblies @(
        'System.dll', 'System.Core.dll',
        [System.Windows.Automation.AutomationElement].Assembly.Location,
        [System.Windows.Automation.ControlType].Assembly.Location,
        [System.Windows.Threading.Dispatcher].Assembly.Location,
        [System.Web.Script.Serialization.JavaScriptSerializer].Assembly.Location
    )
    if ($Mode -eq 'List') { [TerminalViews]::Snapshot(); exit 0 }
    if ($Mode -eq 'CloseTestWindow') { [TerminalViews]::CloseTestWindow($WindowHandle); exit 0 }
    if ($Mode -eq 'State') {
        Write-Output ('{"foreground":' + [TerminalViews]::GetForegroundWindow().ToInt64() + ',"tabs":' + [TerminalViews]::Snapshot() + '}')
        exit 0
    }
    if ($Mode -eq 'Activate') {
        if ($AfterPid) {
            $herdrLauncher = Get-Process -Id $AfterPid -ErrorAction SilentlyContinue
            if ($herdrLauncher -and -not $herdrLauncher.WaitForExit(5000)) { exit 1 }
            Start-Sleep -Milliseconds 300
            if ([TerminalViews]::GetForegroundWindow().ToInt64() -ne $InvokeWindow) { exit 1 }
        }
        if ([TerminalViews]::Activate($RuntimeId)) { exit 0 }
        exit 1
    }
    if ($Mode -eq 'Track') {
        [TerminalViews]::Track($RecordPath, $InitialTitle, $RuntimeId, $OwnerPid)
        exit 0
    }
    $herdrRecords = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($RecordsBase64))
    $herdrResult = [TerminalViews]::Focus($herdrRecords, $Scope, $OriginTitle, ($Mode -eq 'Probe'))
    if ($herdrResult) { Write-Output $herdrResult; exit 0 }
    exit 1
} catch {
    Write-Error $_
    exit 2
}
