"""Attach another Herdr view, or return to the last-used live Terminal tab."""
import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "apps/port-forward-tui"))
from focus_settings import read_scope
from forwarding import DATA_DIR, validate_host
from views import mark_origin, process_alive, delayed_focus

POWERSHELL = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"


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


def try_focus(directory: Path, scope: str, origin_title: str = "", probe=False) -> bool:
    records = live_records(directory)
    if not records:
        return False
    payload = base64.b64encode(json.dumps(records).encode()).decode("ascii")
    try:
        result = subprocess.run(helper("Probe", "-RecordsBase64", payload,
                                       "-Scope", scope, "-OriginTitle", origin_title),
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding="utf-8",
                                creationflags=subprocess.CREATE_NO_WINDOW, timeout=8)
        if result.returncode != 0:
            return False
        if probe:
            return True
        target = json.loads(result.stdout)
        user32 = ctypes.WinDLL("user32")
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        return delayed_focus(helper("Activate", "-RuntimeId", target["runtime_id"],
                                    "-AfterPid", os.getpid(), "-InvokeWindow", user32.GetForegroundWindow()))
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--herdr", default=str(Path(os.environ["LOCALAPPDATA"]) / "Programs/Herdr/bin/herdr.exe"))
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--focus-existing", action="store_true")
    options = parser.parse_args()
    validate_host(options.host)
    if not Path(options.herdr).is_file():
        raise ValueError("Herdr executable not found; pass --herdr PATH")
    scope = read_scope(options.data_dir)
    directory = view_directory(options.data_dir, options.host)
    directory.mkdir(parents=True, exist_ok=True)
    origin = mark_origin()
    if options.focus_existing and try_focus(directory, scope, origin):
        return 0
    record = directory / (uuid.uuid4().hex + ".json")
    tracker = None
    try:
        with (directory / "tracker.log").open("ab") as log:
            tracker = subprocess.Popen(helper("Track", "-RecordPath", record, "-InitialTitle", origin,
                                              "-OwnerPid", os.getpid()),
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 8
        while not record.exists() and tracker.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        if not record.exists():
            print("Herdr will open, but this tab could not register for the return shortcut.", file=sys.stderr)
        # Inherit the console unchanged; Herdr owns its input, output and SSH session.
        return subprocess.call([options.herdr, "--remote", options.host])
    finally:
        if tracker:
            if tracker.poll() is None:
                tracker.terminate()
            tracker.wait(timeout=5)
        record.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"Herdr shortcut: {error}", file=sys.stderr)
        raise SystemExit(1)
