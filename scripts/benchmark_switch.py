"""Measure actual Herdr/Ports keypress-to-content-focus latency in temporary tabs."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import statistics
import subprocess

from check_interactive import ROOT, state, wait_for
from focus_settings import save_scope
from forwarding import DATA_DIR
from herdr_launcher import helper, live_records, view_directory
from configure import HERDR, PORTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--samples", type=int, default=6)
    parser.add_argument("--app", choices=("ports", "herdr"), default="ports")
    parser.add_argument("--trace", action="store_true", help="Profile Herdr stages using a temporary shortcut override")
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    if not options.yes:
        parser.error("Use --yes to allow temporary windows and focus changes")
    if not 1 <= options.samples <= 30:
        parser.error("Use between 1 and 30 samples")
    if options.trace and options.app != "herdr":
        parser.error("Stage tracing currently requires --app herdr")
    before = {t["window"] for t in state()["tabs"]}
    preferences = DATA_DIR / "ui-settings.json"
    original = preferences.read_bytes() if preferences.exists() else None
    created = set()
    try:
        save_scope(DATA_DIR, "all")
        # Put the target before the source, so closing the temporary launcher
        # cannot accidentally focus the target just because it is adjacent.
        profiles = (PORTS, HERDR) if options.app == "ports" else (HERDR, PORTS)
        subprocess.Popen(["wt.exe", "-w", "new", "new-tab", "-p", profiles[0], ";", "new-tab", "-p", profiles[1]])
        current = wait_for(lambda s: len([t for t in s["tabs"] if t["window"] not in before]) == 2,
                           "benchmark window opened")
        created = {t["window"] for t in current["tabs"]} - before
        current = wait_for(lambda s: any(t["window"] in created and t["title"].startswith("Ports | ") for t in s["tabs"]),
                           "Ports benchmark view ready")
        if options.app == "herdr":
            machine = json.loads((ROOT / ".machine.json").read_text())
            records = view_directory(DATA_DIR, machine["ssh_host"])
            current = wait_for(lambda s: any(r["window"] in created for r in live_records(records)),
                               "Herdr benchmark view registered")
            target_ids = {r["runtime_id"] for r in live_records(records) if r["window"] in created}
            target = next(t for t in current["tabs"] if t["runtime_id"] in target_ids)
        else:
            target = next(t for t in current["tabs"] if t["window"] in created and t["title"].startswith("Ports | "))
        source = next(t for t in current["tabs"] if t["window"] in created and t != target)
        # Compile once before the stopwatch starts. Poll cached UIA handles so
        # helper startup and whole-tree scans aren't counted as measurement lag.
        command = """param([string]$Root,[string]$Target,[string]$Source,[int]$Count,[byte]$Shortcut)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase,System.Web.Extensions
$refs = @('System.dll','System.Core.dll',[System.Windows.Automation.AutomationElement].Assembly.Location,
 [System.Windows.Automation.ControlType].Assembly.Location,[System.Windows.Threading.Dispatcher].Assembly.Location,
 [System.Web.Script.Serialization.JavaScriptSerializer].Assembly.Location)
Add-Type -Path @((Join-Path $Root 'scripts/TerminalViews.cs'),(Join-Path $Root 'scripts/BenchmarkSwitch.cs')) -ReferencedAssemblies $refs
[BenchmarkSwitch]::Run($Target,$Source,$Count,$Shortcut)
"""
        import tempfile
        with tempfile.TemporaryDirectory(prefix="terminal-benchmark-") as folder:
            script = Path(folder) / "measure.ps1"
            script.write_text(command, encoding="utf-8")
            from profile_focus import collect, trace_herdr
            trace_dir = Path(folder) / "traces"
            with trace_herdr(trace_dir) if options.trace else nullcontext():
                result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                    "-Root", str(ROOT), "-Target", target["runtime_id"], "-Source", source["runtime_id"], "-Count", str(options.samples),
                    "-Shortcut", str(ord("P" if options.app == "ports" else "H"))],
                    capture_output=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW, timeout=90)
                if result.returncode:
                    raise RuntimeError(result.stderr)
            measurements = json.loads(result.stdout)
            stages, verification_tail = collect(trace_dir, measurements) if options.trace else (None, None)
        samples = [m["milliseconds"] for m in measurements]
        report = {"app": options.app, "samples_ms": [round(x, 1) for x in samples], "median_ms": round(statistics.median(samples), 1),
                  "min_ms": round(min(samples), 1), "max_ms": round(max(samples), 1)}
        if stages:
            report["stage_timings_ms"] = stages
            report["helper_verification_after_focus_ms"] = verification_tail
        if options.output:
            options.output.parent.mkdir(parents=True, exist_ok=True)
            options.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    finally:
        if original is None:
            preferences.unlink(missing_ok=True)
        else:
            preferences.write_bytes(original)
        for window in created:
            subprocess.run(helper("CloseTestWindow", "-WindowHandle", window), timeout=12,
                           creationflags=subprocess.CREATE_NO_WINDOW)


if __name__ == "__main__":
    main()
