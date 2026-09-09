# Scope and installation choices

Terminal Workspace connects an existing remote terminal and a saved-port app
to Windows Terminal. Its main job is opening that pair and returning to the
appropriate existing view. Portable appearance settings are optional.

## Why a separate repository

Port Forward TUI can be used without Herdr or this setup. It owns favorites,
the TUI, connection commands and the background SSH processes. This repository
owns the workspace button, remote/local tab registration, Terminal profiles,
return shortcuts and settings export. Ordinary SSH is the public default;
Herdr and a third local Herdr tab are optional.

The app is a Git submodule: a separate repository whose exact commit is
recorded here. `git clone --recurse-submodules` downloads that version. A
private parent can pin this repository and other personal tools, but public
users do not need one.

## Add integration without replacing preferences

Developers may already have a default shell, themes, fonts and a custom menu.
The public quickstart uses `-IntegrationOnly -SessionPicker` to add the managed
profiles, shortcuts and button, preserve appearance/menu, and deliberately set
SSH Sessions as the ordinary new-tab default. Conflicts
with unrelated shortcut bindings still stop installation.

`-ApplySharedSettings` additionally applies `config/terminal.json`, restores
the saved SSH-picker or PowerShell default, and applies the menu preference. The selected mode
is stored in local `.machine.json`, so updates do not silently switch it.
Existing installations without the field keep their original behavior.

Switching to integration-only does not undo earlier settings changes; it
preserves the current values. Settings backups support selective recovery.
See [setup details](setup.md).

## Current boundary

Machines are selected at runtime. The independent port app owns manual entry,
opt-in SSH-config import, and separate data folders/controllers per machine.
Old favorites and their running controller stay in place during upgrades.
Installation downloads compiled apps and creates Terminal integration without requiring
a host. A fresh public installation does not require Herdr.

The workspace picker opens a remote session and Ports for the same machine.
An optional third tab opens local Herdr. Return shortcuts resolve the invoking
Terminal window by a unique title marker, then use its last-focused registered
machine view. Candidate tabs are filtered by machine before applying the saved
window scope and most-recent-focus ordering. A window without a known machine
asks the user when several machines are saved; it does not guess another
window's machine. This extra window lookup is skipped for a single saved machine.

Session identity is independent of display titles. Local Herdr has its own
registry, separate from remote sessions. The port app's context format contains
machine IDs and window/view identity, with no dependency on Herdr. Custom SSH
config/port overrides use the ordinary SSH client, which supports those options.
The current launcher does not preserve SSH shell sessions after their terminal
closes; Herdr supplies that behavior when selected. Packaged prerequisites and
general terminal-plugin support remain outside this implementation.

The READMEs show what the tools do, a first usable example and verifiable
test results. They do not claim installation times, customer adoption or
performance on machines that have not been measured.
