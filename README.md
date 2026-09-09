# Terminal Workspace

Open a remote shell and its SSH port forwards in one Windows Terminal window.

Choose a machine, then open an **SSH** tab for your shell, a
[Ports](https://github.com/brant92good/port-forward-tui) tab for its web apps
and notebooks, and shortcuts to return to the tab you were using.
[Herdr](https://herdr.dev/) is an optional alternative for remote sessions;
you can also add a third tab for local Herdr.

Want to choose a server whenever you open a new tab? The optional
[SSH Sessions](https://github.com/brant92good/ssh-session-tui) picker supports
named routes for each machine, with a separate route choice on each device.
Your existing SSH client handles login.

```text
Terminal Workspace button
  └─ Windows Terminal
       ├─ Remote  ← selected; ordinary SSH or optional Herdr
       └─ Ports   ← saved connections to remote apps

Ctrl+Alt+R → return to remote     Ctrl+Alt+P → return to Ports
```

[Install](#set-up-on-windows) · [Daily use](#use-it-every-day) · [Test results](#what-has-been-checked) · [Setup help](docs/setup.md)

Windows is supported today. See the [macOS/Linux assessment and plan](docs/platforms.md)
for the current limits of each app and the terminal integration.

## When this is useful

If you regularly use both a remote shell and remote web apps, this gives them
one Start/desktop button and consistent return shortcuts. Ports tabs share
background connections; adding Shift opens another view. Ordinary SSH tabs
are separate shell sessions; Herdr manages its own persistent sessions.

The installer can keep your current Terminal appearance, default shell and
menu. If you want the same appearance and shortcuts on another computer, it
also supports sharing those preferences through your own fork.

Only need saved port forwards? Install
[Port Forward TUI](https://github.com/brant92good/port-forward-tui) on its own.
This repository adds machine-aware Terminal windows and optional Herdr integration.
Each machine keeps separate favorites and running forwards.

## Set up on Windows

You need **Windows 10/11, Windows Terminal, PowerShell 7, Git, Windows Python
3.12+ and OpenSSH Client**. The [setup guide](docs/setup.md) links to
installation instructions for missing tools. These prerequisites are installed
separately.

You do not need to choose a host during installation. Background port connections
will need an SSH key or agent when you start them. Run in PowerShell on Windows:

```powershell
git clone --recurse-submodules https://github.com/brant92good/terminal-workspace.git
cd terminal-workspace
.\install.ps1 -IntegrationOnly
.\open.ps1
```

On first launch, **A** adds a machine or **I** imports names from your SSH config.
Choose one: its **remote shell opens first and Ports second**, with the remote
tab selected. The installer also creates **Terminal Workspace** in Start and
on the desktop. Pin its Start entry to the taskbar if you want a taskbar button.
Keep the checkout in place; the shortcuts refer to it.

`-IntegrationOnly` adds the two profiles, four keyboard shortcuts and the
button, while preserving your appearance, default shell and menu. Settings
are backed up before changes. The mode is remembered when you reinstall or
sync. For a custom menu listing specific profiles, add Remote/Ports to that menu
manually if desired; the button and keyboard shortcuts work independently.

To also apply this repository's appearance, PowerShell default and compact
menu, run `.\install.ps1 -ApplySharedSettings`. Existing installations keep
their saved mode; older installs without a saved mode retain the original
shared-settings behavior. See [setup options](docs/setup.md).

To use Herdr, install it separately and run `.\install.ps1 -RemoteClient herdr`.
Add `-LocalHerdr` for a third, local Herdr tab and **Ctrl+Alt+L** to return to it.
These choices survive updates. Custom SSH config files and login-port overrides
use ordinary SSH because Herdr's remote command accepts an SSH target only.

## Choose a server in every new tab

```powershell
.\install.ps1 -IntegrationOnly -SessionPicker
```

This explicitly makes **SSH Sessions** the default new-tab screen and adds
**Ctrl+Alt+N** for a normal local PowerShell tab. Your appearance and menu remain
unchanged in integration-only mode. Press **A** to add a machine, **Enter** to
connect, or **R** to add and select a route such as LAN or Tailscale. Logging out
returns to the picker. Installation does not require a host.
**Local terminal** is also a visible picker row. Highlight a machine or the local
terminal and press **F** to assign a favorite number; **1–9, then Enter** opens it.
Favorite numbers are saved on this device and use its selected machine route.
Press **I** to preview and import local SSH hosts, including static Include files.
Imported hosts use their existing SSH aliases and settings.

For a simpler new-tab shortcut, run `.\install.ps1 -NewTabShortcut ctrl+n`.
Ctrl+Shift+T remains available. This optional binding is kept on this computer;
it intercepts Ctrl+N before shells or editors can use it. Use `ctrl+t` for the
usual browser new-tab key, or `none` to remove the extra shortcut.

![SSH Sessions with example machines](https://raw.githubusercontent.com/brant92good/ssh-session-tui/main/docs/screenshots/picker.svg)

*Example machines in the picker.*

Use **G** to browse nested groups, **Space** to select machines, **M** to move
them and **T** to add or remove tags. Numbered favorites work across groups.
Search accepts names, addresses, group paths and tags such as `tag:gpu`.

To share machine names, addresses and usernames, point it at a catalog in your
own private Git checkout:

```powershell
.\install.ps1 -IntegrationOnly -SessionPicker -SessionCatalog C:\MyPrivateSetup\connections\catalog.json
```

Device route choices remain local. **S** opens explicit Pull/Publish options;
authentication uses your existing Git sign-in. A failed SSH connection offers
alternative routes and waits for your choice. It never tries a fallback silently.
Groups and tags sync with the catalog and require SSH Sessions 0.4+ on each device.
See the [picker setup and sync guide](https://github.com/brant92good/ssh-session-tui).

The workspace button still opens its paired remote/Ports tabs and optional
local Herdr tab. The picker currently has its own machine catalog; selecting a
picker machine does not retarget those paired tabs. SSH-config ownership and
future agent session policy are [deferred design work](https://github.com/brant92good/ssh-session-tui/blob/main/docs/backlog.md).
Use `-NoSessionPicker` to disable its profile and restore PowerShell as the default.

## Use it every day

Work in your remote shell as usual. Ports now shows all saved servers together;
the chosen workspace's server is selected initially. To open a remote web app,
select a row for its server, press **A**,
enter its port (for example `8000`), then Enter. When it shows ON, **B** opens
its local HTTP address. The remote app must already be running.

![The Ports tab with saved example web apps and notebooks](https://raw.githubusercontent.com/brant92good/port-forward-tui/main/docs/screenshots/connections.svg)

*Example connections in the Ports tab.*

| Key inside Windows Terminal | Action |
| --- | --- |
| Ctrl+Alt+R | Return to a remote tab for this window's machine; open one if needed |
| Ctrl+Alt+P | Return to a Ports tab for this window's machine; open one if needed |
| Ctrl+Alt+L, when enabled | Return to local Herdr |
| Ctrl+Alt+N, with SessionPicker enabled | Open local PowerShell |
| Ctrl+N or Ctrl+T, when explicitly configured | Open the default new-tab profile |
| Add Shift | Open another view |
| F2 inside Ports | Search this Terminal window or all Terminal windows |
| Esc, then H inside Ports | Add/import machines or choose a server without stopping forwards |

These shortcuts apply while Terminal has focus. In the default all-windows
mode, a return shortcut may bring another Terminal window for the **same machine**
forward. The last-focused machine view in the invoking window supplies the
machine context. Selecting a different server's row in Ports updates that tab's
context, so Ctrl+Alt+R follows the selected server. A new workspace window with
several saved machines shows a picker.
Use F2 for the current-window setting. A temporary launcher tab may appear during
the handoff. Moved Herdr tabs may need reopening; split panes are not tracked
as separate tabs.

Closing the terminal leaves background port forwards running. **S** in Ports
stops all listed servers and their pending retries. Interrupted network
connections retry automatically after SSH detects the drop; Enter cancels a
retry and R tries again now. Authentication, host-key and local-port errors need
attention. Reboot or sign-out ends tunnels. Herdr owns
its workspace on the remote server; use its detach command to leave a client.

After updating, close old Ports views and run
`ports.ps1 restart-manager --machine MACHINE_ID` for each running server to load
the new controller. This briefly interrupts and restores its requested forwards;
OFF favorites remain stopped. See the app's
[network recovery and update guide](https://github.com/brant92good/port-forward-tui#when-a-laptop-loses-its-connection).

## What has been checked

Real keyboard tests exercised duplicate tabs, both window scopes, content
focus, and cancellation when another application took focus. A real SSH
forward also carried traffic after its entire test Terminal window closed.
See [test details and reproduction](docs/verification.md).
The optional picker also passed real SSH login, logout back to the list and
the local PowerShell shortcut in one small test-owned window. See the
[picker test and installation details](docs/session-picker.md).

Existing-tab return was measured before and after replacing the old launcher:

| Return shortcut | Old median | New median |
| --- | ---: | ---: |
| Herdr | 1,292 ms | 363 ms |
| Ports | 1,360 ms | 370 ms |

Six keypresses per before/after batch, on one Windows 11 desktop. These are
same-window returns to an already open tab, **not new-window or SSH startup
times**. The [full report](docs/before-after.md) includes raw samples, method,
hardware, and remaining costs. These numbers are not a comparison with other tools.
Those historical batches predate multiple-machine routing. On the current
version, another six-press check measured Ports at **405 ms with one saved
machine / 572 ms with two**, and remote Herdr at **411 / 606 ms** with tracing
enabled. The report records the extra window lookup, conditions and raw samples.

A separate [Python/Rust launcher experiment](docs/language-experiment.md) measured
about 22% lower return latency with Rust in a one-machine setup. It is optional
research code, not the installed launcher or a rewrite of the TUI.

## Check setup or use a coding agent

```powershell
.\doctor.ps1                  # Local checks and next steps
.\doctor.ps1 --json           # The same checks for a script or agent
.\ports.ps1 list --json       # Saved connections and available live state
.\sessions.ps1 doctor --json # Picker setup, when enabled
```

Doctor does not install, change settings or contact SSH. It needs a usable
Windows Python. If the included port app folder is empty, run
`git submodule update --init --recursive` first.

Agents can install with `-IntegrationOnly -NonInteractive`, then use
`ports.ps1 machines add YOUR_SSH_NAME --json` and the returned machine id.
See the port app's [command guide](https://github.com/brant92good/port-forward-tui/blob/main/docs/automation.md).
For repository work, read [AGENTS.md](AGENTS.md).

## Use the same settings on another computer

In your own fork, `config/terminal.json` stores appearance and shortcut
preferences. Each computer keeps paths, client choice and install mode in
ignored `.machine.json`; the port app keeps machines in private local app data.
The included port app is pinned to a specific version.
SSH Sessions is a second independent public app, also pinned as a submodule.
An optional private parent stores personal values and pins this repository;
neither public app requires that private parent.

```powershell
.\sync.ps1             # Download the saved version and apply it here
.\sync.ps1 -Publish    # Export and push portable preferences to your fork
```

Integration-only installs continue to keep local appearance and menu settings
when syncing. Choose `-ApplySharedSettings` on computers where you want the
shared appearance too. Save local Git changes before syncing. Keys and tokens
belong outside Git; a private parent for personal values is optional.

[Technical reference](docs/reference.md) · [Design and scope](docs/design.md) · [MIT license](LICENSE) · [Herdr artwork attribution](NOTICE)
