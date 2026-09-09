# SSH Sessions integration

SSH Sessions is an independent public leaf at `apps/ssh-session-tui`. It owns
the keyboard machine list, named address/port routes, device-only route choices
and explicit Git sync of the catalog. Terminal Workspace owns the profile,
default-tab choice and local-shell shortcut.

Run `install.ps1 -IntegrationOnly -SessionPicker` to make normal new tabs open
the picker while keeping the existing Terminal appearance and menu. This explicit
option changes the default even in integration-only mode. Ctrl+Alt+N opens a
normal local PowerShell tab. `-SessionCatalog C:\PrivateSetup\connections\catalog.json`
selects a metadata file; the absolute path is saved only in ignored `.machine.json`.
Without that option, the app uses local app data and starts with an empty list.

Later installs reuse the saved picker choice and catalog. Integration-only
updates preserve a default the user subsequently selected in Terminal settings;
passing `-SessionPicker` explicitly selects the picker again. Shared-settings
mode restores the saved default. `-NoSessionPicker` disables its profile and
local-shell shortcut and restores PowerShell as the default. The installer
backs up settings before writing.
`-NewTabShortcut ctrl+n` optionally adds a simpler new-tab key; `ctrl+t` is also
available and `none` removes it. The default public install claims neither key.
This binding opens the default profile directly, without a temporary launcher
tab. It stays local in `.machine.json`; a private parent can record the preference.
Terminal consumes that key before terminal programs see it. Ctrl+Alt+N continues
to open local PowerShell, and Ctrl+L inside the picker opens its internal shell.

The picker now supports I for explicit read-only SSH import. See the
[import guide](../apps/ssh-session-tui/docs/ssh-import.md). Writing SSH configuration
and designing agent session policy remain deferred.
If integration-only setup has no PowerShell profile, enabling the picker adds
a direct `pwsh.exe` profile for the local shortcut. This also works when the
automatic PowerShell profile source is disabled; existing profiles are preserved.

Press G to browse nested groups, Space to select machines, M to move them and T
to edit their tags. Search accepts names, addresses, groups and tags. Numbered
favorites work across groups. Group/tag metadata syncs with the catalog and
requires SSH Sessions 0.4+ on each device.

The existing workspace button and R/P/L shortcuts remain independent. The two
leaf apps currently use separate machine catalogs. Existing local SSH
configuration is used by the normal SSH client. See the leaf's [README](../apps/ssh-session-tui/README.md)
and [backlog](../apps/ssh-session-tui/docs/backlog.md).

For macOS/Linux support and where platform-specific shortcuts belong, see
[Platform support](platforms.md).

## Verification on September 9, 2026

On Windows 11 with Windows Terminal 1.24, PowerShell 7.6 and Python 3.12,
`scripts/check_session_picker.py --yes` opened one small test-owned window:

1. Ctrl+Shift+T opened the configured default picker.
2. Enter connected to the configured server through its existing SSH client.
3. A harmless remote `printf` produced a marker not present literally in the
   typed command, proving execution rather than just matching input echo.
4. `exit` returned to the picker.
5. Ctrl+Alt+N opened a separate PowerShell Core tab and executed a local marker.
6. Cleanup closed only that test window and verified the original tab identities
   were unchanged. Each keyboard action checked test-window foreground ownership.

The test passed. This is one actual desktop and route, not a cross-device or
all-network guarantee. No existing user window was activated by the test.
Headless app tests additionally cover route choice, temporary fallback,
catalog conflicts, form validation and sync through two isolated local Git clones.
See [leaf verification](../apps/ssh-session-tui/docs/verification.md).

The follow-up `--new-tab-key ctrl+n` check passed the same real SSH/local-shell
flow after the optional key was installed. Existing tab identities remained
unchanged. The extra binding opens the default profile through Terminal's native
newTab action. Import's read-only parser and keyboard selection have their own
tests in the leaf, including a static comparison with real OpenSSH.
