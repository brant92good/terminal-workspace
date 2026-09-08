# Shortcut latency: before, after, and remaining costs

Measured on September 8, 2026. Returning to an existing Herdr tab fell from
**1,292.1 ms to 363.4 ms median**, a **71.9% reduction**, on this desktop.
These are real keyboard-to-content-focus measurements. They do not measure
opening a fresh TUI, establishing SSH, or switching across windows.

## End-to-end results

Each Herdr batch contains six actual Ctrl+Alt+H presses, with tracing disabled
for these headline results. All samples are retained, including the slow first
sample after the change.

| Herdr return | Median ms | Minimum ms | Maximum ms |
| --- | ---: | ---: | ---: |
| Before: PowerShell handoff | 1292.1 | 1276.5 | 1298.0 |
| After: shared native helper | 363.4 | 359.7 | 421.2 |

Before samples: `1291.4, 1292.9, 1276.5, 1298.0, 1283.9, 1293.8` ms.
After samples: `421.2, 362.1, 371.5, 359.7, 364.8, 361.1` ms.
Raw data: [before](benchmarks/herdr-switch-before.json), [after](benchmarks/herdr-switch-after.json).

Ports previously measured **1,360.1 -> 369.6 ms median** in its six-sample
optimization comparison ([before](benchmarks/ports-switch-before.json),
[after](benchmarks/ports-switch-after.json)). A subsequent three-sample check with the helper now
shared by both apps measured **365.3 ms median**; see
[shared-helper check](benchmarks/ports-shared-helper-check.json). The detailed stage
comparison below is for Herdr only.

## Current version: cost of multiple-machine routing

After adding machine selection and R/P/L shortcuts, another six-keypress batch
per condition measured the current launcher. These results supersede the older
numbers for describing today's installed behavior; the old/new optimization
comparison above remains a record of that earlier change.

| Current return path | One saved machine: median (range), ms | Two saved machines: median (range), ms | Median difference, ms |
| --- | ---: | ---: | ---: |
| Ports, normal shortcut | 404.8 (395.6–427.4) | 571.6 (566.9–598.9) | +166.8 |
| Remote Herdr, tracing enabled | 410.6 (406.3–415.9) | 606.2 (582.5–627.0) | +195.6 |

Raw samples: [Ports, one](benchmarks/ports-1-machine.json),
[Ports, two](benchmarks/ports-2-machine.json),
[Herdr, one](benchmarks/herdr-1-machine.json),
[Herdr, two](benchmarks/herdr-2-machine.json). Herdr files also retain all
17 stage distributions; the stage means add to their batch's mean total.
The Ports batches have no stage tracing.

With one machine, choosing it took **0.47 ms mean** in Herdr. With two, choosing
the invoking window's machine took **182.96 ms mean**. The latter starts an
extra native helper and reads accessibility/window records before the usual
return helper starts. This is the clearest additional cost. Consolidating that
lookup into the existing helper might remove a process startup and duplicate
window discovery, but would need fresh routing and focus-stealing tests. It
has not been implemented, and its possible savings are not measured.

Other current two-machine Herdr means: Terminal/Python startup and imports
144.48 ms, return-helper startup and initialization 90.52 ms, initial tab
enumeration 80.27 ms, and waiting for launcher-tab closure 60.92 ms. Those remain
possible optimization targets, subject to the compatibility tradeoffs below.

Conditions: the same desktop and interpreter described below; both views in
one temporary window; the actual installed Ctrl+Alt+R/P return commands; six
samples per condition, one-machine batches followed by two-machine batches.
Initial views explicitly select the same primary machine. The second saved
profile stays dormant: no second server, tunnel or view is opened. It activates
the multi-machine context path while keeping the visible tab count comparable.
The temporary profile is removed afterward and original favorites are verified
unchanged. This sequential comparison includes ordinary desktop variation; it
does not establish a cross-machine distribution or isolate tracing overhead.

To select the initial target on an installation with several machines, append
`--machine ID_OR_NAME` to either reproduction command below. The benchmark
leaves the actual return shortcut's machine detection enabled.

## What changed in the original optimization

The old sequence was: create a temporary Terminal tab, start Python, start a
PowerShell probe, load libraries and compile its C# helper, find the saved tab,
start a second PowerShell process, load and compile again, wait for launcher
exit, sleep for 300 ms, discover the destination again, then focus its content.

