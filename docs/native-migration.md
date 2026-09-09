# Native integration candidate

Terminal Workspace 0.7.1 is a development candidate. The earlier 0.7.0 prerelease
remains immutable. Windows captured-output fixes now pass locally for the direct
Ports CLI, both public/private PowerShell wrappers and parent helper dispatch.
Hosted checks and corrected published leaf bundles are still required before
stable promotion.

## Production paths

`terminal-workspace.exe` owns settings rendering/export, diagnostics, paired tab
composition and remote/local Herdr or SSH launch. Profiles call the installed
`ssh-sessions.exe` and `ports.exe` directly. Taskbar identity and accessibility
helpers remain compiled C# programs using the Windows .NET Framework; no Python
process or compiler runs during ordinary use.

The parent uses the Ports `machines pick --json` interface. Its TUI uses
stderr and console input while the parent captures stdout. The SSH picker keeps
its own catalog. No cross-catalog machine-ID conversion is inferred.

## Behavior held fixed

- With the picker enabled, the global Terminal default is SSH Sessions, including
  the + button and standard Ctrl+Shift+T. The optional Ctrl+N/Ctrl+T action names
  SSH Sessions explicitly; Ctrl+Alt+N names local PowerShell explicitly.
- Remote/Ports/local-Herdr GUIDs, machine context, return scope and inherited
  Herdr environment guards remain. Custom SSH config/port routes use OpenSSH.
- Remote first, Ports second, optional local Herdr third; the paired launcher
  selects the first tab in its uniquely named window.
- Explorer integration adds **Open PowerShell here** in the classic context menu.
  Windows 11's built-in modern **Open in Terminal** entry remains unchanged.

## Development evidence

Fourteen native parent tests pass on Windows: new-tab behavior, idempotence, preserved
integration-only settings, shortcut collisions, JSONC, backups/concurrent changes,
safe export, argv quoting, JSON argument errors, Explorer plan and tab composition.
Mixed-case profile GUIDs update in place; malformed personal preferences fail
before settings are written. The dispatch regression starts an owned child with a
longer-lived descendant: status-only calls return when the child exits, without
waiting for an unused inherited output pipe. A separate timeout assertion verifies
the bounded wait. A second regression supplies an unrelated inheritable pipe;
status-only dispatch excludes it, so the caller sees EOF while the owned fixture
descendant remains alive. The three status-only call sites use explicit arguments
and a shared Windows handle-list creator, inheriting the developer's environment
and working directory. Interactive machine selection still captures its JSON
output with console input/stderr. Clippy passes with warnings denied.
The [hosted release run](https://github.com/brant92good/terminal-workspace/actions/runs/34388272293)
passes with the recorded leaf source pins and packages the exact released Windows
binaries and helpers. The versioned public HTTPS bootstrap, fresh installation
and update also passed in isolated fixtures on PowerShell 5.1 and 7.
See [verification](verification.md) for the tested archive and unresolved gate.
Native desktop focus and shortcut timings remain separate qualifications.

Three additional actual-ZIP tests pass against a locally built candidate:
fresh install, update, checksum rejection, destination ownership, saved preferences,
paths containing spaces/Unicode/apostrophes, and a real Ports machine-selection JSON
response. Legacy migration also preserves exact preference/current.json bytes,
copies customized shared settings, prefers newer native settings and rejects
redirected or malformed legacy metadata before changing the destination. These
tests were followed by the separate public HTTPS bootstrap checks described above.

Packaged PowerShell wrappers preserve embedded quotes, empty arguments, trailing
backslashes, Chinese text and emoji. Explicit `--json` output reaches PowerShell
assignment and `ConvertFrom-Json`; externally redirected wrapper JSON is UTF-8.
Help/version output is captured too. Other textual commands retain console output;
use the compiled CLI directly when piping those commands. Normal TUI views inherit
the console. A real ConPTY test checks both PowerShell 5.1 and 7, including an
interactive `machines pick --json` call whose UI uses stderr while its result goes
through the PowerShell pipeline. These tests open no desktop windows.

An initial helper build accidentally wrote the checkout's live taskbar executable.
It was immediately rebuilt from the committed legacy launcher source before any
desktop launch. The restored binary contains the legacy Python/workspace.py paths,
not the new native command. Native build output now defaults to
`artifacts/native-build`; using the checkout root as output is rejected. The
standalone launcher builder defaults to `artifacts/native-launcher` and rejects
the live launcher path. Both its default build and refusal were checked while
verifying that the installed launcher's SHA256 stayed unchanged. Packaging uses
a unique artifact directory. Live installation remains a separate gate.

## Release barrier

Build and review leaf releases first. Package their exact Windows binaries and
helpers, recording asset URLs and SHA256 hashes in `release.json`. Create a parent
prerelease, smoke-test that actual HTTPS installer in an isolated destination,
obtain independent code and README review, then promote identical bytes to stable.
Do not update child pins or run the recursive private installer during development.

The Windows-specific parent does not claim to install Terminal hotkeys on other
systems. Standalone leaves supply their own Linux/macOS installation; macOS stays
beta until actual desktop use is qualified.
