# Verification

## README and taskbar identity update — September 9, 2026

The 35-test workspace suite passed locally, including a new native taskbar
property test. That test creates two hidden window handles and a temporary
shortcut in a path containing spaces and Chinese characters. It verifies matching
shortcut/window AppIDs, quoted relaunch command, icon path, repeat registration,
missing/invalid origin refusal, and preservation of the other window and foreground.
It does not launch Windows Terminal or log into a server.

Hosted checks exposed WScript.Shell rejecting the fixture's Unicode executable
path before identity registration; expanding the runner's short TEMP path did
not fix it. Shortcut creation now uses Windows' Unicode `IShellLinkW` interface
directly, in both installation and tests. Tests read the saved target back and
check that matching-pin updates preserve unrelated and malformed shortcuts.

The installed workspace executable was rebuilt and its existing Start, desktop
and taskbar shortcuts registered with the same ID. An earlier icon experiment
restored its window properties after the test and was never part of that launcher.
The new implementation applies the ID at explicit workspace startup and leaves
it for the window's lifetime. Explorer grouping, pin activation, cached pins and
dragged-tab behavior still need a real desktop check; the feature is labeled beta.

All three public READMEs were rendered in light/dark desktop layouts and a narrow
layout using a headless browser. Relative documentation links and anchors were
checked, and the screenshots use example metadata. The SSH picker screenshot
was regenerated through its actual UI to show the current local shell label.

Results recorded on September 8, 2026. The desktop checks used Windows 11
Pro build 26200, Terminal 1.24.11911.0, PowerShell 7.6.5, Python 3.12.11 from
Miniforge, and an existing SSH destination. Another physical laptop remains
untested.

## Launcher language experiment and focus isolation — September 9, 2026

The [Python/Rust report](language-experiment.md) records 12 real keypresses per
variant per app: 72 successful returns, eight preparation-contract checks and
four mini-application cancellation checks. Both timing drivers also refused to
activate or send keys when the mini app had focus. The final window-ownership
changes passed separate two-keypress smoke checks for the language harness
and the older benchmark. These smoke samples are not part of the headline table.

The new-view Herdr launcher now discards inherited pane identity only after
registering a separate Terminal tab. Twenty-six Terminal tests passed, including
preservation of developer environment settings. Existing-tab return remains on
the installed Python path; Rust is optional research code with incomplete
machine-selection/fallback behavior.