The new sequence creates the same temporary tab and Python launcher, starts
one prebuilt helper, finds the destination, signals Python to exit, waits for
actual tab disappearance, then focuses the destination. The same helper stays
alive through the handoff. No resident keyboard hook or additional focus service
is installed. Ports also bypasses the Textual import when returning to a view.

Herdr matches registered accessibility runtime identities and validates the
owner PID plus process start time. Duplicate or changing titles do not decide
its target. Both focus scopes and the guard against stealing focus from another
application remain. The PowerShell fallback still has its old delay if the
native helper is unavailable. New-view registration also still uses PowerShell.

## Before-and-after stage profile

A separate instrumented comparison ran six old-path presses followed by six
new-path presses on the same machine. The old launcher was reconstructed from
Terminal commit `c5af577` in an isolated fixture and instrumented with performance
counter timestamps; the installed launcher was not downgraded. The new path
used the shared helper from app `1ae7b31` / Terminal `e1dab0f`.

| Instrumented batch | Median ms | Mean ms | Range ms |
| --- | ---: | ---: | ---: |
| Before | 1337.4 | 1341.8 | 1325.0-1373.3 |
| After | 370.8 | 378.0 | 359.6-421.0 |

The following rows group sequential stages into comparable work. They use
**means**, which add to the mean total within rounding. Individual stage
medians do not necessarily add to the overall median.

| Work on the shortcut path | Before mean ms | After mean ms |
| --- | ---: | ---: |
| Terminal/Python startup, Python imports and argument parsing | 125.4 | 123.1 |
| Settings, live records, helper request and event setup | 1.0 | 3.6 |
| First helper startup, libraries, compilation and initialization | 365.3 | 90.4 |
| Initial tab discovery and most-recently-used selection | 80.1 | 72.4 |
| Probe result, second helper startup, libraries and compilation | 346.2 | 0.0 |
| Launcher process exit check/wait | 5.0 | 8.7 |
| Fixed pause before / actual tab-close wait after | 314.5 | 52.4 |
| Destination lookup, tab selection and content focus | 104.4 | 27.5 |
| **Total** | **1341.8** | **378.0** |

The old requested 300 ms pause occupied 314.5 ms between the surrounding
timestamps, including scheduling and PowerShell dispatch. Its exit check was
short partly because Python had time to exit during the second helper's
startup. The new helper begins waiting earlier. These wait rows therefore
have different work around them.

The old helpers spent a combined **302.5 ms compiling** and **251.2 ms starting
PowerShell**. The new helper is compiled during installation. Afterward, its
process/CLR startup averaged **34.9 ms** and native initialization/options
**55.5 ms**. That remaining runtime startup is not eliminated by precompilation.

Raw files contain all samples plus mean, median, minimum and maximum for each
of the **25 old** and **16 new** sequential stages:
[before stages](benchmarks/herdr-switch-before-stages.json),
[after stages](benchmarks/herdr-comparison-after-stages.json).
An [earlier after-only profile](benchmarks/herdr-switch-stages.json) is retained separately.
Post-focus verification took a median 18.4 ms before and 16.8 ms after; this
tail is excluded from the user-visible latency and stage totals.

This is stage profiling, not a separate microbenchmark of every function or
Windows API call. Instrumented and uninstrumented batches ran separately.
Their differences combine instrumentation and normal variation; they do not
isolate tracing overhead. The later Python-environment compatibility changes
were not part of this timing comparison.

## What might be optimized next

These are hypotheses based on measured costs, not promised savings.

| Candidate | Evidence and practical tradeoff |
| --- | --- |
| Reduce repeated accessibility property requests | Initial discovery/selection averaged 72.4 ms. Windows UI Automation supports caching properties to reduce cross-process calls. Test bulk/cached reads while preserving duplicate identity, stale-record checks and both scopes. The result depends on the provider and tab count. |
| Let a native launcher perform the return path directly | Terminal/Python startup plus imports costs 123.1 ms, but part of that is Terminal itself. Removing Python cannot be assumed to save all 123.1 ms. It also moves settings and record handling into another implementation. |
| Reduce native helper startup | Startup and initialization total 90.4 ms. Fewer initialization steps might help; a persistent helper could amortize startup but adds service lifecycle, IPC and update complexity. No such service is currently installed. |
| Avoid creating the temporary launcher tab | Could remove some Terminal startup and the 52.4 ms tab-disposal wait. This needs another launch mechanism and changes shortcut ownership and behavior. Simply deleting the wait can reintroduce incorrect focus. |
| Settings/record reads | Together roughly 1 ms. Low priority relative to the rows above. |

