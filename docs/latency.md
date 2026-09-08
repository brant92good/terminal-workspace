# Herdr return shortcut latency

Ctrl+Alt+H now uses the shared compiled focus helper to find a registered Herdr
tab and complete the handoff after the temporary launcher closes. Matching uses
the tab runtime identity and checks the owner PID plus process start time, so
changing titles, duplicate titles, and stale process records are handled.

On this Windows desktop, six actual keypresses per batch gave:

| Existing Herdr return | Median | Minimum | Maximum |
| --- | ---: | ---: | ---: |
| Old PowerShell handoff | 1292.1 ms | 1276.5 ms | 1298.0 ms |
| Native handoff, tracing disabled | 363.4 ms | 359.7 ms | 421.2 ms |
| Native handoff, tracing enabled | 376.6 ms | 370.1 ms | 398.1 ms |

The normal-path median fell by 71.9%.
Ports also measured 365.3 ms median across three checks with the shared helper.
The trace and normal batches ran separately; their difference includes ordinary
run-to-run variation, so it does not isolate instrumentation overhead.

## Stage profile

This is a profile of 16 sequential stages on the real shortcut path. The first
bucket includes Terminal tab creation and Python interpreter startup. The native
startup buckets include Windows process creation, .NET runtime startup, library
initialization, and parsing. Individual OS calls and every function have not been
benchmarked separately. Fresh TUI startup and cross-window latency are outside
these timings.

The tracing batch averaged 380.4 ms to observable content focus.
Means below can be added, allowing for rounding; medians of individual stages
need not add up to the overall median.

| Stage | Mean ms | Median ms | Min-max ms |
| --- | ---: | ---: | ---: |
| Terminal and Python startup | 70.71 | 70.49 | 66.73-74.17 |
| Python imports and arguments | 54.45 | 53.85 | 52.43-56.96 |
| Settings and origin marker | 0.46 | 0.45 | 0.43-0.48 |
| Read live view records | 0.58 | 0.57 | 0.53-0.70 |
| Payload and helper cache | 0.74 | 0.71 | 0.66-0.92 |
| Create handoff event | 0.10 | 0.09 | 0.08-0.16 |
| Helper process and CLR startup | 31.27 | 30.92 | 29.10-34.64 |
| Native initialization and options | 54.28 | 54.55 | 53.24-55.34 |
| Enumerate Terminal tabs | 70.07 | 69.80 | 68.03-72.25 |
| Choose live MRU target | 3.30 | 3.22 | 3.08-3.60 |
| Signal and wait for launcher exit | 8.63 | 8.63 | 8.25-9.03 |
| Wait for tab closure | 55.08 | 54.91 | 51.55-59.60 |
| Resolve destination tab | 13.19 | 10.77 | 10.41-18.43 |
| Select destination tab | 9.76 | 9.49 | 8.98-10.77 |
| Apply window foreground | 0.00 | 0.00 | 0.00-0.00 |
| Focus terminal content | 7.75 | 5.79 | 4.98-15.76 |

The helper continued verification for a median
16.5 ms after the observer saw usable keyboard focus.
That tail is reported separately in the raw data. Each stage above is clipped
at observed focus, so it excludes work occurring after the user-visible endpoint.

Most remaining time is in process/library startup and Windows accessibility
lookup. Settings and saved-view reads are already short. The measured tab-close
wait follows actual Terminal disposal; it is not a fixed sleep. No resident
keyboard hook or extra focus service is installed.

## Method and limits

Measurements ran on Windows Terminal 1.24.11911.0 with the existing default
Ctrl+Alt+H/P bindings. The benchmark prepares a temporary window containing the
target before the source tab, then sends the real keyboard shortcut. This layout
prevents automatic adjacent-tab selection from falsely satisfying the test. It
is a measurement control and adds no production behavior or delay.

A cached accessibility handle is polled roughly every 5 ms until the correct
window is foreground, the target is selected, and terminal text has keyboard
focus. Setup, compilation, initial tab readiness, and the one-second inter-sample
cooldown are outside the stopwatch. Existing windows also remain present during
the test; their number can affect accessibility lookup cost.

Python and C# timestamps use Windows' shared performance counter. With --trace,
the benchmark temporarily adds --trace-dir to the Herdr return command, then
restores the original settings. It preserves unrelated concurrent settings edits.
Normal shortcuts do not write trace files. The temporary-tab design remains, so
another tab can still appear briefly during handoff.

## Reproduce

```powershell
.\apps\port-forward-tui\.venv\Scripts\python.exe scripts/benchmark_switch.py --yes --app herdr --samples 6 --output artifacts/herdr.json
.\apps\port-forward-tui\.venv\Scripts\python.exe scripts/benchmark_switch.py --yes --app herdr --trace --samples 6 --output artifacts/herdr-stages.json
```

Raw samples: [old](herdr-switch-before.json), [new](herdr-switch-after.json),
[stage profile](herdr-switch-stages.json), [Ports check](ports-shared-helper-check.json).

Validation: 45 app tests and 15 Terminal setup tests passed. Real keyboard checks
passed both focus scopes, duplicate MRU selection for both apps, new-view fallback,
content focus, and leaving another application alone after a delayed lookup.