The [setup guide](setup.md#taskbar-icon-and-closing-tips) records taskbar grouping
status and the built-in way to dismiss the termination
tip while retaining useful error output. Test windows were closed and temporary
benchmark bindings removed. No native return launcher was installed by this work.

## Combined server list and automatic reconnect — September 9, 2026

The pinned port app is v0.6.0 / **42b32cf**, with 88 local tests and passing
[main](https://github.com/brant92good/port-forward-tui/actions/runs/34264686897)
and [release](https://github.com/brant92good/port-forward-tui/actions/runs/34265018250)
Windows Python 3.12/3.13/3.14 CI. Terminal setup passed its 24 tests and the
private setup passed 12 tests against that app version.

The real machine-routing check now selects B's row inside an A-initialized
combined Ports view, verifies that view's registration moves to B, and presses
Ctrl+Alt+R to reach B's remote tab. Selecting A again returns to A. Existing
cross-window and mixed-machine checks passed. Both profiles use the same
physical SSH endpoint, with independent identities and connection settings.

The full R/P/L desktop check passed both scopes, duplicate MRU selection, new
views, and delayed-lookup cancellation while another application had focus.
The current overview also passed the whole-Terminal-window persistence check
with real SSH traffic. That test now waits for the controller to appear after
the first Start key: opening an overview alone no longer starts controllers.

The app's [recovery test](https://github.com/brant92good/port-forward-tui/blob/main/scripts/check_reconnect_live.py)
verified two simultaneous forwards, interruption of one isolated TCP relay,
automatic recovery after closing the overview, and stop-while-offline
cancellation. Actual laptop suspend/resume and Wi-Fi roaming remain untested;
see its [evidence and limits](https://github.com/brant92good/port-forward-tui/blob/main/docs/verification.md).

The multi-machine update passed **24 local Terminal tests**, including an
installation with no host and no Herdr, optional local Herdr, distinct R/L/P
bindings, and machine-specific companion-tab arguments. The port app passed
71 local tests and its Windows Python matrix; private setup passed 12 tests.

Real desktop checks passed again after installing this update: the optional
three-tab launcher opened remote, Ports and local Herdr, leaving remote selected.
R/P returned correctly for both scopes and duplicate MRU cases; L returned to
local Herdr across windows and respected the current-window scope. Delayed
lookups left another focused application alone.
The completion check also pressed Ctrl+Alt+Shift+L and verified returning to
both the older and newer duplicate local view after each became most recently
used. Opening the installed taskbar shortcut produced the same three-tab order
and initial remote focus. A fresh real SSH traffic check with the current app
passed after closing its whole temporary Terminal window.

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

The [timing report](before-after.md#current-version-cost-of-multiple-machine-routing)
now includes six samples each for one and two saved machines: Ports medians
404.8/571.6 ms, instrumented remote Herdr 410.6/606.2 ms. Machine/window selection
took 0.47/182.96 ms mean in the Herdr traces. The second profile remained dormant;
these are same-window timings on this desktop, with raw samples retained.

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

## SSH picker integration

The optional new-tab picker passed a real remote/local handoff test in a small
owned window. [Steps, scope and limits](session-picker.md#verification-on-september-9-2026).

The September 9 organization update passed all 33 integration tests locally.
SSH Sessions 0.4 adds nested groups, tags, bulk edits and group-aware import;
its leaf passed 79 tests. Ports passed its full 88-test local suite after an
add-form test synchronization adjustment; the initial hosted failure and
reproduction limits are recorded in its verification document.
App and setup wording was reviewed, and the README screenshots were regenerated
from the actual apps with example data. This update does not change shortcut
timing, focus selection or background-forwarding behavior. No visible windows
were activated during these feature checks. Platform support is documented in
the [source-based assessment](platforms.md); no Linux/macOS run is claimed.

The pinned SSH release passed its [Python 3.12/3.13 CI](https://github.com/brant92good/ssh-session-tui/actions/runs/34344370866).
The pinned Ports release passed its [Python 3.12–3.14 CI](https://github.com/brant92good/port-forward-tui/actions/runs/34344953326)
after rerunning a hosted native accessibility-probe timeout. No native focus
code changed in this release.
# Automatic installation and portable SSH leaf (2026-09-09)

SSH Sessions 0.5.0 passed its 83-test suite on Windows, Ubuntu and macOS with
Python 3.12/3.13 ([six-job run](https://github.com/brant92good/ssh-session-tui/actions/runs/34352141990)).
Windows runs 80 tests with three platform skips; Unix runs 82 with one skip.
Each OS also passed fresh installation, PATH setup and repeat installation,
including space/Chinese paths, inherited Python settings and catalog/favorite
preservation. The Unix pseudo-terminal test uses `/bin/sh`: command input,
Ctrl+C, resize, exit and returning to the picker. Remote SSH login in macOS/Linux
terminal applications remains unqualified; the full workspace remains Windows-only.

The test work found inherited PowerShell module/shell markers, Windows short
path aliases and code-page assumptions, and a macOS PTY shutdown wait. These
were corrected rather than treating the first Windows/WSL pass as proof for
other environments. The final PTY harness drains output while waiting for exit,
closes the master before cleanup, and bounds reads and child cleanup.
The published 0.5.0 ZIP and tar.gz archives also passed the isolated installer
and update check from Windows and WSL after release publication.

The workspace bootstrap was run headlessly on Windows in an isolated directory
containing spaces and Chinese characters. It downloaded the workspace and exact
child commits, downloaded Python 3.12, installed dependencies, built the native
helper/icon and launched the SSH CLI. Repeating it preserved a fixture's local
preferences. `-NoConfigure` kept these checks from applying a second desktop
setup. The 33 existing settings/launcher tests passed separately. The owner's
four tab identities, active controller, HTTP forward, favorites and SSH config
were checked without activation. No alternative project from the survey was
installed or substituted into the running setup.
