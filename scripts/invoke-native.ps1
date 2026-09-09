$ErrorActionPreference = 'Stop'
function ConvertTo-WorkspaceArgument([string]$Value) {
    $text = [Text.StringBuilder]::new(); [void]$text.Append('"'); $slashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') { $slashes++; continue }
        if ($character -eq '"') { [void]$text.Append(('\' * ($slashes * 2 + 1))) }
        else { [void]$text.Append(('\' * $slashes)) }
        $slashes = 0; [void]$text.Append($character)
    }
    [void]$text.Append(('\' * ($slashes * 2))); [void]$text.Append('"')
    return $text.ToString()
}
function Invoke-WorkspaceNative([string]$Executable, [string[]]$Arguments, [switch]$CaptureOutput) {
    # PowerShell 5.1's '&' binder can strip embedded quotes. Pass a correctly
    # escaped Windows argument vector while retaining the caller's console.
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Executable
    $start.Arguments = (($Arguments | ForEach-Object { ConvertTo-WorkspaceArgument $_ }) -join ' ')
    $start.UseShellExecute = $false
    $start.RedirectStandardOutput = [bool]$CaptureOutput
    if ($CaptureOutput) { $start.StandardOutputEncoding = [Text.UTF8Encoding]::new($false) }
    $process = [Diagnostics.Process]::new(); $process.StartInfo = $start
    try {
        if (-not $process.Start()) { throw 'Could not start the compiled app.' }
        if ($CaptureOutput) { $stdout = $process.StandardOutput.ReadToEndAsync() }
        $process.WaitForExit()
        if ($CaptureOutput -and -not $stdout.Wait(1000)) { throw 'Native command output did not close.' }
        return [PSCustomObject]@{code=$process.ExitCode;output=$(if ($CaptureOutput) { $stdout.Result } else { '' })}
    } finally { $process.Dispose() }
}

function Write-WorkspaceNativeOutput([string]$Text) {
    # PowerShell pipelines retain .NET strings. When this shell itself is
    # redirected, emit UTF-8 instead of Windows PowerShell's legacy code page.
    $previous = [Console]::OutputEncoding
    try {
        if ([Console]::IsOutputRedirected) { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) }
        Write-Output $Text
    } finally { [Console]::OutputEncoding = $previous }
}
