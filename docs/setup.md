# Setup

[README](../README.md) · [Daily use](daily-use.md)

These instructions describe the compiled distribution. Check the
[release status and remaining limits](native-migration.md) before installing.

## Prerequisites

Windows 10/11 x64 with Windows Terminal, PowerShell 7 and OpenSSH Client.
The regular installer uses Windows PowerShell and the compiled binaries; it does
not install a language runtime or change Python/Conda environments.

```powershell
winget install --id Microsoft.WindowsTerminal -e
winget install --id Microsoft.PowerShell -e
```

Enable **OpenSSH Client** in Windows Optional features if `ssh` is unavailable.
Herdr is optional and installed separately from [herdr.dev](https://herdr.dev/).
Test a new SSH destination with `ssh YOUR_ALIAS` before saving background forwards;
SSH keys or an existing key agent must allow noninteractive authentication.

## One-command setup

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/brant92good/terminal-workspace/v0.7.2/bootstrap.ps1 | iex"
```

The installer downloads a versioned ZIP, verifies its SHA256 checksum and its
file manifest, then checks the packaged executable versions. The bundle includes
SSH Sessions, Ports, the Rust workspace launcher, and precompiled
Windows focus/taskbar helpers. Git is optional for later settings/catalog sync.

The default directory is `%LOCALAPPDATA%\Programs\TerminalWorkspace`. Run the
same command to update. Existing `.machine.json`, shared appearance configuration
and unrelated files remain. Replaced executables are retained with a
`.previous-...` suffix for rollback and running sessions.

Upgrading the older public source-bundle install carries over its saved machine
preferences and shared appearance file automatically from
`%LOCALAPPDATA%\TerminalWorkspace\install`. The installer checks the old ownership
marker and recorded source revision first. Originals and `current.json` stay in
place; exact-byte backups are saved under the new installation's `migration`
directory. An existing native `.machine.json` always takes precedence. For a
custom old location, pass `-LegacyInstallDir 'C:\Tools\Old Workspace'` to the
downloaded bootstrap. It does not search arbitrary folders or modify checkouts.

To inspect or pass options, download [bootstrap.ps1](../bootstrap.ps1), then:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 -InstallDir 'C:\Tools\Terminal Workspace'
```

`-Version 0.7.2` selects a release. `-NoShortcuts` skips Start/desktop entries.
`-NoConfigure` only prepares compiled files; it does not apply Terminal settings,
Explorer entries or shortcuts. Setup opens no app window.

## What changes

A fresh install adds Remote, Ports and SSH Sessions profiles, sets **SSH Sessions**
as the new-tab default, and adds the R/P return/new-view shortcuts plus
**Ctrl+Alt+N** for local PowerShell. It creates a Terminal Workspace Start/desktop
shortcut. Your appearance, unrelated profiles and custom menu remain as configured.
Windows Terminal settings are backed up beside `settings.json` before changes.

The + button and ordinary Ctrl+Shift+T use the SSH picker. Optional Ctrl+N or
Ctrl+T bindings explicitly open its profile. Explorer integration never switches
the global default to PowerShell.

From the installed directory:

```powershell
.\install.ps1 -SkipDependencies -NewTabShortcut ctrl+n
.\install.ps1 -SkipDependencies -RemoteClient herdr -HerdrPath C:\Tools\Herdr\herdr.exe -LocalHerdr
.\install.ps1 -SkipDependencies -SessionCatalog C:\MySetup\connections\catalog.json
```

Use `-RemoteClient ssh`, `-NoLocalHerdr` or `-NewTabShortcut none` to undo those
specific choices. `-NoSessionPicker` explicitly restores the local PowerShell
default. Routine updates reuse saved choices. `-IntegrationOnly` preserves
appearance/menu/default settings; explicit `-SessionPicker` changes the default
even in that mode. `-ApplySharedSettings` applies `config/terminal.json`, including
the compact profile menu and the saved picker/default choice.

Conflicting unrelated keyboard bindings stop configuration with a message rather
than being overwritten. Keep the installation at its chosen path.

## Explorer and taskbar

```powershell
.\install.ps1 -SkipDependencies -NoShortcuts -ExplorerPowerShell
```

This adds **Open PowerShell here** for folders, folder backgrounds and drives.
The command names PowerShell's profile and the clicked directory explicitly.
On Windows 11, it is a classic entry under **Show more options**.
The built-in modern **Open in Terminal** entry still follows Terminal's default
profile and therefore opens the SSH picker. The integration does not replace it.

Remove only these owned entries with
`./install.ps1 -SkipDependencies -NoShortcuts -NoExplorerPowerShell`, or inspect
the exact command without writing the registry with
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/explorer.ps1 -Plan`.

Pin **Terminal Workspace** from Start for its Herdr-artwork button. The launcher
assigns its own application ID only to a workspace window it can identify by a
unique marker. **Separate taskbar grouping is beta**: Explorer caching, dragged
tabs and actual pinned-launch behavior still need desktop qualification. Re-pin
from Start if Explorer retains an old identity. It remains Windows Terminal under
the hood; this is not a second terminal emulator.

Keep `closeOnExit: "automatic"`: successful sessions close, failures stay visible.
For Terminal's informational closing-behavior tip, choose **Don't show again**;
an empty termination setting is not a supported suppression mechanism.

## Source checkout

```powershell
git clone --recurse-submodules https://github.com/brant92good/terminal-workspace.git
cd terminal-workspace
.\install.ps1
```

Source installation still downloads compiled binaries. Git is needed to obtain
the checkout; Python and a Rust compiler are not required to run it. Child source
pins are not automatically advanced by the installer. When developing the Rust
code, use the [contributor workflow](../AGENTS.md); native builds go to an artifact
directory, never directly over an installed launcher.

## Checks and updates

`./doctor.ps1 --json` reports local prerequisites without contacting SSH.
`./ports.ps1 list --json` reads saved forwards and available controller state.
`./sessions.ps1 doctor --json` checks the standalone picker.

Updating binaries does not kill running connections. Close old views, then run
`./ports.ps1 restart-manager --machine MACHINE_ID` for each controller when a
brief handover is acceptable; requested forwards restart and stopped favorites
stay stopped. Keep older files until that handover is complete.

[Platform support](platforms.md) · [Verification](verification.md) · [Reference](reference.md)
