# Command and configuration reference

The compiled `bin/terminal-workspace.exe` has four commands:

| Command | Purpose |
| --- | --- |
| `doctor --json` | Read-only installation checks |
| `configure` | Render profiles/shortcuts and back up original settings |
| `configure --export` | Export portable appearance and managed shortcuts |
| `configure --dry-run --json` | Print proposed settings without writing |
| `remote` | Select or return to a machine's SSH/Herdr tab |
| `remote --local` | Launch or return to independent local Herdr |
| `workspace --window UNIQUE_NAME` | Select a machine, add its companion tabs, then connect |

`--root PATH` selects an installation for commands and diagnostics. Settings are
normally found in Windows Terminal's packaged or unpackaged LocalState directory;
`configure --settings PATH` permits an isolated fixture or explicit installation.

Machine settings are in ignored `.machine.json`: `remote_client`, `herdr`,
`local_herdr`, `session_picker`, `session_catalog`, `integration_only` and optional
`shortcuts`. Existing additional fields are preserved. `config/terminal.json`
contains shareable presentation settings and default managed shortcut choices.
Export excludes shell commands, addresses, startup actions and working directories.

`remote --machine ID`, `--machines`, `--focus-existing` and `--data-dir PATH`
mirror the paired workspace's Ports machine-selection behavior. The parent calls
`ports machines pick --json`: its terminal UI uses stderr, then stdout returns
one selection object. Cancellation returns a null machine and opens no companion
tabs. SSH Sessions has its own catalog; those machine IDs are not interchangeable.

The install wrappers expose the most common choices; see [setup](setup.md).
`sessions.ps1` adds the saved SSH catalog argument before calling the leaf binary.
`ports.ps1` passes arguments directly to Ports.

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

Build output defaults to `artifacts/native-build`. The actual-bundle test is
opt-in and writes only an owned temporary directory:

```powershell
$env:WORKSPACE_TEST_BUNDLE = 'C:\Downloads\terminal-workspace-x86_64-pc-windows-msvc.zip'
cargo test --locked --test native_install -- --ignored
```

Older Python scripts and measurements remain reference/compatibility material;
they are not invoked by the native installer or production launch paths. Desktop
tests must use owned windows and explicit foreground guards. See [verification](verification.md).
