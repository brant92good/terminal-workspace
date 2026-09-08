# Setup guide

[Back to the README](../README.md)


Use a **PowerShell tab on Windows 10/11**. You need:

| Tool / information | Purpose and where to get it |
| --- | --- |
| Windows Terminal | The window that holds the tabs; available in Microsoft Store |
| PowerShell 7 | Used by setup and session tracking; install with `winget install --id Microsoft.PowerShell -e` |
| Git for Windows | Downloads this project and its included port app; [download](https://git-scm.com/downloads/win) |
| Windows Python 3.12+ | Runs Ports; [download](https://www.python.org/downloads/windows/) or select an existing Conda Python |
| Windows OpenSSH Client | Connects to your remote computer; install through Windows Optional features |
| Herdr (optional) | For remote or local Herdr sessions; follow [Herdr's installation guide](https://herdr.dev/) |
| Your working SSH name | If you connect using `ssh workbox`, your name is `workbox` |

Before starting connections, run `ssh YOUR_SSH_NAME`, confirm you can log in, and type
`exit`. If this is new to you, the port app's [first-connection walkthrough](https://github.com/brant92good/port-forward-tui#set-up)
explains ports, SSH names and keys. Saved background connections need a working
SSH key or key agent because they cannot ask for a password.

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

The installer requires Git, a usable Windows Python, Windows Terminal,
PowerShell 7 and OpenSSH Client. Herdr is optional. It does not install these prerequisites
or provide a remote server. Background forwards need a working noninteractive
SSH login. `doctor.ps1` checks local prerequisites; it does not test remote SSH.

For scripts, add `-NonInteractive`; selecting a machine is a separate runtime step.
Pass `-NoShortcuts` to skip Start/desktop shortcuts. The full settings and
verification options are in [REFERENCE.md](reference.md).
