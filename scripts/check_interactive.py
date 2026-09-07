"""Opt-in desktop test: opens temporary Terminal windows and sends real shortcuts."""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps/port-forward-tui"))
from forwarding import DATA_DIR
from focus_settings import save_scope
from herdr_launcher import helper, live_records, view_directory

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def state():
    result = subprocess.run(helper("State"), capture_output=True, encoding="utf-8", timeout=12,
                            creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    return json.loads(result.stdout)


def activate(tab):
    subprocess.run(helper("Activate", "-RuntimeId", tab["runtime_id"]), check=True, timeout=12,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(.4)


def chord(letter, shift=False):
    keys = [0x11, 0x12] + ([0x10] if shift else []) + [ord(letter)]
    try:
        for key in keys:
            user32.keybd_event(key, 0, 0, 0)
        time.sleep(.06)
    finally:
        for key in reversed(keys):
            user32.keybd_event(key, 0, 2, 0)


def wait_for(predicate, message, timeout=22):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = state()
        result = predicate(current)
        if result:
            print("PASS: " + message, flush=True)
            return current
        time.sleep(.3)
    raise AssertionError(message + "\n" + json.dumps(current))


def is_active(current, tab):
    return current["foreground"] == tab["window"] and current.get("focused_type") == "ControlType.Text" and any(
        t["runtime_id"] == tab["runtime_id"] and t["selected"] for t in current["tabs"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Allow desktop focus changes and temporary windows")
    options = parser.parse_args()
    if not options.yes:
        parser.error("Run with --yes while you are ready for desktop focus to move")
    machine = json.loads((ROOT / ".machine.json").read_text())
    records_dir = view_directory(DATA_DIR, machine["ssh_host"])
    before = {t["window"] for t in state()["tabs"]}
    preferences = DATA_DIR / "ui-settings.json"
    original = preferences.read_bytes() if preferences.exists() else None
    created = set()
    try:
        windows = []
        for label in ("A", "B"):
            existing = before | created
            subprocess.Popen([str(ROOT / "build/TerminalWorkspace.exe")])
            current = wait_for(lambda s: len([t for t in s["tabs"] if t["window"] not in existing]) == 2,
                               f"launcher {label} creates exactly two tabs")
            window = next(t["window"] for t in current["tabs"] if t["window"] not in existing)
            created.add(window)
            current = wait_for(lambda s: any(t["window"] == window and t["title"].startswith("Ports | ") for t in s["tabs"])
                and any(r["window"] == window for r in live_records(records_dir)), f"window {label} registers both app views")
            tabs = [t for t in current["tabs"] if t["window"] == window]
            ports = next(t for t in tabs if t["title"].startswith("Ports | "))
            herdr = next(t for t in tabs if t != ports)
            wait_for(lambda s: is_active(s, herdr), f"launcher {label} leaves the Herdr tab selected")
            windows.append((herdr, ports))
        (ha, pa), (hb, pb) = windows
        save_scope(DATA_DIR, "all")
        activate(pa)
        activate(hb)
        chord("P")
        wait_for(lambda s: is_active(s, pa) and len([t for t in s["tabs"] if t["window"] in created]) == 4,
                 "Ctrl+Alt+P returns across windows and removes its temporary launcher tab")
        save_scope(DATA_DIR, "window")
        activate(hb)
        chord("P")
        wait_for(lambda s: is_active(s, pb), "Ctrl+Alt+P stays in the invoking window")
        save_scope(DATA_DIR, "all")
        activate(ha)
        activate(pb)
        chord("H")
        wait_for(lambda s: is_active(s, ha), "Ctrl+Alt+H returns to the last-used Herdr view across windows")
        save_scope(DATA_DIR, "window")
        activate(pb)
        chord("H")
        wait_for(lambda s: is_active(s, hb), "Ctrl+Alt+H stays in the invoking window despite duplicate titles")
        activate(pb)
        old_tabs = {t["runtime_id"] for t in state()["tabs"]}
        chord("H", shift=True)
        current = wait_for(lambda s: any(t["window"] == hb["window"] and t["runtime_id"] not in old_tabs for t in s["tabs"]),
                           "Ctrl+Alt+Shift+H opens an additional Herdr view")
        second_herdr = next(t for t in current["tabs"] if t["window"] == hb["window"] and t["runtime_id"] not in old_tabs)
        wait_for(lambda s: any(r["runtime_id"] == second_herdr["runtime_id"] for r in live_records(records_dir)),
                 "duplicate Herdr tab has its own registered identity")
        activate(hb)
        activate(pb)
        chord("H")
        wait_for(lambda s: is_active(s, hb), "return shortcut chooses the older duplicate when it was used last")
        activate(second_herdr)
        activate(pb)
        chord("H")
        wait_for(lambda s: is_active(s, second_herdr), "return shortcut chooses the newer duplicate after its last focus changes")
        activate(pa)
        old_tabs = {t["runtime_id"] for t in state()["tabs"]}
        chord("P", shift=True)
        current = wait_for(lambda s: any(t["window"] == pa["window"] and t["runtime_id"] not in old_tabs and t["title"].startswith("Ports | ") for t in s["tabs"]),
                 "Ctrl+Alt+Shift+P opens an additional Ports view")
        second_ports = next(t for t in current["tabs"] if t["window"] == pa["window"] and t["runtime_id"] not in old_tabs)
        activate(pa)
        activate(ha)
        chord("P")
        wait_for(lambda s: is_active(s, pa), "Ports return chooses the older duplicate when it was used last")
        activate(second_ports)
        activate(ha)
        chord("P")
        wait_for(lambda s: is_active(s, second_ports), "Ports return chooses the newer duplicate after its last focus changes")
        existing = before | created
        subprocess.Popen(["wt.exe", "-w", "new", "new-tab", "-p", "{574e775e-4f2a-5b96-ac1e-a2962a402336}"])
        current = wait_for(lambda s: any(t["window"] not in existing for t in s["tabs"]), "empty test window opens")
        shell = next(t for t in current["tabs"] if t["window"] not in existing)
        created.add(shell["window"])
        activate(shell)
        chord("P")
        wait_for(lambda s: s["foreground"] == shell["window"] and any(t["window"] == shell["window"] and t["title"].startswith("Ports | ") and t["selected"] for t in s["tabs"]),
                 "window with no Ports view opens one locally instead of jumping elsewhere")
        activate(shell)
        chord("H")
        wait_for(lambda s: s["foreground"] == shell["window"] and any(r["window"] == shell["window"] for r in live_records(records_dir)),
                 "window with no Herdr view opens one locally instead of jumping elsewhere")
        from check_foreground import check_handoff
        save_scope(DATA_DIR, "all")
        for app, target, other in (("ports", pa, ha), ("herdr", ha, pa)):
            activate(target)
            activate(other)
            check_handoff(app, target, machine)
        print("PASS: real desktop shortcut checks completed", flush=True)
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
