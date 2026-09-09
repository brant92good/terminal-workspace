# Platform support and portability plan

The shipped workspace supports Windows. macOS and Linux support is future work;
installing a different terminal emulator alone does not make the whole stack portable.

macOS includes [Terminal, with tabs and profiles](https://support.apple.com/guide/terminal/trmlb20c7888/mac).
[iTerm2](https://iterm2.com/documentation-one-page.html) adds split panes and
global, session and profile hotkeys. Either can host a compatible terminal app.
These features make a macOS integration plausible, but do not establish that our
existing window-return code works there.

## Current evidence

| Component | Windows | Linux and macOS |
| --- | --- | --- |
| SSH Sessions leaf | Installed and tested; CI on Python 3.12/3.13 | Python/Textual code has Unix file locking, SSH and local-shell paths. No platform CI or real terminal handoff verification yet. Experimental only. |
| Port Forward TUI leaf | Installed and tested; CI on Python 3.12–3.14 | Not supported. Windows process ownership, detached controllers, TCP ownership checks and view tracking need replacements. |
| Terminal Workspace, layer two | Installs Windows Terminal profiles, launchers and hotkeys | No installer or terminal adapter yet. Windows `settings.json` is not a cross-platform settings format. |
| Private settings, layer three | Pins the public workspace and records owner preferences | Machine metadata can be shared; paths, terminal preferences and OS-specific setup need device overrides. |

This assessment is from the source and Windows checks on September 9, 2026.
Portable-looking code is not a Linux/macOS test result. The SSH picker still
labels its local shell PowerShell in the UI even though its Unix command path
can fall back to `$SHELL` or `/bin/sh`.

## Which layer owns shortcuts?

Keys inside an app, such as G for groups and number-then-Enter favorites, belong
to that leaf. System hotkeys, new-tab defaults, companion tabs and returning to
an existing window belong to the terminal integration in layer two. The private
layer selects the owner's preferred bindings.

Some implementation predates this separation: Port Forward TUI currently owns
`views.py`, `launch.py` and `native/FocusHelper.cs`; Terminal Workspace reuses
that Windows focus helper for remote/local launchers. A portability change
should give this shared integration an explicit platform interface, preserving
standalone Ports installation. It should not duplicate a second focus engine
inside the SSH picker.

## Future work, in order

1. **Qualify the SSH leaf on Linux and macOS.** Add CI, test a packaged install,
   normal and custom SSH configs, Unicode paths and file locks. Verify a real
   terminal handoff, Ctrl+C, resize, logout back to the picker and the correct
   local shell. Add platform-specific installation instructions only after this
   works. Keep ordinary picker use independent of global hotkeys.
2. **Port the forwarding engine.** Isolate Windows jobs, locks, socket ownership
   probes and detached-process creation behind OS implementations. Verify that
   closing a tab leaves requested forwards running, reconnect works after a
   network outage, stop cancels retries, and unrelated processes are untouched.
   Define logout/reboot behavior separately from closing a terminal window.
3. **Add terminal integrations.** Retain Windows Terminal; evaluate iTerm2 on
   macOS and a specific Linux terminal after choosing supported targets. Share
   the intent (open app, create tab, return to session), with terminal-specific
   implementations. Account for Linux desktop/Wayland differences. Report an
   unavailable return-to-tab feature without preventing basic app startup.
4. **Extend private setup by OS.** Share machine IDs, groups, tags and routes;
   apply the correct device's route, shell and key bindings. Keep Windows
   settings out of macOS/Linux configuration files. Continue pinning tested
   public releases through the same three-layer repository tree.

No Linux/macOS port or new global shortcut is installed by this documentation
update. SSH configuration ownership and agent session policy remain a separate
[design discussion](../apps/ssh-session-tui/docs/backlog.md).
