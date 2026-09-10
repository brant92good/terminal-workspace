# Working on Terminal Workspace

Read README.md and docs/native-migration.md before changing shipping paths.
This is the Windows integration layer around three independent public leaf apps.
An optional private parent can pin this repository; public installs never need it.

## Behavior contracts

- With SessionPicker enabled, **+**, ordinary **Ctrl+Shift+T**, and optional
  **Ctrl+N/Ctrl+T** open SSH Sessions. **Ctrl+Alt+N** opens local PowerShell.
  An Explorer local-shell entry must not change the global default profile.
- The workspace button selects a machine first, opens remote then Ports then
  optional local Herdr, and leaves the remote tab selected.
- Return shortcuts resolve the invoking window's machine, then its most recently
  focused matching view. Preserve all-window/current-window scopes. Never infer
  identity from adjacency, duplicate titles or current foreground alone.
- Only a verified separate Herdr view drops inherited Herdr pane identifiers.
  Preserve the developer environment. Custom SSH config/port routes use OpenSSH.
- Closing views must not stop saved background forwards. Controller ownership,
  reconnect and cancellation belong to the Ports leaf.
- Shared preferences exclude addresses, command lines and local paths. Preserve
  original backups and reject concurrent settings edits and key conflicts.

## Ownership

| Path | Responsibility |
| --- | --- |
| `src/settings.rs` | Settings renderer, JSONC, export and backups |
| `src/launch.rs` | Machine selection, paired tabs and session launch |
| `src/main.rs` | CLI and read-only diagnostics |
| `scripts/install-native.ps1`, `bootstrap.ps1`, `install.ps1` | Binary distribution/setup |
| `scripts/explorer.ps1` | Owned, removable classic Explorer menu entries |
| `scripts/WorkspaceLauncher.cs`, `TaskbarIdentity.cs`, `WorkspaceShortcut.cs` | Explicit workspace/taskbar identity |
| `apps/port-forward-tui` | Separate repo: tunnels, TUI, shared Windows view/focus API |
| `apps/ssh-session-tui` | Separate repo: picker, routes, import and catalog sync |
| `apps/ssh-files` | Separate repo: beta SFTP browser and transfer queue on a frozen SSH route |
| `config/terminal.json` | Portable preferences |
| ignored `.machine.json` | Device choices and paths |

The two machine catalogs remain independent. The parent calls the documented
`ports machines pick --json` interface with inherited stdin/stderr and captured
stdout. Cancellation creates no companion tabs. Do not guess cross-catalog IDs.
SSH Sessions owns the X action and frozen Files handoff. The parent bundles
`ssh-files.exe` beside `ssh-sessions.exe` for adjacent discovery; Files has no
catalog of its own. Preserve explicit route choices and no automatic fallback.
Include each bundled leaf's license notices; SourceCheckout installs generated
`bin/`, `build/` and `licenses/` files while retaining checked-out source/config.

Read each child's AGENTS.md before editing it. Publish reviewed child versions,
then parent pins, then the optional private pin. Never reset dirty child worktrees
or silently advance their source to main.

## Build and verify

Production uses Rust and precompiled C# Windows helpers. Normal installation
needs no Python, Cargo or Git. Existing Python files are compatibility/reference
material, not production entrypoints.

```powershell
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_native.ps1
```

Native builds go to `artifacts/native-build`, never the live checkout's build/bin
directories. Only the explicit installer replaces production files. The actual
release-bundle test is separately opt-in; see docs/reference.md. Review components,
publish prerelease assets, test those exact HTTPS downloads, then promote the
same bytes. Keep macOS leaf and taskbar beta labels until desktop use is qualified.

Tests must not activate unrelated user windows. Prefer temporary files, owned
pseudo terminals and hidden checks. Desktop testing uses small owned windows
with identity and foreground guards. Independent README review must use final
binaries/installers; historical desktop tests are not a new Rust benchmark.

Taskbar identity uses the unique marker in an explicitly launched workspace
window. Failed lookup keeps ordinary Terminal grouping; no persistent watcher
or surprise activation belongs here. Explorer integration adds a classic entry;
it does not replace Windows 11's modern built-in entry.

Herdr artwork retains NOTICE attribution. Screenshots use demonstration metadata
and must identify simulated connection states.
