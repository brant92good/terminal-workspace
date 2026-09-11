<img src="docs/brand/mark.svg" width="112" align="right" alt="Terminal Workspace logo">

# Terminal Workspace

**Your servers, shells, and tunnels in one keyboard workflow.**

Give Windows Terminal a searchable SSH picker, saved port forwards, and shortcuts
that bring you back to the right machine. Run a coding agent on a server, preview
its app on localhost, browse its files, and keep the shell and tunnels within
reach across tabs and windows.

[![Checks](https://github.com/brant92good/terminal-workspace/actions/workflows/test.yml/badge.svg)](https://github.com/brant92good/terminal-workspace/actions/workflows/test.yml)
[![Windows](https://img.shields.io/badge/integration-Windows-65d6be)](docs/platforms.md)
[![MIT](https://img.shields.io/badge/license-MIT-65d6be)](LICENSE)

[Install](#install) · [Daily use](docs/daily-use.md) · [Standalone apps](#use-only-what-you-need) · [Setup help](docs/setup.md)

![SSH Sessions: choose a server or local terminal](https://raw.githubusercontent.com/brant92good/ssh-session-tui/v0.8.0/docs/screenshots/picker.svg)

*The included SSH Sessions picker, using example machines.*

> **Current stable bundle: 0.10.0.** Includes the Files server/path chooser,
> Remote–Local–Ports–SFTP order, grouped Ports rows and updated file controls.
> Check [downloads and release status](https://github.com/brant92good/terminal-workspace/releases/tag/v0.10.0)
> for availability and [verification](docs/verification.md) for qualification.
> The [previous qualified 0.9.0 instructions](https://github.com/brant92good/terminal-workspace/blob/v0.9.0/README.md)
> remain available. Files and taskbar grouping remain beta.

## Install

Optional Windows Ports beta setup is being qualified separately. Its
[explicit channel helper](docs/ports-beta-setup.md) leaves the normal bundle,
workspace tabs and hotkeys unchanged and pins the separately qualified
Ports 0.10.0-beta.1 release. The helper's source publication and device setup
remain separate steps.

On **Windows 10/11 x64**, with Windows Terminal, PowerShell 7 and OpenSSH Client:

The pinned command uses the stable bundle's compiled assets.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/brant92good/terminal-workspace/v0.10.0/bootstrap.ps1 | iex"
```

Setup downloads compiled apps and checks their SHA256 hashes. It needs no Python,
Rust toolchain or Git. No server address is required during installation.

Open **Terminal Workspace** from Start. Add a machine or import an SSH alias,
then choose it. The remote tab opens first, optional Local Herdr follows, then
**Ports**, with the remote tab selected. Ordinary new tabs open the SSH picker; **Ctrl+Alt+N** opens local
PowerShell. Appearance and menus stay as configured.

[Prerequisites, options and updates](docs/setup.md) ·
[What setup changes](docs/setup.md#what-changes)

## Keep the loop short

| You want to… | Do this |
| --- | --- |
| Open a server in a new tab | Use **+** or **Ctrl+Shift+T**, then search or choose a numbered favorite |
| Return to this machine's shell | **Ctrl+Alt+R** |
| Return to this machine's saved tunnels | **Ctrl+Alt+P** |
| Open another view | Add **Shift** to the R/P shortcut |
| Work locally | **Ctrl+Alt+N**, or the picker's Local terminal row |
| Browse a server's files | Select it in the SSH picker and press **X** |
| Choose a server or saved path for SFTP | Choose **SFTP** in Terminal's tab menu |
| Keep return shortcuts inside the current window | **F2** in Ports |

The shortcuts apply while Windows Terminal has focus. With several windows open,
the invoking window's machine context determines the target; the most recently
used matching view wins. The current-window setting keeps that search local.

![Saved forwards grouped by server](https://raw.githubusercontent.com/brant92good/port-forward-tui/v0.9.1/docs/screenshots/connections.svg)

*Ports with example servers and simulated connection states.*

For a dev server on remote port **8000**, type `8000` in Ports and press **Enter**.
When it shows **ON**, press **B** to open `http://localhost:8000`. Several servers
can forward at once. A background controller keeps active forwards independent
of the views and retries recoverable network failures. Stop forwards explicitly
when finished; reboot and sign-out end the connections.

Want the same tunnels ready each time? Select a saved forward and press **E** to
edit **Open automatically**, or use **F2 Settings**. The preference defaults off.
A new Ports view starts your chosen forwards;
already-running ones keep their connections. Refreshing a view leaves manual stops
alone. Returning to an existing view with the shortcut does not start them again.

Prefer **Ctrl+N** for a new tab? Set it once with
`./install.ps1 -SkipDependencies -NewTabShortcut ctrl+n` in the installed directory.
[Keyboard and machine-selection details](docs/daily-use.md).

## Files on the route you selected

To include SFTP whenever you open the workspace, run this from its installed folder:

```powershell
.\install.ps1 -SkipDependencies -WorkspaceFiles
```

The button opens Remote, optional Local Herdr, Ports, then SFTP, with Remote selected.
The SFTP tab shows your SSH catalog's groups, servers and saved paths before connecting. Use
`-NoWorkspaceFiles` to turn off the extra tab; the **SFTP** profile stays installed.
If you maintain a custom tab menu, [add SFTP to it](docs/setup.md#custom-tab-menus).

Select a server in the SSH picker and press **X**. SSH Files opens local and remote
panes on that machine's selected route. Mark files, review their destinations,
and start the queue while you keep browsing. Close Files to return to the picker.

![SSH Files local and remote panes](https://raw.githubusercontent.com/brant92good/ssh-files/v0.3.0/docs/assets/browser.svg)

*The bundled beta file manager, rendered by the app with example files.*

From the picker, Files uses its selected SSH alias, address and custom config.
The workspace and SFTP menu open that same SSH catalog's Files chooser. They do
not copy a machine ID from the separate Ports catalog. Files adds no address book.
It requires SSH authentication without an interactive
prompt and an already trusted host. Uploads currently need OpenSSH's SFTP hardlink
extension. Existing destinations are preserved, and interrupted or uncertain
transfers stay visible. [Connection requirements and transfer controls](https://github.com/brant92good/ssh-files/blob/v0.3.0/docs/usage.md).

## Use only what you need

- **[SSH Sessions](https://github.com/brant92good/ssh-session-tui)** — searchable
  machines, numbered favorites, groups, SSH import and routes chosen per device.
- **[Ports](https://github.com/brant92good/port-forward-tui)** — saved SSH forwards,
  several servers in one list, background connections and reconnect.
- **[SSH Files](https://github.com/brant92good/ssh-files)** — beta file browsing and
  queued SFTP transfers using your existing SSH setup.
- **Terminal Workspace** — the Windows profiles, paired tabs, return shortcuts and
  optional local/remote [Herdr](https://herdr.dev/) integration around those apps.

All three leaves have their own compiled installers for Windows, Linux and macOS
(macOS **beta**). This repo's Terminal integration is **Windows only**.
[Platform boundaries](docs/platforms.md).

The picker and paired workspace currently have separate machine catalogs.
Selecting a picker machine does not retarget an existing shell/Ports pair.

## Who might find this useful?

Developers who work on remote machines, run agents away from their laptop, or
regularly open remote web apps and notebooks locally. It is also useful when
your shell is already familiar and you want better navigation around it.

A fork can share Terminal appearance and shortcut preferences. An optional
private parent can hold your machine catalog and other personal setup. Public
installs work independently; released bundles pin exact app versions and hashes.
[Settings and repository layers](docs/daily-use.md#use-the-same-settings-on-another-computer).

## Evidence and limits

The 0.10.0 [verification record](docs/verification.md) distinguishes source,
bundle and public-download checks; availability is recorded on its release page.
The previous 0.9.0 prerelease bundle passed native settings and launch checks, actual-ZIP install/update
tests, and public HTTPS installation on PowerShell 5.1 and 7. The checks include
the bundled Files handoff and rejected incomplete updates.
Wrapper JSON pipelines and interactive input are tested through real pseudo
terminals. [Verification and remaining gates](docs/verification.md).
Historical focus/SSH/persistence checks and [timing measurements](docs/before-after.md)
remain available with their versions and conditions; they are not a new Rust
performance claim.

Separate taskbar grouping is **beta**. Explorer's optional **Open PowerShell here**
entry opens the clicked directory locally without changing new tabs; on Windows
11 it appears under **Show more options**. [Taskbar and Explorer details](docs/setup.md#explorer-and-taskbar).

For a script or coding agent, run `./doctor.ps1 --json`,
`./ports.ps1 list --json` or `./sessions.ps1 list --json` from the installation.

[Contributing](AGENTS.md) · [Alternatives](docs/alternatives.md) · [MIT](LICENSE) · [Artwork attribution](NOTICE)
