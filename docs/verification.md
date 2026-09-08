# Verification

Results recorded on September 8, 2026. The desktop checks used Windows 11
Pro build 26200, Terminal 1.24.11911.0, PowerShell 7.6.5, Python 3.12.11 from
Miniforge, and an existing SSH destination. Another physical laptop remains
untested.

The multi-machine update passed **24 local Terminal tests**, including an
installation with no host and no Herdr, optional local Herdr, distinct R/L/P
bindings, and machine-specific companion-tab arguments. The port app passed
71 local tests and its Windows Python matrix; private setup passed 12 tests.

Real desktop checks passed again after installing this update: the optional
three-tab launcher opened remote, Ports and local Herdr, leaving remote selected.
R/P returned correctly for both scopes and duplicate MRU cases; L returned to
local Herdr across windows and respected the current-window scope. Delayed
lookups left another focused application alone.

[check_machine_routing.py](../scripts/check_machine_routing.py) additionally
opened two machine profiles, made the other profile's target more recent, and
verified R/P still returned to the invoking window's machine. An A Ports view
in B's window returned to A's remote session. Both profiles used one physical
SSH endpoint (one through Herdr, one through ordinary SSH with an explicit
login port), so this is routing evidence rather than a two-server network test.
Original favorites stayed byte-for-byte unchanged; temporary windows and the
second profile/controller were removed.

Reproduce that opt-in check using an existing machine with default SSH settings:

```powershell
.\apps\port-forward-tui\.venv\Scripts\python.exe -E -s scripts/check_machine_routing.py --yes --machine YOUR_SSH_NAME
```

The latency figures below predate multiple-machine routing. Resolving context
adds a lookup when several machines are saved; no new timing claim is made.

Earlier baseline checks:

| Behavior | Observed check | Reproduction/source |
| --- | --- | --- |
| Return to the right existing view | Real keypresses for both apps, duplicate tabs, both window scopes, keyboard content focus, new-view fallback and cancellation after another app took focus | [check_interactive.py](../scripts/check_interactive.py) |
| Keep a tunnel after closing its window | Started an isolated forward with the TUI, closed its whole test Terminal window, then read an SSH banner through the same live tunnel | [check_terminal_persistence.py](../scripts/check_terminal_persistence.py) |
| Shortcut timing | Six actual presses in each before/after batch; destination positioned so adjacent-tab selection could not falsely pass | [Report, conditions and raw samples](before-after.md) |
| Preserve Terminal preferences with `-IntegrationOnly` | Fixtures with a custom default shell, theme, font, profile visibility, menu and unrelated shortcuts; repeat install; switch to shared settings | [test_configure.py](../tests/test_configure.py) |
| Apply settings and manage launchers | 20 automated tests, including JSONC parsing, original settings backup and concurrent-edit protection | [Windows CI](https://github.com/brant92good/terminal-workspace/actions/workflows/test.yml) |

The integration-only checks exercise real settings-file reads and writes in
temporary folders; they do not change the user's installed Terminal settings.
The desktop tests above predate this install-mode addition. The focus helper
and launch commands were unchanged by it.

From an installed checkout:

```powershell
.\apps\port-forward-tui\.venv\Scripts\python.exe -E -s -m unittest discover -s tests -v
```

Desktop checks **move real windows and use the configured SSH connection**.
Run them when it is okay to interrupt your desktop:

```powershell
.\apps\port-forward-tui\.venv\Scripts\python.exe -E -s scripts/check_interactive.py --yes
.\apps\port-forward-tui\.venv\Scripts\python.exe -E -s scripts/check_terminal_persistence.py --yes
```

They create temporary views/connections and clean up their own resources.
Windows accessibility identity can change when tabs move between windows;
reopen a moved Herdr view if its return shortcut no longer finds it. Separate
split panes are not registered as separate tabs.

Hosted CI does not exercise a physical interactive desktop or your remote
server. The [port app's verification notes](https://github.com/brant92good/port-forward-tui/blob/main/docs/verification.md)
describe its Python matrix, process restrictions, SSH check and screenshot data.
Passing tests on these configurations is evidence for those cases, not a
guarantee across Windows releases or proof of broad external use.
