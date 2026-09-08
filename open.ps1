$workspaceLauncher = Join-Path $PSScriptRoot 'build\TerminalWorkspace.exe'
if (-not (Test-Path -LiteralPath $workspaceLauncher)) { throw 'Run .\install.ps1 first, then .\open.ps1.' }
Start-Process -FilePath $workspaceLauncher -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
