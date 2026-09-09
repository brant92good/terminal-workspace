# Existing tools and what this workspace adds

Surveyed September 9, 2026 using project documentation and selected source.
No alternative was installed or benchmarked in this survey. This is a feature
comparison, not a reliability ranking or a claim to have searched every project.

SSH pickers, tunnel managers and private dotfile deployment already exist as
substantial open-source projects. We found no verified drop-in for this entire
workspace: device-specific named routes with deliberate fallback, fixed favorite
slots, local shells, persistent shared port forwards, and machine-aware return
shortcuts in Windows Terminal. Small key-binding differences alone do not justify
rebuilding a whole manager.

| Project | Existing overlap | Concrete difference to evaluate |
| --- | --- | --- |
| [SSHM](https://github.com/Sn0wAlice/sshm) | Rust SSH TUI, nested folders, tags, favorites, numeric quick-connect, background tunnels, static SSH import and Git configuration sync | Numbers open the Nth visible host rather than a fixed favorite slot. One endpoint per host; no per-device named-route selection. Native TUI releases cover Linux/macOS; Windows TUI behavior was not qualified. |
| [SSHub](https://github.com/Petyok/SSHub) | Rust TUI with nested groups, favorites, local-shell tabs and persistent tunnels | Import resolves hosts with `ssh -G`; discovery may evaluate executable SSH config conditions. Profiles are separate inventories, not routes of one machine. Cross-device Git sync was found as a design, not verified shipped behavior. |
| [sshelf](https://github.com/max-rh/sshelf) | SSH picker, groups/sites/tags, static import, shareable host file and persistent forwards | No Windows distribution or reconnecting tunnel supervisor. Default connection replaces the picker with SSH; tmux mode can keep a separate picker. |
| [Portato](https://github.com/portuber/portato) | Keyboard tunnel manager, shared background daemon, multiple clients, saved forwards, reconnect and Windows/macOS/Linux binaries | New-forward form asks for separate endpoints. Partial OpenSSH configuration support; no corresponding remote-tab policy or our route catalog. |
| [sshroute](https://github.com/thereisnotime/sshroute) | One logical host with LAN/VPN/public routes in versionable configuration | Connection chooses by detected network; optional fallback tries alternatives automatically. Explicit `resolve --network` exists, but not a per-device selection/fallback-confirmation TUI. |

## Source details that affect adoption

SSHM's [host model](https://github.com/Sn0wAlice/sshm/blob/main/crates/sshm-core/src/models.rs)
contains one endpoint plus identity-file paths, commands and usage metadata.
Its [sync engine](https://github.com/Sn0wAlice/sshm/blob/main/crates/sshm-core/src/sync/engine.rs)
syncs that host file. This is broader than SSH Sessions' metadata allowlist,
even though it does not mean private-key contents are synchronized.

SSHub's [resolver](https://github.com/Petyok/SSHub/blob/main/src/ssh/resolver.rs)
runs `ssh -F ... -G ...`. Our importer instead reads supported static directives
without invoking SSH. Its [host-sync design](https://github.com/Petyok/SSHub/blob/main/docs/host-sync-design.md)
should not be counted as a released cross-device sync feature.

Portato's [daemon tests](https://github.com/portuber/portato/blob/main/internal/daemon/server_test.go)
cover updates reaching multiple clients. Its [tunnel loop](https://github.com/portuber/portato/blob/main/internal/forward/tuber.go)
and [backoff](https://github.com/portuber/portato/blob/main/internal/forward/backoff.go)
implement reconnection. This is the same core architecture as a persistent
multi-view port manager, not merely a similar-looking list.
Its [SSH-config support](https://github.com/portuber/portato/blob/main/docs/phases/phase-44-ssh-config.md)
covers selected directives; the reviewed dial path did not implement
ProxyCommand. That matters for [Cloudflare Access with client-side cloudflared](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/use-cases/ssh/ssh-cloudflared-authentication/).
A Tailscale IP working does not establish compatibility with that route.

sshroute's [resolver](https://github.com/thereisnotime/sshroute/blob/main/cmd/resolve.go)
is an integration candidate, but its [connect fallback](https://github.com/thereisnotime/sshroute/blob/main/cmd/connect.go)
uses exit 255 to try subsequent profiles. OpenSSH defines 255 for errors
generally, not only network failures ([manual](https://man.openbsd.org/ssh.1#EXIT_STATUS)).
Our fallback requires a fresh user choice instead.

## A smaller amount of custom code

Keep the three logical layers, but make their implementations replaceable:

1. **Connection tools:** retain explicit device route selection and delegate
   authentication/session behavior to OpenSSH. Trial Portato against direct IP,
   ProxyJump, Cloudflare, close-all-views and network recovery before deciding
   whether an adapter or contribution costs less than maintaining our controller.
2. **Terminal integration:** consider a WezTerm adapter. It has
   [activation by tab ID](https://wezterm.org/cli/cli/activate-tab.html),
   [client focus information](https://wezterm.org/cli/cli/list-clients.html), and
   [workspace layouts](https://wezterm.org/recipes/workspaces.html).
   This could reduce desktop automation. Host matching and same-window/all-window
   last-used policy still need code, and adopting it changes the terminal app.
3. **Private configuration:** evaluate chezmoi's
   [per-machine templates](https://www.chezmoi.io/user-guide/manage-machine-to-machine-differences/)
   and [external repositories/archives](https://www.chezmoi.io/user-guide/include-files-from-elsewhere/).
   The existing private repository can remain the source; no hosted credential
   sync is required. Configuration deployment does not replace interactive routing.

The recommendation is a bounded compatibility trial before expanding into
generic Termius features or rewriting the tunnel engine in another language.
The practical value to aim for is a coherent installation and connection workflow
across personal devices. The survey did not establish that migrating immediately
would be cheaper or safer than keeping the current working apps.
