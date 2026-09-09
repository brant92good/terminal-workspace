# Platform support and portability plan

The shipped workspace supports Windows. The standalone SSH picker has macOS/Linux
**beta** support. Port Forward TUI and the workspace integration still need porting;
installing a different terminal emulator alone does not make the whole stack portable.

macOS includes [Terminal, with tabs and profiles](https://support.apple.com/guide/terminal/trmlb20c7888/mac).
[iTerm2](https://iterm2.com/documentation-one-page.html) adds split panes and
global, session and profile hotkeys. Either can host a compatible terminal app.
These features make a macOS integration plausible, but do not establish that our
existing window-return code works there.

## Current evidence

| Component | Windows | Linux and macOS |
| --- | --- | --- |
| SSH Sessions leaf | Installed and tested; CI on Python 3.12/3.13 | **Beta.** Version 0.5 passes one-command install/update and local-shell checks in Ubuntu/macOS 14 CI. Live remote login in Linux/macOS terminal apps remains unqualified. See the leaf's verification record. |
| Port Forward TUI leaf | Installed and tested; CI on Python 3.12–3.14 | Not supported. Windows process ownership, detached controllers, TCP ownership checks and view tracking need replacements. |
| Terminal Workspace, layer two | Installs Windows Terminal profiles, launchers and hotkeys | No installer or terminal adapter yet. Windows `settings.json` is not a cross-platform settings format. |
| Private settings, layer three | Pins the public workspace and records owner preferences | Machine metadata can be shared; paths, terminal preferences and OS-specific setup need device overrides. |

This assessment is from the source and Windows checks on September 9, 2026.
The local Windows/WSL suites passed 83 discovered tests with the appropriate
platform skips. The SSH picker now labels the actual local shell and uses
`$SHELL` or `/bin/sh` on Unix. The whole workspace remains Windows-specific.

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

1. **Finish SSH desktop qualification on Linux and macOS.** Version 0.5 covers
   packaged installation, import/locks, Unicode paths and local-shell terminal
   handoff, Ctrl+C, resize and return. Test real remote login in chosen terminal
   applications separately. Keep ordinary picker use independent of global hotkeys.
2. **Evaluate an existing forwarding engine before porting ours.** The
   [alternatives survey](alternatives.md) identifies Portato as a close match.
   If retaining our controller, isolate Windows jobs, locks, socket ownership
   probes and detached-process creation behind OS implementations. Verify that
   closing a tab leaves requested forwards running, reconnect works after a
   network outage, stop cancels retries, and unrelated processes are untouched.
   Define logout/reboot behavior separately from closing a terminal window.
3. **Add terminal integrations.** Retain Windows Terminal; evaluate WezTerm's
   direct tab-ID API before extending desktop automation, with iTerm2 as another
   macOS candidate. Share
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
