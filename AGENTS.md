# Working on Terminal Workspace

This is the Windows setup around two apps: Herdr is the remote terminal, and
Port Forward TUI opens remote services on local ports. The Start/desktop button
opens Herdr first and Ports second, leaving Herdr selected. This repo can be
installed without anyone's private personal-setup repository.

Read README.md. Run `./doctor.ps1 --json` for local checks and
`./ports.ps1 list --json` for connection state. These commands do not start SSH.
For setup use `./install.ps1 -SshHost EXISTING_ALIAS -NonInteractive` with an
actual SSH name supplied by the user or existing configuration. Respect prior
authorization; do not invent additional approval steps.

## Where changes belong

- App UI, favorites, CLI, diagnostics and SSH lifecycle: `apps/port-forward-tui`.
  Read its AGENTS.md before changing it. It is a separate pinned repository.
- Terminal appearance and shortcuts: `config/terminal.json` (public preferences).
- Machine paths and SSH name: ignored `.machine.json` (local values).
- Installation and settings rendering: `install.ps1`, `scripts/configure.py`.
- Herdr tab identity and return behavior: `scripts/herdr_launcher.py` and the
  port app's shared focus helper. Never use duplicate titles as Herdr identity.

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

Publish app changes first; then update the app submodule pin and publish this
repository. A private parent can pin this resulting commit. Sync should follow
recorded child commits, not automatically advance every child to its main branch.
Screenshots use demonstration data; see README captions for what is simulated.
