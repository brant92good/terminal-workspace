"""Opt-in real SSH traffic check after closing a whole temporary Terminal window."""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

from check_interactive import ROOT, state, wait_for, activate, user32
from herdr_launcher import helper
from port_forward_tui.background import exchange
from port_forward_tui.forwarding import Store, Forward
from port_forward_tui.views import process_alive


def has_process_job(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel.IsProcessInJob.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        result = wintypes.BOOL()
        if not kernel.IsProcessInJob(handle, None, ctypes.byref(result)):
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(result.value)
    finally:
        kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true")
    options = parser.parse_args()
    if not options.yes:
        parser.error("Use --yes to open and close a temporary Terminal window")
    machine = json.loads((ROOT / ".machine.json").read_text())
    before = {t["window"] for t in state()["tabs"]}
    with tempfile.TemporaryDirectory(prefix="terminal-persistence-check-") as folder:
        directory = Path(folder)
        store = Store(directory)
        store.host = machine["ssh_host"]
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        rule = Forward.make(port, 22, "Temporary Terminal lifecycle test")
        store.save([rule])
        window = daemon_pid = None
        try:
            subprocess.Popen(["wt.exe", "-w", "new", "new-tab", "--",
                sys.executable, str(ROOT / "apps/port-forward-tui/app.py"), "--data-dir", folder])
            current = wait_for(lambda s: any(t["window"] not in before and t["title"].startswith("Ports | ") for t in s["tabs"]),
                "isolated port app opened in its own Terminal window")
            tab = next(t for t in current["tabs"] if t["window"] not in before)
            window = tab["window"]
            activate(tab)
            # Start the only saved rule using the actual app's keyboard path.
            user32.keybd_event(0x0D, 0, 0, 0)
            time.sleep(.08)
            user32.keybd_event(0x0D, 0, 2, 0)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                response = exchange(directory, "status")
                if response["states"].get(rule.id) == "ON":
                    break
                if response["states"].get(rule.id) == "ERROR":
                    raise AssertionError("Temporary SSH tunnel failed to start")
                time.sleep(.1)
            else:
                raise AssertionError("Temporary tunnel did not become ready")
            daemon_pid = response["pid"]
            if has_process_job(daemon_pid):
                raise AssertionError("Supervisor remains attached to a Windows process job")
            subprocess.run(helper("CloseTestWindow", "-WindowHandle", window), check=True,
                timeout=12, creationflags=subprocess.CREATE_NO_WINDOW)
            wait_for(lambda s: not any(t["window"] == window for t in s["tabs"]), "whole temporary Terminal window closed")
            response = exchange(directory, "status")
            if response["pid"] != daemon_pid or response["states"].get(rule.id) != "ON":
                raise AssertionError("Original supervisor or tunnel did not survive")
            with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
                if not connection.recv(256).startswith(b"SSH-2.0-"):
                    raise AssertionError("No SSH banner crossed the surviving tunnel")
            print("PASS: real traffic survives closing the whole window; supervisor is outside Terminal's process jobs", flush=True)
        finally:
            if window and any(t["window"] == window for t in state()["tabs"]):
                subprocess.run(helper("CloseTestWindow", "-WindowHandle", window), timeout=12,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                response = exchange(directory, "shutdown")
                daemon_pid = response["pid"]
            except (OSError, ValueError):
                pass
            deadline = time.monotonic() + 8
            while daemon_pid and process_alive(daemon_pid) and time.monotonic() < deadline:
                time.sleep(.1)
            if daemon_pid and process_alive(daemon_pid):
                raise AssertionError("Test supervisor did not stop after explicit shutdown")
        print("PASS: isolated test tunnel stopped; user favorites and tunnels untouched", flush=True)


if __name__ == "__main__":
    main()
