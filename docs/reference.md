# Terminal Workspace

A repeatable Windows Terminal setup for PowerShell, WSL, remote Herdr, and
saved SSH port forwards. The desktop/Start shortcut opens Herdr in the first
tab and Ports in the second, with Herdr selected. Its Herdr icon can be pinned
to the taskbar.

This is the public middle layer of a personal setup:

```text
personal-setup (private, optional)
├── terminal-workspace (this public repo)
│   └── apps/port-forward-tui (public submodule)
└── skills (private submodule)
```

You can use this repository on its own. The public tree contains portable
preferences and app launchers. SSH targets and resolved installation paths are
saved locally in the ignored `.machine.json`. Each submodule is pinned to a
specific commit for repeatable installation.

## Install

For adding the apps to an existing Terminal setup, follow the
[public quickstart](../README.md#set-up-on-windows) with `-IntegrationOnly`.
It preserves appearance, default shell and menu and saves that choice locally.
`-ApplySharedSettings` applies the full preferences described below. Older
installs without a saved choice retain that full mode. See [setup options](setup.md).

Prerequisites: Windows 10/11, Git, Python 3.12+, Windows Terminal, PowerShell 7,
Windows OpenSSH Client, and [Herdr](https://herdr.dev/). Configure and verify
your existing SSH alias with `ssh workbox` first. Background port forwards use
SSH keys or ssh-agent.

For missing Windows apps:

```powershell
winget install --id Microsoft.WindowsTerminal -e
winget install --id Microsoft.PowerShell -e
```

Use Herdr's official Windows installation instructions on its website. Then:

```powershell
git clone --recurse-submodules https://github.com/brant92good/terminal-workspace.git
cd terminal-workspace
.\install.ps1 -SshHost workbox
```

Use `-Python C:\path\python.exe` or `-HerdrPath C:\path\herdr.exe` when needed.
Keep the checkout at its installed location. The installer creates an isolated
Python environment, renders app paths, backs up Terminal settings, makes
PowerShell the default, and creates desktop and Start menu shortcuts. Existing
WSL profiles stay visible. Other profiles are hidden when `compactMenu` is true.

Python discovery tries `python.exe`, `py.exe`, then `python3.exe`. Setup validates
the Windows runtime and SSL support, then reuses a healthy app `.venv` or creates
one. Conda users can select their environment for setup; subsequent shortcuts
use the private executable directly without activation or shell profile startup.
Managed Python commands ignore `PYTHONHOME`, `PYTHONPATH`, and user site packages.
Global packages and PATH are preserved. Keep the base Python installed. A broken
`.venv` produces repair guidance and is never automatically deleted. See the
[app installation notes](../apps/port-forward-tui/README.md#set-up) for details.

Right-click **Terminal Workspace** in Start and choose **Pin to taskbar** for
the one-click two-tab launcher.

## Keyboard and focus scope

| Shortcut in Windows Terminal | Behavior |
| --- | --- |
| Ctrl+Alt+H | Return to the most recently focused Herdr view, or open one |
| Ctrl+Alt+Shift+H | Open another Herdr view attached to the same remote session |
| Ctrl+Alt+P | Return to the most recently focused Ports view, or open one |
| Ctrl+Alt+Shift+P | Open another connected Ports view |
| F2 inside Ports | Choose shortcut focus scope |

F2 offers **All Terminal windows** (default) and **Current Terminal window
only**. Both Herdr and Ports read this preference. In current-window mode, a
window with no matching view gets a new one there. Separate views share their
underlying sessions. The Herdr launcher tracks the identity of each Terminal
tab, so duplicate or changing titles do not determine the target.

Return shortcuts use a brief launcher tab, then hand focus over after it
closes. Keyboard focus moves into the terminal content so you can type
immediately. The helper does not raise a window if you switch to another application
during that handoff. These are Terminal shortcuts, not system-wide hotkeys.
Both return shortcuts use a shared focus executable built once during
installation. It waits for launcher closure instead of imposing a fixed pause.
The same helper process performs lookup and the final handoff. Ports skips
loading the TUI, and Herdr matches registered tab identities even when titles
change or duplicate one another.
Manually moving a Herdr tab between windows may require reopening the view to
register its new accessibility identity. Separate split panes are not tracked
as separate Terminal tabs.

Ports keeps tunnels running when every UI closes. Herdr's remote server owns
its panes. Detach Herdr with Ctrl+B then Q. Do not stop the remote server just
to close a client view.

## Share Terminal preferences across computers

`config/terminal.json` stores shared appearance, profile defaults, compact-menu
behavior, and keyboard shortcuts. Install or sync renders each machine's paths.

```powershell
.\sync.ps1             # Pull the shared version and apply it here
.\sync.ps1 -Publish    # Export portable preferences, commit, and push them
```

Export includes presentation settings and these managed shortcuts. It excludes
shell commands, SSH targets, startup commands, and working directories. Your
private top-level repository can store personal values and pin this repo.
Removing a shared preference restores its default on the receiving computer.
Installation also supports a Terminal settings file that has not been created
yet, and existing JSONC files with comments; an existing file is backed up.
Sync refuses to discard local Git edits. Submodules stay at the parent-pinned
version; update the child commit deliberately when adopting an app update.

## Verification

```powershell
python -m unittest discover -s tests -v
.\apps\port-forward-tui\.venv\Scripts\python.exe scripts/check_interactive.py --yes
.\apps\port-forward-tui\.venv\Scripts\python.exe scripts/check_terminal_persistence.py --yes
```

The second command is an opt-in desktop test. It opens temporary Terminal
windows, uses the actual keyboard shortcuts, verifies the selected tab and
foreground window, then closes its test windows and restores the focus-scope
preference. It requires an installed setup and a reachable Herdr SSH target.
It also checks switching to another application while shortcut lookup is pending.
It does not stop the shared SSH tunnels or Herdr server. The last command creates
an isolated temporary SSH forward to remote port 22 through a real Ports window,
closes that whole window, verifies SSH traffic still crosses the tunnel, and
explicitly stops its test supervisor. Your existing favorites and tunnels stay
unchanged.

To measure the installed Ports return shortcut:

```powershell
.\apps\port-forward-tui\.venv\Scripts\python.exe scripts/benchmark_switch.py --yes --samples 6 --output artifacts/switch.json
.\apps\port-forward-tui\.venv\Scripts\python.exe scripts/benchmark_switch.py --yes --app herdr --samples 6 --output artifacts/herdr-switch.json
```

These commands use the default Ctrl+Alt+P/H bindings. They open a temporary
window with the target before a source tab and measure until the target has
keyboard focus. The target is deliberately
not adjacent to the temporary launcher, so closing the launcher cannot itself
satisfy the measurement. Compilation and setup are outside the stopwatch. The
report includes every sample and the median; results depend on the machine and
Terminal version. It restores the focus-scope setting and closes its test window.

For opt-in Herdr stage timings, add `--trace`. This temporarily adds a profiling
argument to the Herdr return shortcut, restores its settings afterward, and
records startup, lookup, closure, and focus stages. Normal shortcuts write no
profiling files. The [before-and-after report](before-after.md) compares
stage timings, identifies possible optimizations, and explains environment
differences including Conda. The [earlier profile](latency.md) is retained.

[MIT](../LICENSE). See [NOTICE](../NOTICE) for Herdr artwork attribution.
