<img src="docs/brand/mark.svg" width="112" align="right" alt="Terminal Workspace logo">

# Terminal Workspace

**A Termius alternative for developers working with coding agents.**

Run the agent on your server. Open the dev app on `localhost`. Keep the SSH
session and its saved port forwards together in Windows Terminal, and get back
to either with a shortcut.

Choose a machine when you open a workspace. New tabs give you a searchable SSH
picker, with numbered favorites and a local shell.

[![Checks](https://github.com/brant92good/terminal-workspace/actions/workflows/test.yml/badge.svg)](https://github.com/brant92good/terminal-workspace/actions/workflows/test.yml)
[![Windows](https://img.shields.io/badge/platform-Windows-65d6be)](docs/platforms.md)
[![MIT license](https://img.shields.io/badge/license-MIT-65d6be)](LICENSE)

[Install](#set-up-on-windows) · [Daily use](#use-it-every-day) · [Setup help](docs/setup.md) · [Report a problem](https://github.com/brant92good/terminal-workspace/issues)

![SSH Sessions: choose a server or a local terminal in a new tab](https://raw.githubusercontent.com/brant92good/ssh-session-tui/main/docs/screenshots/picker.svg)

*SSH Sessions, the new-tab picker included in the workspace. Example machines.*

## Set up on Windows

You need **Windows 10/11, Windows Terminal, PowerShell 7 and OpenSSH Client**.
The installer downloads the apps and their Python runtime; you don't need Git
or a Python installation. [Help with prerequisites](docs/setup.md).

Paste into PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/brant92good/terminal-workspace/main/bootstrap.ps1 | iex"
```

Open **Terminal Workspace** from Start or the desktop. Press **A** to add a
machine, or **I** to import SSH names. Setup doesn't ask for a host.
The selected machine opens with its **remote tab first and Ports second**,
leaving the remote tab selected.

New tabs open **SSH Sessions**. **Ctrl+Alt+N** opens local PowerShell directly.
Your Terminal appearance and menu are preserved. Run the same install command
again to update. [What setup changes, custom options and source installs](docs/setup.md).

This integration is **Windows only**. The standalone SSH picker also has
**macOS/Linux beta** installers; Ports and the workspace hotkeys aren't ported
yet. [Platform status](docs/platforms.md).

## Who is this for?

- You develop on a remote machine and keep opening its web app, notebook or dashboard locally.
- You lose track of shell and port-forward tabs across several Terminal windows.
- You work with a coding agent on a server and want a quick way back to the shell and preview.
- You want to carry your Terminal preferences to another Windows laptop.

If you only need the server picker or saved forwards, the two apps also work
independently: [SSH Sessions](https://github.com/brant92good/ssh-session-tui)
and [Port Forward TUI](https://github.com/brant92good/port-forward-tui).

## Use it every day

Start your web app on the remote machine, then type its port, such as **8000**,
in Ports and press **Enter**. When the connection is ON, **B** opens
`http://localhost:8000`. Saved connections from several servers share one list.

![Ports shows saved connections grouped by server](https://raw.githubusercontent.com/brant92good/port-forward-tui/main/docs/screenshots/connections.svg)

*The included Ports app, with simulated connection states and example servers.*

| While Windows Terminal has focus | Action |
| --- | --- |
| Ctrl+Alt+R | Return to the remote tab for this window's machine |
| Ctrl+Alt+P | Return to its Ports view |
| Add Shift to R or P shortcuts | Open another view |
| Ctrl+Alt+N | Open local PowerShell |
| F2 inside Ports | Choose return targets in this window or across all Terminal windows |

Return shortcuts open a tab if there isn't one to return to. Multiple Ports
views share the same background connections. Closing Terminal leaves forwards
running; network interruptions retry, while authentication and port conflicts
need attention. Reboot or sign-out ends active forwards.

Prefer **Ctrl+N** or **Ctrl+T** for a new tab? Both are optional
[setup choices](docs/daily-use.md#choose-a-server-in-every-new-tab).
The picker includes numbered favorites, nested groups, SSH import and routes
you can choose separately on each computer.

The picker and paired workspace tabs currently use separate machine catalogs.
Choosing a server in the picker doesn't retarget an existing remote/Ports pair.
[Daily-use guide](docs/daily-use.md) explains machine selection, window scopes and updates.

## Optional Herdr sessions

Ordinary SSH works by default. If you use [Herdr](https://herdr.dev/), enable it
as the remote client and optionally add a third tab for local Herdr.
**Ctrl+Alt+L** returns to the local Herdr tab.
[Enable Herdr](docs/setup.md#source-checkout).

The Start/desktop button can be pinned to the taskbar. Its running windows use
Windows Terminal; see the [taskbar behavior](docs/setup.md#taskbar-icon-and-closing-tips).

## Bring your settings to another laptop

A fork can hold your shared appearance and shortcut preferences. Each computer
keeps its paths and installation choices locally. An optional private parent
repository can store your machine catalog and other personal setup.

The workspace pins both apps to specific commits, so an update gets a known
combination. [Settings sync and repository layout](docs/daily-use.md#use-the-same-settings-on-another-computer).

## What has been checked

Real Windows desktop checks cover return shortcuts across tabs and windows,
remote SSH login, and a forward carrying traffic after its entire Terminal
window closed. CI checks settings changes and fresh installation/update in an
isolated directory. [Evidence and reproduction](docs/verification.md).

The [latency report](docs/before-after.md) shows measured shortcut timings and
their conditions. The [Python/Rust experiment](docs/language-experiment.md)
records what a native launcher changed; it isn't the installed launcher.

## Help and automation

From the installed workspace directory, run **`./doctor.ps1`** for local checks
and suggested fixes. Add **`--json`** for a script or coding agent.
**`./ports.ps1 list --json`** lists saved forwards and available live state.

[Agent commands](https://github.com/brant92good/port-forward-tui/blob/main/docs/automation.md) ·
[Working on the code](AGENTS.md) · [Existing alternatives](docs/alternatives.md) ·
[MIT license](LICENSE) · [Herdr artwork attribution](NOTICE)
