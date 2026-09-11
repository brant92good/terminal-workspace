# Separate Ports beta setup on Windows

The normal Workspace installation stays on 0.10.0 with Ports 0.9.1. This optional
helper manages a separate Ports beta installation and profile. It is Windows-only;
the standalone Ports installers remain the path for Linux and macOS (beta).

**Helper candidate:** the contract pins the qualified
[Ports 0.10.0-beta.1 release](https://github.com/brant92good/port-forward-tui/releases/tag/v0.10.0-beta.1).
Its [tag workflow](https://github.com/brant92good/port-forward-tui/actions/runs/34643401076)
passed five native platform jobs and five published HTTPS installation jobs.
The integration helper still needs its own reviewed source publication and
device setup; a qualified leaf is not an installed profile. No current Workspace
archive or stable binary is replaced by this source change.

From a checkout of the reviewed integration commit:

```powershell
.\ports-channel.ps1 -Channel stable -Action Status -Json
.\ports-channel.ps1 -Channel beta -Version 0.10.0-beta.1 -Action Plan -Json
```

Local Plan reads files only: no downloads, native process or writes. Stable
Plan/Status never starts Ports. Stable mutation requests are refused; continue
to use the ordinary Workspace installer for stable installation.

After helper qualification, select the exact published integration commit and beta
version. These are separate actions, so installation does not silently copy
favorites or add a profile:

```powershell
$revision = '<reviewed full 40-character integration commit>'
.\ports-channel.ps1 -Channel beta -Version 0.10.0-beta.1 -IntegrationRevision $revision -Action Install -Json
.\ports-channel.ps1 -Channel beta -Version 0.10.0-beta.1 -IntegrationRevision $revision -Action Import -FromDataDir "$env:LOCALAPPDATA\PortForwardTUI" -Json
.\ports-channel.ps1 -Channel beta -Version 0.10.0-beta.1 -IntegrationRevision $revision -Action AddProfile -Json
```

The install path is `%LOCALAPPDATA%\Programs\PortsBeta\bin\ports-beta.exe`.
Data uses `%LOCALAPPDATA%\PortForwardTUI-Beta`. The helper downloads the exact
tagged installer, Windows ZIP and frozen release record, validates pinned hashes,
then invokes the leaf installer with explicit parameters and no PATH addition.
The contract in [ports-channels.json](../config/ports-channels.json) is actually
validated and consumed; unknown fields, pending qualification and mismatches fail.
Environment variables cannot substitute a different bundle, version or destination.
Existing short-name (8.3) ancestors are resolved before checking protected path
overlap. Reparse points and ambiguous paths are refused, including aliases with
a new, nonexistent directory suffix.

Import requires a nonexistent beta destination. It calls the beta's metadata-only
import command; it never copies the source directory itself. Saved machine/forward
metadata is imported, automatic-opening preferences and controller/view state are
excluded, and no SSH connection starts. If beta data already exists, keep it or
choose a new explicit `-DataDir`. Do not delete it just to rerun this command.

AddProfile writes one owned UTF-8 Windows Terminal fragment named **Ports (BETA)**.
It does not edit `settings.json`, default profiles, hotkeys or workspace tabs.
The profile invokes the exact beta path and data directory. Identical repeated
calls are harmless; different requested paths require explicit RemoveProfile
before AddProfile. Edited, partial or unknown files are retained for inspection.
RemoveProfile also remains available when the beta contract is pending, because
it only removes a verified owned fragment and needs no installed binary.

```powershell
.\ports-channel.ps1 -Channel beta -Version 0.10.0-beta.1 -IntegrationRevision $revision -Action RemoveProfile -Json
```

The fragment lives under the current user's
`Microsoft\Windows Terminal\Fragments\TerminalWorkspace.PortsBeta` directory.
Standard menus that include remaining profiles can expose it; custom fixed menus
or disabled fragment sources may hide it. The helper reports profile visibility
as unobserved and never rewrites your menu to force it. A created JSON file is not
proof of a physical menu click or focus behavior. See Microsoft's
[fragment contract](https://learn.microsoft.com/en-us/windows/terminal/json-fragment-extensions).

## Use without a source checkout

`bootstrap-ports.ps1` requires `-IntegrationRevision` and downloads the helper,
common functions and contract from that same immutable public commit. No Git,
Python or compiler is required. The first qualified publication will provide
its exact commit here; no moving-main command is supplied for this candidate.

Remote bootstrap Plan necessarily fetches source into a temporary directory;
it does not fetch leaf binaries or alter product/data/profile paths. Every later
action uses the same helper. Normal Workspace bootstrap behavior is unchanged.

## What stays stable

The existing workspace remains Remote (selected), optional Local, Ports, optional
SFTP. Normal new tabs still use SSH Sessions when enabled. This helper neither
repins the bundled Ports dependency nor changes existing return shortcuts.
Windows Files is also unrelated to this Ports setup and to the SSH Files leaf.

To return to stable, use the original workspace or stable Ports command and its
preserved data. Remove only the optional beta fragment if desired. This helper
does not uninstall programs, delete saved data or stop any controller. Stop
beta-owned forwards explicitly in the beta when appropriate. A future beta data
downgrade needs that version's compatibility policy; reinstalling an old binary
alone does not prove its data can be read safely.

The helper reports actual file hashes and a caller-declared integration revision.
The remote bootstrap establishes which source commit it downloaded; a local
caller must independently verify its checkout. Source fixtures, published HTTPS
installation and a device's applied receipt are separate qualification stages.
The optional private setup uses its existing request ledger for those records.
