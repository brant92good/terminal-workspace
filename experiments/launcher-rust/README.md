# Python/Rust return-launcher experiment

This compares returning to an existing Terminal tab using the installed Python
launcher, a thinner Python control and a Rust launcher. It keeps the same C#
focus helper. **It is not installed by setup and is not a complete replacement.**

[Results, methodology and limitations](../../docs/language-experiment.md).
Normal users do not need Rust or this directory.

## Reproduce

Use Windows, an installed Terminal Workspace checkout and Rust with the MSVC
toolchain. From this repository's root:

```powershell
Push-Location experiments/launcher-rust
cargo build --release --locked
cargo fmt --check
cargo clippy --release --locked -- -D warnings
Pop-Location

.\apps\port-forward-tui\.venv\Scripts\python.exe -E -s experiments/launcher-rust/measure.py --output artifacts/language-headless.json
```

The headless check creates temporary sample records and measures 40 warm
process launches per case. It does not open Terminal or SSH.

Desktop timing needs exactly one saved machine, a reachable remote session,
the compiled native helper, and the normal installed return actions. This is
an intentional restriction to isolate language costs from machine selection.
The benchmark copies the machine's connection choice into temporary data;
it does not copy or start your saved forwards.

```powershell
.\apps\port-forward-tui\.venv\Scripts\python.exe -E -s experiments/launcher-rust/measure.py --desktop ports --yes --output artifacts/language-ports.json
.\apps\port-forward-tui\.venv\Scripts\python.exe -E -s experiments/launcher-rust/measure.py --desktop herdr --yes --output artifacts/language-herdr.json
.\apps\port-forward-tui\.venv\Scripts\python.exe -E -s experiments/launcher-rust/check_cancellation.py --yes --output artifacts/language-cancellation.json
```

Desktop tests open small windows and move focus between their own tabs. Timing
uses temporary Ctrl+Alt+F9/F10/F11 bindings, refuses conflicts and removes them
afterward. Switching to another application stops timing. The cancellation
check uses synthetic records plus a mini application; it needs no SSH machine.
Run these when brief focus changes to small test windows are acceptable.

`--debug --debug-variant rust` runs one block with native tracing. Debug output
may contain local view details; keep `artifacts/` private. Debug samples are
not comparable with the uninstrumented headline table.

## Scope of the interface

The plan contains `mode` (`ports` or `records`), `views`, `settings`, and `helper`
paths. Optional `trace` enables native diagnostics. `--prepare` prints the
current scope, helper argument flag and live-record payload without focusing.
`--noop` measures executable startup only.

Machine selection, new-view fallback, TUI rendering and SSH control are outside
this interface. Never configure this experimental executable as the normal
shortcut without implementing and checking those missing paths. Temporary
plans can contain private paths and belong outside version control.
