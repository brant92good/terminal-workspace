# Optional Files beta chooser

The normal Workspace 0.10.0 bundle remains unchanged: SSH Sessions 0.8.0 and
Files 0.3.0, existing shortcuts and ordinary workspace tabs. This optional
Windows source helper can install a separately qualified Files beta and add a
**Files (BETA)** profile. It does not change the ordinary SFTP profile or open a
connection during setup. Linux/macOS users can use the leaf beta installer;
this Windows profile helper does not qualify their desktop integration.

The checked-in 0.4.0-beta.1 contract binds the independently qualified
[immutable leaf release](https://github.com/brant92good/ssh-files/releases/tag/v0.4.0-beta.1),
including its actual published Windows binary and installer hashes. Its
[tag workflow](https://github.com/brant92good/ssh-files/actions/runs/34649607589)
passed the five native and five HTTPS installation jobs. The optional helper's
own source, chooser-to-beta and personal setup checks remain separate. This
document does not claim it is already installed on your computer. Future pending
contracts still refuse Install, AddProfile and Launch.

## Inspect without changing anything

From a persistent, reviewed Terminal Workspace source checkout:

```powershell
./files-channel.ps1 -Channel beta -Version 0.4.0-beta.1 -Action Plan -Json
./files-channel.ps1 -Channel beta -Version 0.4.0-beta.1 -Action Status -Json
```

Local Plan/Status read and hash files only. They do not download, run an
executable, invoke Git, initialize a catalog or create directories. Missing
catalog/selector prerequisites are reported. The default beta directory is
`%LOCALAPPDATA%/Programs/SSHFilesBeta`; `-WorkspaceRoot` identifies the existing
normal bundle when it differs from this source checkout.

## Set up this qualified beta

Use the integration commit and three source hashes from its reviewed receipt:
`-IntegrationRevision` (40 lowercase hex characters), `-SourceSha256` for
`files-channel.ps1`, `-CommonSha256` for `scripts/files-channel-common.ps1`, and
`-ContractSha256` for `config/files-channels.json`. Mutations and Launch require
all four. The caller verifies their association with the immutable commit;
the helper checks exact bytes before loading the common script. It deliberately
does not query Git at runtime. Recomputing hashes from unknown downloaded code
does not establish that code was reviewed.

With those parameters in a PowerShell splat named `$pins`, and the intended
source checkout/bundle paths already chosen, the actions are:

```powershell
./files-channel.ps1 @pins -Channel beta -Version 0.4.0-beta.1 -Action Install -WorkspaceRoot $workspace
./files-channel.ps1 @pins -Channel beta -Version 0.4.0-beta.1 -Action AddProfile -WorkspaceRoot $workspace -Catalog $catalog -LocalDirectory $local
```

These examples require real `$pins`, `$workspace`, `$catalog` and `$local`
values from your reviewed integration checkout and existing setup.
Install requires neither a host nor a catalog. It fetches only fixed official
tag URLs and checks the installer, binary, checksum sidecar and release record
against the contract before passing that staged binary to the leaf installer.
The leaf performs its bounded version check; no chooser or SSH session opens.
This helper download path is distinct from the leaf's separately qualified
default HTTPS installer path. Existing in-use files may cause an update to
fail; setup never stops your open sessions to force replacement.

AddProfile and Launch require an existing readable SSH Sessions catalog, the
exact baseline selector and an existing local directory. The helper reads no
catalog contents; SSH Sessions retains validation and selection ownership.
There is no catalog import or beta controller. Optional `-StateDir` passes an
explicit device preference location, which may not exist yet. The helper does
not create it; SSH Sessions may initialize it when its own actions require it.
Normally omit it to reuse the selector's normal preferences.
`-LocalDirectory` becomes the child's working
directory and hence the Files local pane; by default it is the user home.

The new fragment lives only in
`%LOCALAPPDATA%/Microsoft/Windows Terminal/Fragments/TerminalWorkspace.FilesBeta`.
Its command references the persistent helper source and freezes the three
source hashes. Do not delete or edit that checkout while using the profile;
later source drift causes Launch to refuse. A helper in temporary storage
cannot create a profile. After a reviewed source/path update, explicitly remove
the old owned profile before adding its replacement. These checks catch source
drift, not malicious same-user replacement of the launcher and its checks.

No settings.json, .machine.json, default profile, keybinding, PATH or existing
fragment is edited. An unchanged owned fragment is idempotent across PowerShell
5.1 and 7; edited or partial ownership is retained for inspection. A custom
Terminal menu or disabled fragment source can hide it. JSON readback does not
prove visible menu placement or focus behavior.

## Use and return to the ordinary version

Select **Files (BETA)**, or run the same helper with `-Action Launch` and the
verified pins/catalog/local arguments. It starts the existing stable
`ssh-sessions --catalog PATH files` chooser, inheriting your terminal streams.
Only the child receives `SSH_FILES_BIN` pointing at the verified beta. The
caller's environment and ordinary sibling tabs keep their values.

The generated profile uses Windows PowerShell 5.1 as its launcher. That exact
path passed four real chooser/SFTP cases with the published Files binary:
pane switching and a selected two-file drag transfer, transfer cancellation,
quitting during a transfer, and closing its ConPTY terminal. Cancellation kept
the browser usable; terminal closure stopped the child processes. These were
owned terminal tests, not a visible Windows Terminal desktop test.

PowerShell 7 setup and source-guard checks also passed. A manual interactive
Launch under the tested MSIX PowerShell 7.6.6 reached the chooser and completed
the transfer case, but its full close/cancel test remains unqualified: packaged
process activation escaped the test Job, and Windows denied explicit Job
assignment. This is a test-containment limitation, not evidence that all
PowerShell 7 launches fail. Use the generated profile for the qualified launch
path; it does not change your default shell.

Choose a group/server and then its home or a saved remote path. R selects a
route once without replacing your device preference. Saved paths still use
the existing catalog's `.files.json` sibling. They are not cloned or migrated;
deliberate chooser edits affect that same saved-path file. Alias, HostName,
custom config and route identity remain the selector's responsibility. A
failure never silently falls back to ordinary SSH or another Files binary.

The personal fourth SFTP tab remains ordinary: current Workspace dispatch
supplies its explicit selector command. Editing a profile commandline cannot
replace that explicit dispatch. A future fourth-tab opt-in needs its own
reviewed parent change; setting a global environment variable is not a shortcut.

Use the unchanged ordinary SFTP entry to return to Files 0.3.0. To remove only
the unchanged owned optional fragment, use the pinned helper with
`-Channel beta -Version 0.4.0-beta.1 -Action RemoveProfile`; no catalog is needed.
Removal does not delete beta binaries or undo file transfers already performed.

Owned fake-download/native-child tests cover this helper's source guards,
installation dispatch, argument/environment handling and fragment ownership.
The actual released chooser-to-beta tests and containment checks are in
`tests/files_channel_pty.rs`; their loopback relay is in
`tests/support/files_channel_gate.rs`.
Public HTTPS and personal installation receipts remain separate gates. None
establishes native Explorer drag-in/out or replaces the unfinished Windows
console-reader experiment.