The caching opportunity follows Microsoft's
[UI Automation client caching documentation](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-cachingforclients).
It has not yet been implemented or timed here. The first measured helper start
and cache lookup were slower than later samples; the cause was not isolated.

## What changes on another developer's computer

The measured desktop runs Windows 11 Pro build 26200, an Intel Core i5-13600K,
Windows Terminal 1.24.11911.0, PowerShell 7.6.5 and Python 3.12.11. The private
venv's base interpreter is **Miniforge**. The return shortcut calls that venv
directly; it does **not** run `conda activate` or the user's PowerShell profile.

| Environment difference | Expected effect or compatibility concern |
| --- | --- |
| CPU, power mode and competing work | Process startup, JIT/runtime initialization and scheduling can vary. No cross-machine or power-mode comparison was run. |
| Disk, caches, antivirus and managed endpoint policies | May change executable/import startup or block helper creation and process detachment. No causal antivirus or cold-cache experiment was run. |
| Python distribution and environment variables | Base-runtime DLL availability and import configuration can differ. Managed commands now ignore `PYTHONHOME`, `PYTHONPATH` and user site packages, and use an absolute private interpreter path. |
| Conda and other environment managers | Installation can select a supported real Windows Python executable. The tested Miniforge venv imported SSL, ctypes and Textual without Conda activation and with a minimal PATH. This does not establish compatibility with every Conda build or shim. |
| Terminal/.NET versions, tab and window counts | Accessibility traversal and tab disposal depend on the local provider, runtime and number of views. Cross-window correctness was tested separately; cross-window latency was not measured here. |
| Relocated checkouts or removed base Python | Generated shortcuts reference local paths; venvs also depend on their base interpreter. Rerun setup at the new location and recreate an invalid venv after keeping a backup. |
| SSH, VPN and remote server | Affect connection establishment, transport and reconnection. Returning focus to an already open local tab does not make a new SSH connection. |

Python documents the launch flags in its
[command-line reference](https://docs.python.org/3/using/cmdline.html) and the
base-interpreter and activation behavior in its
[venv documentation](https://docs.python.org/3/library/venv.html).
Conda documents Windows activation and library-loading considerations in
[Managing environments](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html).

The supported target remains Windows 10/11 with Windows Terminal. WSL can be
a Terminal profile or SSH destination; WSL Python cannot run the Windows helper.
The future physical laptop and other developers' installations remain untested.

## Method, reproduction and correctness checks

The benchmark creates a temporary Terminal window with the destination before
the source tab, then sends the real Ctrl+Alt+H/P shortcut. The target is not
adjacent to the temporary launcher: automatic adjacent-tab selection therefore
cannot falsely pass the measurement. This is a test layout, with no added
production behavior or latency. A brief intermediate tab can still appear.

A cached accessibility handle is polled roughly every 5 ms until the correct
window is foreground, the target is selected, and terminal content has keyboard
focus. Python and C# use the shared Windows performance counter. Each stage is
clipped at observed focus. Setup, initial tab readiness, benchmark-helper
compilation and the one-second inter-sample cooldown are outside the stopwatch.
Existing windows remain present and can affect discovery cost. Six samples on
one desktop do not establish a distribution across users or a cold-start bound.

Run against an installed setup with a reachable Herdr target:

```powershell
.\apps\port-forward-tui\.venv\Scripts\python.exe -E -s scripts/benchmark_switch.py --yes --app herdr --samples 6 --output artifacts/herdr.json
.\apps\port-forward-tui\.venv\Scripts\python.exe -E -s scripts/benchmark_switch.py --yes --app herdr --trace --samples 6 --output artifacts/herdr-stages.json
```

Tracing temporarily changes the return command, then restores it while
preserving unrelated settings edits. Normal shortcuts write no trace files.
The old end-to-end behavior is available at Terminal commit `c5af577`; the
instrumented old fixture was diagnostic code rather than a shipped launcher.

The native-helper change passed 45 app tests and 15 Terminal tests. Actual
keyboard checks passed both scopes, duplicate MRU selection for both apps,
new-view fallback, content focus, and cancellation after another application
took focus. Python compatibility adds four bootstrap tests, including a fresh
venv in a path containing spaces, Unicode and an apostrophe, with conflicting
Python variables and a minimal PATH. All 49 app tests passed locally. These
checks establish observed behavior, not a guarantee against future Windows
or Terminal changes.
