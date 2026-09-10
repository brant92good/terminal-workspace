# Platform support

Terminal Workspace is the Windows integration around three independent Rust apps.
Installing a leaf does not require Windows Terminal or this repository.

| Component | Windows | Linux | macOS |
| --- | --- | --- | --- |
| [SSH Sessions](https://github.com/brant92good/ssh-session-tui) | Compiled x64 app | Compiled x64/ARM64 app | Compiled Intel/Apple Silicon app; **beta** |
| [Ports](https://github.com/brant92good/port-forward-tui) | Compiled x64 app and focus helpers | Compiled x64/ARM64 app | Compiled Intel/Apple Silicon app; **beta** |
| [SSH Files](https://github.com/brant92good/ssh-files) | Compiled x64 app; **beta** | Compiled x64/ARM64 app; **beta** | Compiled Intel/Apple Silicon app; **beta** |
| Terminal Workspace | Windows Terminal profiles, shortcuts and paired tabs | No terminal adapter | No terminal adapter |

The native releases are tracked in [migration status](native-migration.md).
Consult each leaf's release and verification page for the actual artifact and
platform checks; a compiled binary alone does not establish desktop/network use.

macOS Terminal and iTerm2 can host the standalone TUIs. They do not gain this
project's Windows return-to-tab shortcuts or taskbar behavior. Linux terminal
emulators have the same boundary. A future adapter can implement those actions
without tying the leaf apps to a particular terminal.

## Which layer owns what?

- The **leaf apps** own their TUI keys, machine catalogs, favorites and connection
  behavior. Ports includes the shared Windows focus adapter used by this parent.
  Files receives one selected route from SSH Sessions and owns no machine catalog.
- **Terminal Workspace** owns terminal profiles, ordinary new-tab behavior,
  companion tabs, R/P/L return shortcuts and optional Explorer integration.
- An **optional private parent** stores personal choices and pins this public
  repository. Shared machine metadata can travel between devices; routes,
  executable paths and terminal-specific choices remain device-specific.

macOS remains beta until real terminal sessions, remote login and laptop/network
recovery have been qualified beyond hosted tests. No macOS or Linux desktop
integration is installed by the Windows bootstrap.
