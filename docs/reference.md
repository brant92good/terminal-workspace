# Command and configuration reference

The compiled `bin/terminal-workspace.exe` provides these commands:

| Command | Purpose |
| --- | --- |
| `doctor --json` | Read-only installation checks |
| `configure` | Render profiles/shortcuts and back up original settings |
| `configure --export` | Export portable appearance and managed shortcuts |
| `configure --dry-run --json` | Print proposed settings without writing |
| `remote` | Select or return to a machine's SSH/Herdr tab |
| `remote --local` | Launch or return to independent local Herdr |
| `files` | Open SFTP on a selected Ports machine or the window's machine |
| `files --machine ID --json` | Preview exact Files argv without launching or changing selection |
| `workspace --window UNIQUE_NAME` | Select a machine, add its companion tabs, then connect |

`--root PATH` selects an installation for commands and diagnostics. Settings are
normally found in Windows Terminal's packaged or unpackaged LocalState directory;
`configure --settings PATH` permits an isolated fixture or explicit installation.

Machine settings are in ignored `.machine.json`: `remote_client`, `herdr`,
`local_herdr`, `workspace_files`, `session_picker`, `session_catalog`, `integration_only` and optional
`shortcuts`. Existing additional fields are preserved. `config/terminal.json`
contains shareable presentation settings and default managed shortcut choices.
Export excludes shell commands, addresses, startup actions and working directories.

`remote --machine ID`, `--machines`, `--focus-existing` and `--data-dir PATH`
mirror the paired workspace's Ports machine-selection behavior. The parent calls
`ports machines pick --json`: its terminal UI uses stderr, then stdout returns
one selection object. Cancellation returns a null machine and opens no companion
tabs. SSH Sessions has its own catalog; those machine IDs are not interchangeable.

`configure --workspace-files` enables the SFTP companion; `--no-workspace-files`
disables it. This opt-in does not control the always-available SFTP menu profile.
`files --machines` forces an interactive Ports picker. JSON preview requires an
explicit machine and cannot open a picker. Relative custom config paths are made
absolute before handing off; workspace tabs retain the selected destination even
if a catalog selection changes afterward.

The install wrappers expose the most common choices; see [setup](setup.md).
`sessions.ps1` adds the saved SSH catalog argument before calling the leaf binary.
`ports.ps1` passes arguments directly to Ports.
`sessions.ps1 files MACHINE_ID --route ROUTE_ID --json` prints the frozen Files
command without launching the UI or SSH. Without `--json`, it opens the companion
in the current terminal. The bundled binary is discovered beside SSH Sessions;
the leaf also supports an explicit absolute `SSH_FILES_BIN` override.

## Shared preferences

In a source fork, `sync.ps1` pulls the saved parent revision and applies its
released binaries/settings. `sync.ps1 -Publish` exports portable preferences,
commits that file and pushes to the fork's main branch. Git is optional for normal
installation and required only for this explicit source-sync workflow. Uncommitted
changes stop a pull; child source pins must be advanced deliberately.

## Developer checks

```powershell
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_native.ps1
```

Build output defaults to `artifacts/native-build`. The actual-bundle tests are
opt-in and write only owned temporary directories; PowerShell 5.1 and 7 must be available:

```powershell
$env:WORKSPACE_TEST_BUNDLE = 'C:\Downloads\terminal-workspace-x86_64-pc-windows-msvc.zip'
cargo test --locked --test native_install -- --ignored
./scripts/check-captured-save.ps1 -Bundle $env:WORKSPACE_TEST_BUNDLE
```

These three checks cover fresh/update integrity, exact legacy bootstrap migration,
quoted/Unicode JSON pipelines and normal/interactive-picker console input. They
also verify the adjacent Files command, distinct alias/address arguments,
license checksums, incomplete-update refusal and SourceCheckout preservation. The
separate captured-save runner checks direct and PowerShell-wrapped first mutations
and controller restarts outside Cargo's process job. Hosted Windows runs use the
CI-only verified WMI harness. After publishing a prerelease, check the real versioned HTTPS
bootstrap, installer and release downloads without touching the desktop:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check-native-release.ps1 -Version 0.9.0
```

Older Python scripts and measurements remain reference/compatibility material;
they are not invoked by the native installer or production launch paths. Desktop
tests must use owned windows and explicit foreground guards. See [verification](verification.md).
