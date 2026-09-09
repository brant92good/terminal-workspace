"""Measure actual Herdr/Ports keypress-to-content-focus latency in temporary tabs."""
import argparse
from contextlib import nullcontext, ExitStack
import json
from pathlib import Path
import statistics
import subprocess
import sys

from check_interactive import ROOT, small_test_window, wait_for
from port_forward_tui.focus_settings import save_scope
from port_forward_tui.forwarding import DATA_DIR
from port_forward_tui.machines import Catalog
from herdr_launcher import live_records, view_directory
from configure import HERDR, PORTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--samples", type=int, default=6)
    parser.add_argument("--app", choices=("ports", "herdr"), default="ports")
    parser.add_argument("--trace", action="store_true", help="Profile Herdr stages using a temporary shortcut override")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--machine", help="Saved machine ID/name for the initial benchmark views")
    options = parser.parse_args()
    if not options.yes:
        parser.error("Use --yes to allow temporary windows and focus changes")
    if not 1 <= options.samples <= 30:
        parser.error("Use between 1 and 30 samples")
    if options.trace and options.app != "herdr":
        parser.error("Stage tracing currently requires --app herdr")
    catalog = Catalog(DATA_DIR)
    machines = catalog.list()
    if not options.machine and len(machines) != 1:
        parser.error("Select an existing machine with --machine ID_OR_NAME")
    machine = catalog.get(options.machine) if options.machine else machines[0]
    settings = json.loads((ROOT / ".machine.json").read_text(encoding="utf-8-sig"))
    client = "ssh" if machine.ssh_port or machine.ssh_config else settings.get("remote_client", "ssh")
    preferences = machine.directory / "ui-settings.json"
    original = preferences.read_bytes() if preferences.exists() else None
    created = set()
    windows = ExitStack()
    try:
        # Never allow a failed test view to redirect the shortcut to a user's
        # matching tab in a different Terminal window.
        save_scope(machine.directory, "window")
        # Put the target before the source, so closing the temporary launcher
        # cannot accidentally focus the target just because it is adjacent.
        profiles = (PORTS, HERDR) if options.app == "ports" else (HERDR, PORTS)
        commands = {
            PORTS: [sys.executable, "-E", "-s", str(ROOT / "apps/port-forward-tui/app.py"), "--machine", machine.id],
            HERDR: [sys.executable, "-E", "-s", str(ROOT / "scripts/herdr_launcher.py"),
                    "--machine", machine.id, "--client", client],
        }
        if settings.get("herdr"):
            commands[HERDR].extend(["--herdr", settings["herdr"]])
        # Explicit selection only initializes the views. Actual return keypresses
        # use the installed shortcut, including its window/machine lookup.
        created = {windows.enter_context(small_test_window([(profile, commands[profile]) for profile in profiles]))}
        current = wait_for(lambda s: any(t["window"] in created and t["title"].startswith("Ports | ") for t in s["tabs"]),
                           "Ports benchmark view ready")
        if options.app == "herdr":
            records = (view_directory(DATA_DIR, machine.target) if client == "herdr"
                       else DATA_DIR / "ssh-views" / machine.id)
            current = wait_for(lambda s: any(r["window"] in created for r in live_records(records)),
                               "Herdr benchmark view registered")
            target_ids = {r["runtime_id"] for r in live_records(records) if r["window"] in created}
            target = next(t for t in current["tabs"] if t["runtime_id"] in target_ids)
        else:
            target = next(t for t in current["tabs"] if t["window"] in created and t["title"].startswith("Ports | "))
        source = next(t for t in current["tabs"] if t["window"] in created and t != target)
        # Compile once before the stopwatch starts. Poll cached UIA handles so
        # helper startup and whole-tree scans aren't counted as measurement lag.
        command = """param([string]$Root,[string]$Target,[string]$Source,[int]$Count,[byte]$Shortcut,[long]$Window)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase,System.Web.Extensions
$refs = @('System.dll','System.Core.dll',[System.Windows.Automation.AutomationElement].Assembly.Location,
 [System.Windows.Automation.ControlType].Assembly.Location,[System.Windows.Threading.Dispatcher].Assembly.Location,
 [System.Web.Script.Serialization.JavaScriptSerializer].Assembly.Location)
Add-Type -Path @((Join-Path $Root 'scripts/TerminalViews.cs'),(Join-Path $Root 'scripts/BenchmarkSwitch.cs')) -ReferencedAssemblies $refs
[BenchmarkSwitch]::Run($Target,$Source,$Count,$Shortcut,$Window)
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
                    "-Shortcut", str(ord("P" if options.app == "ports" else "R")), "-Window", str(target['window'])],
                    capture_output=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW, timeout=90)
                if result.returncode:
                    raise RuntimeError(result.stderr)
            measurements = json.loads(result.stdout)
            stages, verification_tail = collect(trace_dir, measurements) if options.trace else (None, None)
        samples = [m["milliseconds"] for m in measurements]
        report = {"app": options.app, "saved_machine_count": len(machines), "remote_client": client, "focus_scope": "window",
                  "samples_ms": [round(x, 1) for x in samples], "median_ms": round(statistics.median(samples), 1),
                  "min_ms": round(min(samples), 1), "max_ms": round(max(samples), 1)}
        if stages:
            report["stage_timings_ms"] = stages
            report["helper_verification_after_focus_ms"] = verification_tail
        if options.output:
            options.output.parent.mkdir(parents=True, exist_ok=True)
            options.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    finally:
        try:
            if original is None:
                preferences.unlink(missing_ok=True)
            else:
                preferences.write_bytes(original)
        finally:
            windows.close()


if __name__ == "__main__":
    main()
