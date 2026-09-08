"""Attach another Herdr view, or return to the last-used live Terminal tab."""
import time
STARTED = time.perf_counter()

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "apps/port-forward-tui"))
from port_forward_tui.focus_settings import read_scope
from port_forward_tui.forwarding import DATA_DIR, SSH, validate_host, ssh_options
from port_forward_tui.machines import Catalog
from port_forward_tui.window_context import choose_machine
from port_forward_tui.views import mark_origin, process_alive, delayed_focus, focus_command, native_focus

POWERSHELL = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"


class LaunchTrace:
    """Opt-in profiling only; no files are written during ordinary shortcuts."""
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / (uuid.uuid4().hex + ".json")
        self.events = [{"name": "python_entry", "at": STARTED}]
        self.mark("arguments_parsed")

    def mark(self, name):
        self.events.append({"name": name, "at": time.perf_counter()})

    def save(self):
        self.path.with_suffix(".launcher.json").write_text(json.dumps(self.events), encoding="utf-8")


def helper(mode, *arguments):
    return [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(ROOT / "terminal_views.ps1"), "-Mode", mode, *map(str, arguments)]


def view_directory(directory: Path, host: str) -> Path:
    return directory / "herdr-views" / hashlib.sha256(host.encode()).hexdigest()[:16]


def live_records(directory: Path) -> list[dict]:
    records = []
    for path in directory.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if process_alive(record["pid"]):
                records.append(record)
            else:
                path.unlink(missing_ok=True)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return records


def try_focus(directory: Path, scope: str, origin_title: str = "", probe=False, trace=None) -> bool:
    if not probe and not origin_title:
        return False
    records = live_records(directory)
    if trace:
        trace.mark("records_loaded")
    if not records:
        return False
    payload = base64.b64encode(json.dumps(records).encode()).decode("ascii")
    executable = focus_command()
    if trace:
        trace.mark("helper_ready")
    try:
        if len(executable) == 1:
            command = [*executable, "-RecordsBase64", payload, "-Scope", scope]
            if origin_title:
                command.extend(["-OriginTitle", origin_title])
            if trace:
                command.extend(["-TracePath", str(trace.path)])
            if not probe:
                return native_focus(command, trace=trace)
            result = subprocess.run([*command, "-ProbeOnly"], capture_output=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=8)
            return result.returncode == 0
        result = subprocess.run(helper("Probe", "-RecordsBase64", payload,
                                       "-Scope", scope, "-OriginTitle", origin_title),
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding="utf-8",
                                creationflags=subprocess.CREATE_NO_WINDOW, timeout=8)
        if result.returncode != 0:
            return False
        if probe:
            return True
        target = json.loads(result.stdout)
        if not isinstance(target.get("origin"), int) or not target["origin"]:
            return False
        return delayed_focus(helper("Activate", "-RuntimeId", target["runtime_id"],
                                    "-AfterPid", os.getpid(), "-InvokeWindow", target["origin"]))
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host")
    parser.add_argument('--machine')
    parser.add_argument('--machines', action='store_true')
    parser.add_argument('--client', choices=('ssh', 'herdr'), default='herdr')
    parser.add_argument('--local', action='store_true', help='Open local Herdr, without a remote machine')
    parser.add_argument("--herdr", default=str(Path(os.environ["LOCALAPPDATA"]) / "Programs/Herdr/bin/herdr.exe"))
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--focus-existing", action="store_true")
    parser.add_argument("--trace-dir", type=Path, help=argparse.SUPPRESS)
    options = parser.parse_args()
    trace = LaunchTrace(options.trace_dir) if options.trace_dir else None
    catalog = Catalog(options.data_dir)
    machine = None
    if not options.local:
        selector = catalog.add(options.host).id if options.host else options.machine
        machine = choose_machine(catalog, selector, picker=options.machines, purpose='Choose a machine for a remote session')
        if machine is None:
            return 0
        options.host = machine.target
    if (options.local or options.client == 'herdr') and not Path(options.herdr).is_file():
        raise ValueError("Herdr executable not found; pass --herdr PATH")
    scope = read_scope(machine.directory if machine else options.data_dir)
    if options.local:
        directory = options.data_dir / 'local-herdr-views'
        session_command = [options.herdr]
    else:
        # Herdr accepts SSH aliases. For custom config/port overrides use the
        # ordinary SSH client, which can honor those settings explicitly.
        client = 'ssh' if machine.ssh_port or machine.ssh_config else options.client
        directory = view_directory(options.data_dir, options.host) if client == 'herdr' else options.data_dir / 'ssh-views' / machine.id
        session_command = ([options.herdr, '--remote', machine.target] if client == 'herdr' else
                           [SSH, *ssh_options(machine.ssh_port, machine.ssh_config), machine.target])
    directory.mkdir(parents=True, exist_ok=True)
    origin = mark_origin()
    if trace:
        trace.mark("settings_loaded")
    if options.focus_existing:
        try:
            if try_focus(directory, scope, origin, trace=trace):
                return 0
        finally:
            if trace:
                trace.save()
    record = directory / (uuid.uuid4().hex + ".json")
    context = options.data_dir / 'window-views' / record.name if machine else None
    if context:
        context.parent.mkdir(parents=True, exist_ok=True)
    tracker = None
    try:
        with (directory / "tracker.log").open("ab") as log:
            tracker_command = helper("Track", "-RecordPath", record, "-InitialTitle", origin, "-OwnerPid", os.getpid())
            if context:
                tracker_command += ['-MachineId', machine.id, '-ContextPath', str(context)]
            tracker = subprocess.Popen(tracker_command,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 8
        while not record.exists() and tracker.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        if not record.exists():
            print("Herdr will open, but this tab could not register for the return shortcut.", file=sys.stderr)
        # Inherit the console unchanged; Herdr owns its input, output and SSH session.
        return subprocess.call(session_command)
    finally:
        if tracker:
            if tracker.poll() is None:
                tracker.terminate()
            tracker.wait(timeout=5)
        record.unlink(missing_ok=True)
        if context:
            context.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"Herdr shortcut: {error}", file=sys.stderr)
        raise SystemExit(1)
