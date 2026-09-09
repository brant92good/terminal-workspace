# Does a Rust launcher make tab switching faster?

**Yes, in this experiment: about 78 ms, or 22%, off the median return time.**
This measures returning to an already open tab. It does not measure opening
the TUI, connecting to SSH, or rewriting the whole application in Rust.
The Rust implementation measured here was an experiment, not the installed
default at the time. This report predates the full native 0.7.0 candidate. That
candidate has separate [implementation checks](native-migration.md); its actual
shortcut latency has not been measured by these experiments.

## Results

Measured September 9, 2026, with tracing disabled. Each cell contains 12 real
keypresses. The then-installed Python launcher and two experimental launchers all
used the same installed C# focus helper.

| Return to an existing tab | Installed Python, median (range) ms | Thin Python control, median (range) ms | Rust experiment, median (range) ms |
| --- | ---: | ---: | ---: |
| Remote Herdr | 350.3 (347.3–370.1) | 331.3 (314.8–335.9) | 271.6 (267.9–288.9) |
| Ports | 349.7 (329.1–395.5) | 320.0 (313.4–334.0) | 272.4 (254.8–281.9) |

Rust reduced the installed-launcher median by **78.7 ms / 22.5%** for Herdr
and **77.3 ms / 22.1%** for Ports. All 72 measured returns reached the intended
tab with keyboard focus in its terminal content.

The thin Python control matters: it receives a preselected machine's view
directory, just like Rust. It avoids unrelated launcher imports and argument
routing. Rust's advantage over that control is **59.7 ms** for Herdr and
**47.6 ms** for Ports. The full installed-to-Rust difference therefore mixes
language/runtime costs with the smaller experimental interface.

Raw samples and block order: [Herdr](benchmarks/language-herdr.json),
[Ports](benchmarks/language-ports.json). These are fresh matched comparisons;
do not subtract them from the older, differently configured batches in the
[earlier stage report](before-after.md).

## What the experiment changes

Both experimental launchers accept one JSON plan: record directory, settings
directory, record format and native-helper path. Each invocation reads the
current scope and live records; it does not cache a chosen tab or leave a
background service running. Ports uses its saved titles. Herdr passes identity
records to the existing helper, which validates the owner PID and process start
time before matching the accessibility runtime identity.

The launch sequence remains:

1. Terminal opens a temporary shortcut tab and starts the launcher.
2. The launcher reads live views and starts the existing native focus helper.
3. The helper finds a candidate and signals the launcher to exit.
4. The helper waits for the temporary tab to disappear, checks foreground
   ownership again, then selects the destination and focuses its content.

Only the launcher is replaced. The experimental interface does **not** include
the machine picker, automatic multi-machine context selection or opening a
new view when none exists. At experiment time, normal installations used Python
and needed no Rust toolchain. This was evidence for a possible native return
path, not qualification of a feature-complete replacement.

## Process and import microbenchmarks

These separate headless measurements include process creation through exit,
with captured output. Each case has 40 warm runs in shuffled order.

| Operation | Median ms |
| --- | ---: |
| Start Python and exit | 29.6 |
| Start Rust executable and exit | 12.8 |
| Python control: read scope and eight live records | 66.1 |
| Rust: read scope and eight live records | 13.3 |
| Python: import the focus module | 63.5 |
| Python: import the all-machines TUI module | 264.7 |

[Raw microbenchmarks](benchmarks/language-headless.json). Each row is a separate
process-level measurement, not a component to add to the desktop total.
The TUI import row stops before creating the UI; it is **not first-frame latency**.
The roughly fivefold record-preparation ratio is not a fivefold app speedup.

