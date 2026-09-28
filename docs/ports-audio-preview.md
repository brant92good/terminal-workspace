# Optional Ports audio preview integration

This source branch adds a device-local opt-in. Public Workspace 0.10.0 installs
keep the bundled Ports app; copying this source file alone does not upgrade them.
Build this branch to obtain the preview-aware `terminal-workspace` binary. The
Ports audio client is built separately as described in its audio guide. This is
an explicitly prepared local preview, not a released downloadable workspace bundle.

## Prepare a separate preview installation

First build and configure the [Ports audio source](https://github.com/brant92good/port-forward-tui/blob/feat/audio-beta/docs/audio.md).
Then, from a developer PowerShell with Git and Rust installed:

```powershell
git clone --recurse-submodules --branch feat/audio-preview-integration https://github.com/brant92good/terminal-workspace.git workspace-audio
cd workspace-audio
cargo build --locked --release
$PreviewWorkspace = Join-Path $env:LOCALAPPDATA 'Programs\TerminalWorkspaceAudioPreview'
# Download the existing compiled companion apps without changing Terminal settings:
.\scripts\install-native.ps1 -InstallDir $PreviewWorkspace -Version 0.10.0 -NoConfigure -NoShortcuts
Copy-Item .\target\release\terminal-workspace.exe "$PreviewWorkspace\bin\terminal-workspace.exe"
Copy-Item .\ports.ps1 "$PreviewWorkspace\ports.ps1"
```

Use a new preview directory. This reuses the published bundle's other apps and
helpers; only the parent executable and its Ports wrapper are replaced locally.
Set `$Ports` to the **full path** built in the audio guide, and select its existing
beta data directory:

```powershell
$Ports = 'C:\path\to\ports-audio\target\release\ports.exe'
$BetaData = Join-Path $env:LOCALAPPDATA 'PortForwardTUI-Beta'
$choice = @{schema_version=1; executable=$Ports; data_directory=$BetaData}
[IO.File]::WriteAllText("$PreviewWorkspace\ports-preview.json", ($choice | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
# Opt the normal Terminal profiles and workspace shortcut into this installation:
& "$PreviewWorkspace\install.ps1" -SkipDependencies -IntegrationOnly -SessionPicker
& "$PreviewWorkspace\bin\terminal-workspace.exe" doctor --json
```

That last install command changes the normal Workspace shortcuts/profiles to the
preview installation. It does not start a microphone or stop old port forwards.

Use an existing beta-owned data directory. Never point the preview at stable
Ports data. Keep `PortsFocus.exe` and `TerminalViews.exe` beside the preview
executable. `terminal-workspace doctor --json` checks their locations.

The install command above renders the Ports profile and shortcuts. The workspace launcher and `ports.ps1`
also use this same selection. Normal new tabs still open SSH Sessions. The
workspace order stays Remote, optional Local, Ports, optional SFTP, with Remote
selected. No microphone starts during setup or launch.

Preview and stable connections have separate owners. Stop an old stable forward
before requesting the same local port in the preview; keep automatic opening
in only the installation you intend to use. Existing tabs retain their old
process until closed and reopened.

For a read-only check of the launch arguments:

```powershell
& "$PreviewWorkspace\bin\terminal-workspace.exe" workspace --json --window preview-check --machine SAVED_MACHINE
& "$PreviewWorkspace\ports.ps1" --machine SAVED_MACHINE audio status --json
```

Delete `ports-preview.json` from the preview installation and rerun its
`install.ps1 -SkipDependencies -IntegrationOnly -SessionPicker` to select the
bundled Ports again.
Stop preview audio/forwards first; changing the selected executable does not stop
background work or transfer its ownership. This file contains device paths and
is excluded from Git. Keep personal choices in your private parent setup.
