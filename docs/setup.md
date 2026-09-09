# Setup guide

[Back to the README](../README.md)


Use a **PowerShell tab on Windows 10/11**. You need:

| Tool / information | Purpose and where to get it |
| --- | --- |
| Windows Terminal | The window that holds the tabs; available in Microsoft Store |
| PowerShell 7 | Used by setup and session tracking; install with `winget install --id Microsoft.PowerShell -e` |
| Git for Windows (source checkout only) | Needed for submodule updates and optional catalog sync; [download](https://git-scm.com/downloads/win) |
| Windows Python 3.12+ (source checkout only) | The bootstrap downloads its own runtime; manual installs can select an existing Python |
| Windows OpenSSH Client | Connects to your remote computer; install through Windows Optional features |
| Herdr (optional) | For remote or local Herdr sessions; follow [Herdr's installation guide](https://herdr.dev/) |
| Your working SSH name (when connecting) | If you connect using `ssh workbox`, your name is `workbox`; setup does not ask for it |

Before starting connections, run `ssh YOUR_SSH_NAME`, confirm you can log in, and type
`exit`. If this is new to you, the port app's [first-connection walkthrough](https://github.com/brant92good/port-forward-tui#set-up)
explains ports, SSH names and keys. Saved background connections need a working
SSH key or key agent because they cannot ask for a password.

## One-command setup

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/brant92good/terminal-workspace/main/bootstrap.ps1 | iex"
```

The bootstrap gets the public workspace and both apps from GitHub source
archives at their recorded commits. It downloads uv 0.10.10 and Python 3.12,
then runs the normal installer. A fresh installation enables SSH Sessions for
new tabs and Ctrl+Alt+N for local PowerShell, preserving appearance and menu.
Updates keep the existing `.machine.json` preferences. No host is required.

Files stay in `%LOCALAPPDATA%\TerminalWorkspace\install`. `current.json` records
the last configured source directory; use its `install.ps1` for advanced
options below. Old source directories are retained, so their paths remain
available for rollback. This managed bundle is for running the app; use a Git
checkout to edit/fork shared configuration. Bootstrap does not read or update
a separately installed private parent checkout.

To inspect the script or pass options, download [bootstrap.ps1](../bootstrap.ps1)
and run `powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1`.
`-InstallDir PATH` chooses an empty/installer-owned location; `-Revision COMMIT`
pins a workspace commit; `-NoShortcuts` skips Start/desktop entries.
`-NoConfigure` downloads and prepares dependencies/helpers only, without changing
Terminal settings or shortcuts. It also skips the Windows Terminal/PowerShell 7
prerequisite check, for headless CI. No app window is opened by setup.

GitHub API rate-limit failures can be retried later. In CI, GH_TOKEN or
GITHUB_TOKEN can authenticate metadata requests; tokens are sent only to the
GitHub API, not archive or runtime download hosts.

## Source checkout

```powershell
git clone --recurse-submodules https://github.com/brant92good/terminal-workspace.git
cd terminal-workspace
.\doctor.ps1
.\install.ps1 -IntegrationOnly
.\open.ps1
```

No host is needed during installation. On first launch, add a machine with A
or import SSH config with I. The picker is provided by the independent port app.
On the first doctor run, missing environment/launcher checks are expected.
Use `-RemoteClient herdr` to opt into Herdr, and `-LocalHerdr` for an additional
local Herdr tab. `-RemoteClient ssh` and `-NoLocalHerdr` turn those choices off.
Herdr is only required when enabled. Choices are remembered on this computer.

**What setup changes:** it creates a private Python environment, backs up
Terminal settings, adds Remote/Ports profiles and shortcuts, and creates a
Terminal Workspace button in Start and on the desktop. `-IntegrationOnly`
preserves your appearance, default shell, other profile visibility and custom
dropdown menu. A custom menu that lists specific profiles may need Remote/Ports
added manually; the button and keyboard shortcuts still open them.

The install choice is saved on this computer and reused on updates. To apply
the repository's appearance, PowerShell default and compact menu too, rerun
`.\install.ps1 -ApplySharedSettings`. This is also the legacy first-install
behavior when neither option nor a saved choice exists. In shared-settings
mode, set `compactMenu` to `false` in `config/terminal.json` before installing
to retain other profiles' visibility.

Keep the checkout where you installed it; shortcuts refer to that folder.
For custom installations, pass `-Python 'C:\path\python.exe'` or
`-HerdrPath 'C:\path\herdr.exe'`. Conda is not activated on each shortcut press.
If script execution is blocked, inspect the script and, where allowed, run it
through `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -IntegrationOnly`.



## Existing settings and updates

An update reuses the install mode saved in `.machine.json`. `-IntegrationOnly`
continues to preserve local appearance, the default shell and menu. Shared
shortcut definitions still update; conflicting unrelated keybindings cause
setup to stop with an error.

Switching from shared settings to integration-only preserves your preferences
as they are now. It does not undo earlier changes. Original settings are kept
beside Windows Terminal's settings.json in timestamped
`settings.json.before-workspace-*.bak` files. Restore selectively if you have
edited Terminal since that backup.

The source installer requires Git and a usable Windows Python in addition to
Windows Terminal, PowerShell 7 and OpenSSH Client. The bootstrap supplies source
and Python automatically; Windows components and optional Herdr are installed
separately. Background forwards need a working noninteractive
SSH login. `doctor.ps1` checks local prerequisites; it does not test remote SSH.

For scripts, add `-NonInteractive`; selecting a machine is a separate runtime step.
Pass `-NoShortcuts` to skip Start/desktop shortcuts. The full settings and
verification options are in [REFERENCE.md](reference.md).

## Taskbar icon and closing tips

The Terminal Workspace button uses the Herdr artwork and launches the saved
tabs. The running window still belongs to Windows Terminal, so Windows groups
it under Terminal's taskbar icon. A shortcut icon does not change the identity
of the application that owns the window. Terminal's request for configurable
taskbar groups remains [open upstream](https://github.com/microsoft/terminal/issues/8216).

Windows supports [per-window application IDs](https://learn.microsoft.com/en-us/windows/win32/shell/appids), but attaching one from an external
launcher would need matching shortcut/relaunch metadata and window-lifecycle
management. A local probe accepted and read back an ID; that did not establish
reliable pinned-icon grouping. This project does not install that workaround.
The practical tradeoff is a branded launch button with ordinary Terminal
grouping for running windows.

For the message about configuring termination behavior in advanced settings,
choose **Don't show again** (**不要再顯示** in Traditional Chinese) on the bar.
This dismisses that informational tip; it does not hide process error output.
The X merely closes the current bar. Terminal remembers the choice on that
computer, outside this repository's shared settings.
The dismissal is implemented by [Terminal's information-bar handler](https://github.com/microsoft/terminal/blob/main/src/cascadia/TerminalApp/TerminalPage.cpp).

Keep `closeOnExit` at `"automatic"` for these profiles: directly launched
sessions close after success and stay open after an error. An empty value is
not a supported suppression setting, and `"always"` can close the tab before
you read an error. This is the Windows Terminal default and a useful development
setting; it is not a claim that every developer chooses the same behavior.
See [Microsoft's termination settings](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/profile-advanced#profile-termination-behavior).