Python does have interpreter startup and module-import costs, and CPython
normally executes Python bytecode. But this app also delegates SSH to OpenSSH,
focus changes to a compiled helper, and much UI work to libraries. Changing the
language cannot remove Terminal's tab lifecycle or make an SSH network faster.
[Python's bytecode definition](https://docs.python.org/3/glossary.html#term-bytecode)
describes the execution model; the measured numbers above establish its cost
for this particular task.

Rust's ownership rules prevent many memory errors without a garbage collector.
Python already manages memory for ordinary application code; a rewrite would
not magically fix focus races or stale state. The Rust prototype still needs
small `unsafe` Win32 calls. They have documented preconditions and owned handle
cleanup, but those boundaries need review like any other native interface.
See the Rust Book on [ownership](https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html)
and [unsafe Rust](https://doc.rust-lang.org/book/ch20-01-unsafe-rust.html).

## What may be worth optimizing

| Candidate | Evidence and remaining uncertainty |
| --- | --- |
| Native or thinner return launcher | The matched experiment saved about 78 ms versus installed Python; simplifying Python alone saved 19–30 ms. A production implementation needed separate machine-selection, fallback and packaging qualification. |
| Combine multi-machine context lookup with focus lookup | The earlier instrumented two-machine Herdr batch spent 183 ms mean selecting the invoking window's machine. That extra helper could matter more than changing language. This experiment deliberately used one machine and does not measure the improvement. |
| Native-helper startup and accessibility queries | They remain in the roughly 272 ms Rust result. Earlier stage timings identify runtime startup and discovery costs, but there is no new Rust-versus-Python stage decomposition here. Caching must retain identity and foreground checks. |
| Avoid the temporary shortcut tab | Could remove creation/disposal costs, but requires a different launch mechanism. Deleting the close wait can select the wrong tab. |
| Fresh TUI startup | The 265 ms import measurement warranted profiling first-frame startup and deferring optional imports. No complete Rust TUI was built or timed in this experiment. |
| Tiny JSON reads | Their raw data is small. File-format changes are unlikely to be the first useful optimization. |

At that point, the next proposed step was a native return path behind the
existing UI, with feature parity and fallback tests. A full Rust TUI/controller
rewrite needed separate favorites, multi-server, IPC, persistent-tunnel,
reconnection and installation work. These measurements alone did not qualify it.

## Method and checks

The desktop is Windows 11 Pro build 26200, Intel Core i5-13600K, Windows Terminal
1.24.11911.0, PowerShell 7.6.5, Python 3.12.11 based on Miniforge, and Rust
1.94.0. There were two Terminal windows and five tabs during each final batch.

Each batch used an isolated temporary machine catalog and view records, one
small test window sized to 700×400 pixels, and window-only focus scope. The
real Ports TUI and remote Herdr occupied that window. Existing favorites and
tunnels were not changed. Three temporary Ctrl+Alt+F9/F10/F11 bindings were
installed once before the batch and removed afterward; normal shortcuts were
left in place. All six orders of the three variants were shuffled with seed
923, with two keypresses per variant in each block.

The target tab precedes the source, so closing the launcher cannot pass by
merely selecting its adjacent tab. A cached accessibility selection handle is
polled about every 5 ms until the expected window is foreground, the intended
tab is selected and terminal text has keyboard focus. Setup, compilation and
priming waits are outside the stopwatch. Native tracing is off.

The driver checks foreground ownership before priming, before sending keys
and during measurement. If another application takes focus, it stops rather
than reactivating Terminal. The published harness additionally identifies its
window by a unique held bootstrap title before running apps that rename tabs.
That ownership-hardening change was checked separately after the timing batches;
it does not alter the timed return path. Diagnostics no longer activate tabs.

A separate test deliberately delayed helper startup, moved focus to a
**440×140 mini application**, and resumed the real helper. Python and Rust each
passed both Ports-title and Herdr-record cases: the mini app retained focus,
the target remained unselected, and the helper reported cancellation.
[Recorded checks](benchmarks/language-cancellation.json). These synthetic views
test foreground cancellation without opening SSH or touching a user's live tabs.

Eight shared preparation checks cover empty records, live Unicode titles,
malformed/unrelated records, scope handling, Herdr records and dead-PID pruning.
They are a bounded contract check, not proof of compatibility for every possible
corrupt file. Rust formatting and warning-free Clippy checks passed.

Earlier exploratory Herdr trials failed when a new view exited with
`nested herdr is disabled by default`. The caller was itself inside Herdr;
Terminal inherited its pane/session environment. The registered test view then
disappeared. Those failed batches are not included in the timing table.

The launcher fix made during the experiment removed inherited Herdr runtime identity variables
**only after verifying a separate Terminal tab registration**. It preserves
PATH, Conda settings, SSH agent settings and Herdr configuration. It does not
enable global nested sessions. Twenty-six Terminal tests passed, including
environment preservation and case-insensitive variable names. Herdr has an
[upstream report of the same inherited-environment guard problem](https://github.com/herdrdev/herdr/issues/2135).

## Variation between computers

CPU speed, laptop power saving, competing work, executable scanning, storage
and warm/cold caches can change process startup. Terminal/.NET versions,
accessibility providers, display scaling and the number of windows/tabs can
change focus lookup. None of those causes was isolated in this experiment.

The measured shortcuts invoked an absolute private Python executable with `-E -s`;
they did not activate Conda or run a PowerShell profile. Python distribution and
base-runtime availability could still matter. The Herdr environment leak above
also shows why ignoring Python variables alone is insufficient. SSH/VPN/server
latency affects new connections and reconnection, not returning to an already
open local tab. No cold-start bound, cross-machine distribution, cross-window
latency or physical-laptop result is claimed.

## Code structure guidance

This work used Matt Pocock's
[codebase-design skill](https://github.com/mattpocock/skills/blob/main/skills/engineering/codebase-design/SKILL.md):
keep interfaces small, hide lifecycle complexity behind them, and test observable
results. Both languages implement the same preparation contract; the existing
focus helper remains responsible for tab identity and handoff. Test helpers own
and clean up their windows and temporary settings. Unused settings-rewrite code
was removed, and shortcut restoration uses a context manager.

Two future refactoring candidates are the duplicated view-record readers and
the UI's direct access to multi-machine manager internals. They would benefit
from a shared request/snapshot interface when those areas change. No broad
architecture rewrite or claim that a skill guarantees clean code is made here.

Source and reproduction: [launcher experiment](../experiments/launcher-rust/README.md).
