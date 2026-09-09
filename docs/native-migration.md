# Native integration candidate

The `native-integration` branch prepares Terminal Workspace 0.7.0. It is not a
stable release or a completed upgrade of the owner's installation yet.

## Production paths

`terminal-workspace.exe` owns settings rendering/export, diagnostics, paired tab
composition and remote/local Herdr or SSH launch. Profiles call the installed
`ssh-sessions.exe` and `ports.exe` directly. Taskbar identity and accessibility
helpers remain compiled C# programs using the Windows .NET Framework; no Python
process or compiler runs during ordinary use.

The parent uses the Ports 0.7.0 `machines pick --json` interface. Its TUI uses
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

Twelve native parent tests pass on Windows: new-tab behavior, idempotence, preserved
integration-only settings, shortcut collisions, JSONC, backups/concurrent changes,
safe export, argv quoting, JSON argument errors, Explorer plan and tab composition.
Mixed-case profile GUIDs update in place; malformed personal preferences fail
before settings are written.
Clippy passes with warnings denied.
The precompiled taskbar/tracker/focus helpers build without Python. Real release
download/install and native desktop qualification remain release gates.

Two additional actual-ZIP installer tests pass against a locally built candidate:
fresh install, update, checksum rejection, destination ownership, saved preferences,
paths containing spaces/Unicode/apostrophes, and a real Ports machine-selection JSON
response. Legacy migration also preserves exact preference/current.json bytes,
copies customized shared settings, prefers newer native settings and rejects
redirected or malformed legacy metadata before changing the destination. These
tests do not qualify the future release download URLs.

An initial helper build accidentally wrote the checkout's live taskbar executable.
It was immediately rebuilt from the committed legacy launcher source before any
desktop launch. The restored binary contains the legacy Python/workspace.py paths,
not the new native command. Native build output now defaults to
`artifacts/native-build`; using the checkout root as output is rejected. Packaging
uses a unique artifact directory. Live installation remains a separate gate.

## Release barrier

Build and review leaf releases first. Package their exact Windows binaries and
helpers, recording asset URLs and SHA256 hashes in `release.json`. Create a parent
prerelease, smoke-test that actual HTTPS installer in an isolated destination,
obtain independent code and README review, then promote identical bytes to stable.
Do not update child pins or run the recursive private installer during development.

The Windows-specific parent does not claim to install Terminal hotkeys on other
systems. Standalone leaves supply their own Linux/macOS installation; macOS stays
beta until actual desktop use is qualified.
