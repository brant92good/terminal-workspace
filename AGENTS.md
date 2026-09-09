# Working on Terminal Workspace

This Windows setup pairs remote SSH (optionally Herdr) with Port Forward TUI,
which opens remote services on local ports. The Start/desktop button opens the
remote session first and Ports second, leaving remote selected. This repo can be
installed without anyone's private personal-setup repository. An optional third
tab runs local Herdr independently of the remote machine.

Read README.md. Run `./doctor.ps1 --json` for local checks and
`./ports.ps1 list --json` for connection state. These commands do not start SSH.
For setup use `./install.ps1 -NonInteractive`; no SSH host or Herdr is required.
Machines are added manually or explicitly imported at runtime. Respect prior
authorization; do not invent additional approval steps.

## Where changes belong

- App UI, favorites, CLI, diagnostics and SSH lifecycle: `apps/port-forward-tui`.
  Read its AGENTS.md before changing it. It is a separate pinned repository.
- SSH machine picker, route metadata and explicit catalog sync: `apps/ssh-session-tui`,
  another independent pinned leaf. Read its AGENTS.md. It does not own SSH config
  or key management. The two apps' machine catalogs are currently separate.
- Terminal appearance and shortcuts: `config/terminal.json` (public preferences).
- Machine paths and SSH name: ignored `.machine.json` (local values).
- Installation and settings rendering: `install.ps1`, `scripts/configure.py`.
  `-IntegrationOnly` adds the managed app profiles/shortcuts while preserving
  appearance, default shell and menu. The mode is local to `.machine.json`
  and reused on updates. `-ApplySharedSettings` explicitly opts into the full
  preferences. Keep older installations' default behavior.
  Explicit `-SessionPicker` changes the default profile even in integration-only
  mode and adds Ctrl+Alt+N for local PowerShell. The catalog path stays local.
  `-NewTabShortcut ctrl+n` (or ctrl+t/none) is an optional local preference; the
  public installer does not claim either key by default.
- Herdr tab identity and return behavior: `scripts/herdr_launcher.py` and the
  port app's shared focus helper. Never use duplicate titles as Herdr identity.
- `scripts/workspace.py` selects a machine before creating companion tabs;
  the legacy-named `herdr_launcher.py` supports SSH, remote Herdr and local Herdr.
  `remote_client` and `local_herdr` in ignored `.machine.json` are installation choices.

Preserve settings backups, unrelated profiles, both shortcut scopes, and the
guard against stealing focus from another application. Document intended menu
changes. Do not export shell commands or machine paths into public preferences.
Herdr artwork retains its attribution in NOTICE.

## Verification and publishing

Run `.\apps\port-forward-tui\.venv\Scripts\python.exe -E -s -m unittest discover -s tests -v`.
Opt-in `scripts/check_interactive.py --yes` moves real windows and uses SSH;
`scripts/check_terminal_persistence.py --yes` opens an isolated real tunnel.
Run them only within the user's authorized desktop-testing scope and preserve
their sessions. Ordinary docs changes do not require disruptive desktop tests.
`scripts/check_session_picker.py --yes` checks the real picker/SSH/local-shell
handoff in one small owned window with foreground guards. Its marker commands
require an authorized, working server; it preserves existing windows and tabs.

Publish app changes first; then update the app submodule pin and publish this
repository. A private parent can pin this resulting commit. Sync should follow
recorded child commits, not automatically advance every child to its main branch.
Screenshots use demonstration data; see README captions for what is simulated.
Setup details and supported claims live in docs/setup.md and
docs/verification.md. Keep README claims tied to those recorded checks.

`bootstrap.ps1` is the public one-command entry point. It downloads source
archives at the workspace's exact child pins and manages its own Python under
an installer-owned directory. Git checkouts/private parents keep their existing
install.ps1 flow. `-NoConfigure` prepares code/runtime/helpers without desktop
changes; the network-enabled scripts/check_bootstrap.py uses it in isolation.
Do not run a second configured bundle on the owner's desktop as a smoke test.
