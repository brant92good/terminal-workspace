# Verification

## 0.9.0 candidate — September 10, 2026

The candidate adds the SFTP profile and optional fourth workspace tab, and targets
Ports 0.8.0 automatic forwarding. Nineteen local native integration tests, Clippy
with warnings denied, and formatting checks pass. Independent source review passed
frozen destination/config handling, read-only JSON, preserved settings/custom
actions, cancellation and missing-companion preflight. Owned process fixtures
record actual dispatcher arguments without opening Windows Terminal or SSH.
They do not establish physical four-tab focus or taskbar pin behavior.

Release ZIP, hosted package and actual HTTPS installation gates are pending.
The published release and its evidence below remain 0.8.0 until those pass.

## Native 0.8.0 release - September 10, 2026

[Release 0.8.0](https://github.com/brant92good/terminal-workspace/releases/tag/v0.8.0)
is built from immutable `d4d61ba`, with source pins Ports `23e3cef`, SSH Sessions
`1c6dc9a` and Files `bf25010`. It combines Ports 0.7.3, SSH Sessions 0.7.0 and SSH Files
0.1.0 beta binaries. Each leaf passed its own independent source/README/assets
and actual HTTPS installation gates. The parent adds adjacent companion packaging
and notices, without a new transfer launcher or machine catalog.

The local actual-ZIP checks pass with all four program versions and manifest
hashes. A disposable SSH import then verifies `files --json` chooses the actual
adjacent companion over a bad PATH candidate. The exact command preserves a
distinct SSH alias and selected hostname, custom config, user, port, Unicode
label, local directory and machine/route IDs. It opens neither UI nor SSH.
Tampered Files bytes and a removed Files executable/manifest entry are rejected
before installation writes. Existing preferences and the installed binary remain
unchanged. SourceCheckout installs the generated Files runtime and license notices
while retaining local source documentation, Cargo metadata and preferences.

The [hosted exact-pin run](https://github.com/brant92good/terminal-workspace/actions/runs/34462955825)
passed fourteen ordinary tests, Clippy, three actual-ZIP tests and three captured
first-save/restart tests. The ZIP tests retain legacy migration, quoted/Unicode
wrapper pipelines and real ConPTY input coverage. Initial test-only Windows path
and ZIP-entry lookup assumptions were corrected without changing the runtime.
The published ZIP SHA-256 is
`4fa9ffef29e2e0821415064c105f626a1c0f13e87ddbba9c44f44da05d9a2f13`.
Its manifest records all 25 bundled file hashes, including original released
license/notice bytes. After prerelease publication, the advertised public HTTPS
bootstrap, versioned installer and ZIP/checksum passed fresh installation,
update, preserved preferences and isolated settings configuration on PowerShell
5.1 and 7. No local bundle override, app UI, connection or desktop change was used.
Files and macOS remain beta. Existing transfer evidence belongs to the Files
leaf; these package tests make no new desktop, SSH-network or transfer claim.

## Native 0.7.2 release - September 10, 2026

[Release 0.7.2](https://github.com/brant92good/terminal-workspace/releases/tag/v0.7.2)
is built from `b79a408`, recording Ports source `23e3cef` and SSH Sessions source `54a7815`,
packaging the official Ports 0.7.3 and SSH Sessions 0.6.2 Windows releases.
Both leaves passed their independent release and actual HTTPS installation gates.
SSH 0.6.2 clears the visible session display at picker handoffs, preserves shell
history files, and fixes the compatibility picker's Ctrl+C wait race. Its
[release qualification](https://github.com/brant92good/ssh-session-tui/actions/runs/34448027497)
passed all eleven jobs, including five actual HTTPS installer jobs.

The local package and [hosted exact-pin run](https://github.com/brant92good/terminal-workspace/actions/runs/34459179581)
passed fourteen ordinary parent tests, Clippy, three actual-ZIP checks and three
captured first-save/restart checks for the executable and both PowerShell wrappers.
The published ZIP SHA-256 is
`af9ccc9319f6d1a4298efdd3d12b7ee57fee6922dd8e34ef8c467ec6751b66a8`.
After prerelease publication, the actual public HTTPS bootstrap, versioned
installer and release ZIP/checksum passed fresh installation, update, preserved
preferences and isolated settings configuration on both Windows PowerShell 5.1
and PowerShell 7. No local bundle override or desktop change was used.

The opt-in [three-tab fixture](../scripts/check_native_workspace.py) passed an
independent source review and two headless protocol regressions. It has not been
run on the desktop. Its future measurements would qualify programmatic return
routing, not physical hotkey latency or taskbar pin clicks.

## Native 0.7.1 prerelease - September 10, 2026

[Prerelease 0.7.1](https://github.com/brant92good/terminal-workspace/releases/tag/v0.7.1)
is built from `397946b`, recording Ports source `3315744` and SSH Sessions source
`18d3f67`. It packages the official Ports 0.7.3 and SSH Sessions 0.6.0 Windows
binaries. The [exact-pin hosted run](https://github.com/brant92good/terminal-workspace/actions/runs/34444342819)
passes fourteen ordinary parent tests, Clippy, three actual-ZIP checks and three
captured-command checks. The ZIP SHA256 is
`1e301c56f63fb84b204bff3c4ea00b3b8b59e1fd87aaddaf6617639173ec016e`.

Status-only helper dispatch uses a shared Windows creator with an explicit
inherited-handle list. A bounded regression reproduced the old unrelated-pipe
leak and passed after the fix, without opening a desktop window. The direct CLI
and both PowerShell wrapper first-save/restart checks verify outer stdout/stderr
EOF and stdin closure while the controller remains alive. Each checks the new
controller PID after restart, then shuts down only its authenticated fixture.
Copied private wrappers passed the same three cases locally with released bytes.

The actual-ZIP tests cover fresh/update integrity, legacy metadata migration,
quoted/empty/Unicode JSON pipelines and real ConPTY input, including an interactive
machine picker. The separate CI-only WMI harness escapes the hosted runner's
restrictive job and explicitly verifies that its worker and test are job-free;
its captured-command tests passed. This does not modify a local system service.

After publication, PowerShell 5.1 and 7 each downloaded the versioned bootstrap,
installer and real release ZIP/checksum over public HTTPS. Fresh installation,
repeat update, saved preferences and fixture-only settings configuration passed
without a local bundle override or desktop changes.

The independently reviewed [owned-window harness](../scripts/check_native_window_persistence.py)
also passed against that exact published ZIP. Its first OFF-only save originated
inside a real Windows Terminal window measuring 701 × 400 pixels. The captured
CLI exited successfully with pipe EOF; the same controller answered authenticated
RPC after only that owned window was closed. No SSH connection was opened, the
foreground window was unchanged, and cleanup stopped the fixture controller.
This qualifies controller persistence across real Terminal window closure; it
does not test the workspace's three-tab focus or pin-click behavior.

Stable promotion was held for a separate SSH Sessions screen-cleanup patch in a
new immutable parent bundle. The 0.7.1 prerelease assets remain unchanged.
Native shortcut behavior, taskbar pin clicks and focus latency also remain separate
qualifications. Taskbar grouping is beta. Historical measurements below concern
earlier implementations, not this Rust release.

## Native 0.7.0 prerelease - September 10, 2026

[Prerelease 0.7.0](https://github.com/brant92good/terminal-workspace/releases/tag/v0.7.0)
was built from `cbceb19`, with recorded source pins and the official Ports 0.7.1
and SSH Sessions 0.6.0 Windows binaries. The
[hosted package run](https://github.com/brant92good/terminal-workspace/actions/runs/34388272293)
passed thirteen ordinary native checks, Clippy, helper builds and three tests of
the actual packaged ZIP. The archive's SHA256 is
`2448c463ed8703001990c0974e6e49c6a34bae320a47b4d5438cd571af9b24ab`.

The native checks cover settings backups, explicit new-tab behavior, shortcut
conflicts, preserved preferences, JSON errors, machine-specific tab composition,
Explorer's read-only plan and bounded child dispatch. The ZIP tests cover fresh
install/update/checksums/ownership, exact legacy metadata migration, and preserved
settings. Malformed or redirected legacy records fail before destination writes.

PowerShell 5.1 and 7 wrappers were tested with embedded quotes, empty arguments,
trailing backslashes, Chinese text and emoji. JSON remains available to assignment
and `ConvertFrom-Json`. Real ConPTY checks exercise normal TUI input and an
interactive machine picker with its JSON captured through the PowerShell pipeline.
These checks create no desktop windows or live SSH connection.

After publication, the versioned public HTTPS bootstrap downloaded its installer
and that exact release ZIP in disposable Windows directories under both PowerShell
versions. Fresh install, repeat update, saved preferences and fixture-only settings
configuration passed. No local bundle override was used. Independent review also
passed the local actual-ZIP/wrapper gates.

Stable promotion was held after a live check found a captured-output defect. A
first saved rule could start a background controller that inherited the caller's
output handles, delaying EOF after the CLI exited. The initial direct-binary fix
did not cover opaque handles inherited through PowerShell wrappers. Earlier
quoting, pipeline, installation and ConPTY results had not tested that combination.
The candidate fix is recorded above; 0.7.0's published bytes remain unchanged.
Native desktop focus and shortcut latency are separate qualifications. Historical
sections below name earlier versions; their timings are not new Rust measurements.
Separate taskbar grouping remains beta. See [native migration](native-migration.md).

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
