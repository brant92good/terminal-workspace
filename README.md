# Terminal Workspace

Open Herdr and your SSH port forwards in one Windows Terminal window.

This is a Windows setup for working on a remote computer: a
[Herdr](https://herdr.dev/) tab for your shell, a
[Ports](https://github.com/brant92good/port-forward-tui) tab for its web apps
and notebooks, and shortcuts to return to the tab you were using.

```text
Terminal Workspace button
  └─ Windows Terminal
       ├─ Herdr   ← selected when the window opens
       └─ Ports   ← saved connections to remote apps

Ctrl+Alt+H → return to Herdr     Ctrl+Alt+P → return to Ports
```

[Install](#set-up-on-windows) · [Daily use](#use-it-every-day) · [Test results](#what-has-been-checked) · [Setup help](docs/setup.md)

## When this is useful

If you regularly use both a remote shell and remote web apps, this gives them
one Start/desktop button and consistent return shortcuts. Multiple open tabs
share the underlying sessions; adding Shift opens another view.

The installer can keep your current Terminal appearance, default shell and
menu. If you want the same appearance and shortcuts on another computer, it
also supports sharing those preferences through your own fork.

Only need saved port forwards? Install
[Port Forward TUI](https://github.com/brant92good/port-forward-tui) on its own.
This repository adds the Herdr integration and Terminal setup. It targets one
SSH destination per installed app data folder.

## Set up on Windows

You need **Windows 10/11, Windows Terminal, PowerShell 7, Git, Windows Python
3.12+, OpenSSH Client and Herdr**. The [setup guide](docs/setup.md) links to
installation instructions for missing tools. These prerequisites are installed
separately.

Use the name from your working SSH command in place of `workbox`. Background
port connections need an SSH key or agent that can log in without a password
prompt. Run these commands in a PowerShell tab on Windows:

```powershell
git clone --recurse-submodules https://github.com/brant92good/terminal-workspace.git
cd terminal-workspace
.\install.ps1 -SshHost workbox -IntegrationOnly
.\open.ps1
```

You should get a new Terminal window with **Herdr selected and Ports in the
second tab**. The installer also creates **Terminal Workspace** in Start and
on the desktop. Pin its Start entry to the taskbar if you want a taskbar button.
Keep the checkout in place; the shortcuts refer to it.

`-IntegrationOnly` adds the two profiles, four keyboard shortcuts and the
button, while preserving your appearance, default shell and menu. Settings
are backed up before changes. The mode is remembered when you reinstall or
sync. For a custom menu listing specific profiles, add Herdr/Ports to that menu
manually if desired; the button and keyboard shortcuts work independently.

To also apply this repository's appearance, PowerShell default and compact
menu, run `.\install.ps1 -ApplySharedSettings`. Existing installations keep
their saved mode; older installs without a saved mode retain the original
shared-settings behavior. See [setup options](docs/setup.md).

## Use it every day

Work in Herdr as usual. To open a remote web app, switch to Ports, press **A**,
enter its port (for example `8000`), then Enter. When it shows ON, **B** opens
its local HTTP address. The remote app must already be running.

![The Ports tab with saved example web apps and notebooks](https://raw.githubusercontent.com/brant92good/port-forward-tui/main/docs/screenshots/connections.svg)

*Actual Ports interface with simulated data; this image shows the Ports tab only.*

| Key inside Windows Terminal | Action |
| --- | --- |
| Ctrl+Alt+H | Return to the most recently used Herdr tab; open one if needed |
| Ctrl+Alt+P | Return to the most recently used Ports tab; open one if needed |
| Add Shift to either | Open another connected view |
| F2 inside Ports | Search this Terminal window or all Terminal windows |

These shortcuts apply while Terminal has focus. In the default all-windows
mode, a return shortcut may bring another Terminal window forward. Use F2
for the current-window setting. A temporary launcher tab may appear during
the handoff. Moved Herdr tabs may need reopening; split panes are not tracked
as separate tabs.

Closing the terminal leaves background port forwards running. **S** in Ports
stops them. Reboot, sign-out or a lost SSH connection ends tunnels. Herdr owns
its workspace on the remote server; use its detach command to leave a client.

## What has been checked

Real keyboard tests exercised duplicate tabs, both window scopes, content
focus, and cancellation when another application took focus. A real SSH
forward also carried traffic after its entire test Terminal window closed.
See [test details and reproduction](docs/verification.md).

Existing-tab return was measured before and after replacing the old launcher:

| Return shortcut | Old median | New median |
| --- | ---: | ---: |
| Herdr | 1,292 ms | 363 ms |
| Ports | 1,360 ms | 370 ms |

Six keypresses per before/after batch, on one Windows 11 desktop. These are
same-window returns to an already open tab, **not new-window or SSH startup
times**. The [full report](docs/before-after.md) includes raw samples, method,
hardware, and remaining costs. These numbers are not a comparison with other tools.

## Check setup or use a coding agent

```powershell
.\doctor.ps1                  # Local checks and next steps
.\doctor.ps1 --json           # The same checks for a script or agent
.\ports.ps1 list --json       # Saved connections and available live state
```

Doctor does not install, change settings or contact SSH. It needs a usable
Windows Python. If the included port app folder is empty, run
`git submodule update --init --recursive` first.

Agents can install with `-SshHost YOUR_SSH_NAME -IntegrationOnly -NonInteractive`
and use the port app's [command guide](https://github.com/brant92good/port-forward-tui/blob/main/docs/automation.md).
For repository work, read [AGENTS.md](AGENTS.md).

## Use the same settings on another computer

In your own fork, `config/terminal.json` stores appearance and shortcut
preferences. Each computer keeps its SSH name, paths and install mode in
ignored `.machine.json`. The included port app is pinned to a specific version.

```powershell
.\sync.ps1             # Download the saved version and apply it here
.\sync.ps1 -Publish    # Export and push portable preferences to your fork
```

Integration-only installs continue to keep local appearance and menu settings
when syncing. Choose `-ApplySharedSettings` on computers where you want the
shared appearance too. Save local Git changes before syncing. Keys and tokens
belong outside Git; a private parent for personal values is optional.

[Technical reference](docs/reference.md) · [Design and scope](docs/design.md) · [MIT license](LICENSE) · [Herdr artwork attribution](NOTICE)
