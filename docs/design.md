# Scope and installation choices

Terminal Workspace connects an existing remote terminal and a saved-port app
to Windows Terminal. Its main job is opening that pair and returning to the
appropriate existing view. Portable appearance settings are optional.

## Why a separate repository

Port Forward TUI can be used without Herdr or this setup. It owns favorites,
the TUI, connection commands and the background SSH processes. This repository
owns the two-tab button, Herdr tab registration, Terminal profiles, return
shortcuts and settings export. Keeping it separate lets port-only users avoid
the Herdr and workspace setup prerequisites.

The app is a Git submodule: a separate repository whose exact commit is
recorded here. `git clone --recurse-submodules` downloads that version. A
private parent can pin this repository and other personal tools, but public
users do not need one.

## Add integration without replacing preferences

Developers may already have a default shell, themes, fonts and a custom menu.
The public quickstart uses `-IntegrationOnly` to add the managed Herdr/Ports
profiles, shortcuts and button while keeping those preferences. Conflicts
with unrelated shortcut bindings still stop installation.

`-ApplySharedSettings` additionally applies `config/terminal.json`, sets
PowerShell 7 as default, and applies the menu preference. The selected mode
is stored in local `.machine.json`, so updates do not silently switch it.
Existing installations without the field keep their original behavior.

Switching to integration-only does not undo earlier settings changes; it
preserves the current values. Settings backups support selective recovery.
See [setup details](setup.md).

## Current boundary

This is a Herdr-and-Ports setup for Windows, with one SSH destination per app
data folder. It is not a general plugin host or fleet configuration system.
Making Herdr optional or packaging a self-contained installer would be a
separate product change, with its own install and update testing. The current
installer openly lists its prerequisites.

The READMEs show what the tools do, a first usable example and verifiable
test results. They do not claim installation times, customer adoption or
performance on machines that have not been measured.
