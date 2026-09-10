"""Opt-in: first saved OFF rule originates inside a small owned Windows Terminal.

No SSH connection, live catalog, installed profile edit or desktop shortcut is
used. The compiled binaries may come from an extracted candidate release.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid

PWSH = "{574e775e-4f2a-5b96-ac1e-a2962a402336}"
NO_WINDOW = 0x08000000


class ProcessWitness:
    """Own a process handle and validate PID reuse with image + creation time."""
    def __init__(self, identity, expected):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.handle = self.kernel.OpenProcess(0x1000 | 0x100000, False, identity["pid"])
        if not self.handle:
            if ctypes.get_last_error() == 87:  # Process already exited.
                return
            raise ctypes.WinError(ctypes.get_last_error())
        actual = self.identity(identity["pid"], self.handle, identity["image"])
        if (actual["created"] != identity["created"] or
                Path(identity["image"]).resolve() != Path(expected).resolve() or
                Path(actual["image"]).resolve() != Path(expected).resolve()):
            self.close()
            raise RuntimeError("Owned process identity changed")

    @staticmethod
    def identity(pid, handle, exited_image=None):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(item) for item in times)):
            raise ctypes.WinError(ctypes.get_last_error())
        size = wintypes.DWORD(32768)
        image = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
            # Windows may release a terminated process's image metadata while
            # its cached process object/creation identity still exists.
            if exited_image is None or kernel.WaitForSingleObject(handle, 0) != 0:
                raise ctypes.WinError(ctypes.get_last_error())
            image.value = str(exited_image)
        return {"pid": pid, "created": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime, "image": image.value}

    def wait(self, seconds):
        return not self.handle or self.kernel.WaitForSingleObject(self.handle, int(seconds * 1000)) == 0

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def receipt(folder, name, value):
    temporary = folder / (name + ".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(folder / name)


def rpc(directory, command):
    endpoint = json.loads((directory / "endpoint.json").read_text(encoding="utf-8"))
    assert endpoint["protocol"] == 1 and 0 < endpoint["port"] < 65536
    assert len(endpoint["token"]) == 64
    with socket.create_connection(("127.0.0.1", endpoint["port"]), timeout=2) as stream:
        stream.settimeout(2)
        stream.sendall((json.dumps({**endpoint, "command": command}) + "\n").encode())
        data = bytearray()
        deadline = time.monotonic() + 3
        while b"\n" not in data:
            if time.monotonic() > deadline or len(data) > 2 * 1024 * 1024:
                raise TimeoutError("Owned controller response exceeded its bound")
            chunk = stream.recv(8192)
            if not chunk:
                raise RuntimeError("Owned controller response ended early")
            data.extend(chunk)
    result = json.loads(data)
    assert result["ok"] is True, result
    return result


def worker(folder, executable, machine):
    # This process is launched by wt.exe. No controller is started by the outer
    # harness, and the parent records the unique bootstrap tab before GO.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    receipt(folder, "worker-start.json", ProcessWitness.identity(os.getpid(), kernel.GetCurrentProcess()))
    deadline = time.monotonic() + 25
    while not (folder / "go").exists():
        if (folder / "STOP").exists() or time.monotonic() > deadline:
            return
        time.sleep(.05)
    (folder / "spawn-started").write_text("starting", encoding="ascii")
    child = subprocess.Popen([
        str(executable), "--data-dir", str(folder / "data"), "--machine", machine,
        "--json", "save", "--remote", "18763", "--name", "Owned OFF fixture",
    ], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = {"worker_pid": os.getpid(), "child_pid": child.pid}
    try:
        receipt(folder, "child-start.json", ProcessWitness.identity(child.pid, int(child._handle), executable))
        results = queue.Queue()
        for label, pipe in (("stdout", child.stdout), ("stderr", child.stderr)):
            def read(name=label, stream=pipe):
                results.put((name, stream.read()))
            threading.Thread(target=read, daemon=True).start()
        try:
            result["code"] = child.wait(timeout=12)
            captured = dict(results.get(timeout=2) for _ in range(2))
            result["stdout"] = captured["stdout"].decode("utf-8")
            result["stderr"] = captured["stderr"].decode("utf-8")
        except Exception as error:
            result["error"] = str(error)
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)
        (folder / "cli-reaped").write_text("reaped", encoding="ascii")
    receipt(folder, "result.json", result)
    # Keep the real Terminal container alive after the captured CLI exits.
    deadline = time.monotonic() + 45
    while not (folder / "STOP").exists() and time.monotonic() < deadline:
        time.sleep(.1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Allow one small owned Terminal window")
    parser.add_argument("--bundle-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", nargs=3, metavar=("FOLDER", "PORTS", "MACHINE"))
    options = parser.parse_args()
    if options.worker:
        worker_root = Path(options.worker[0])
        worker(worker_root, Path(options.worker[1]), options.worker[2])
        # Reached only after worker's own child wait/reap completed successfully.
        (worker_root / "worker-finished").write_text("finished", encoding="ascii")
        return
    if not options.yes or not options.bundle_dir:
        parser.error("Use --yes --bundle-dir EXTRACTED_PACKAGE for the explicit desktop check")
    installation = options.bundle_dir.resolve(strict=True)
    executable = installation / "bin/ports.exe"
    helper = installation / "bin/TerminalViews.exe"
    assert executable.is_file() and helper.is_file(), "Choose an extracted native parent package"
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    python_image = ProcessWitness.identity(os.getpid(), kernel.GetCurrentProcess())["image"]
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.IsZoomed.argtypes = [wintypes.HWND]
    user32.IsZoomed.restype = wintypes.BOOL
    user32.GetForegroundWindow.restype = wintypes.HWND

    def state():
        result = subprocess.run([str(helper), "-Mode", "State"], capture_output=True,
                                timeout=10, creationflags=NO_WINDOW, check=True)
        return json.loads(result.stdout)

    temp_parent = Path(tempfile.gettempdir()).resolve()
    folder = Path(tempfile.mkdtemp(prefix="native-window-save-", dir=temp_parent)).resolve()
    nonce = "Native save fixture " + uuid.uuid4().hex
    window = runtime = directory = None
    worker_witness = child_witness = None
    closed = False
    launched = False
    evidence = {"kind": "actual-Windows-Terminal-first-save", "ssh_started": False}
    close_script = folder / "close.ps1"
    close_script.write_text("""param([string]$Helper,[long]$Window,[string]$Nonce,[string]$Runtime)
$ErrorActionPreference='Stop'
[void][Reflection.Assembly]::LoadFrom($Helper)
$tabs = @([TerminalViews]::Tabs() | Where-Object { $_.window -eq $Window })
if ($tabs.Count -ne 1 -or $tabs[0].runtime_id -cne $Runtime -or $tabs[0].title -cne $Nonce) { throw 'Owned tab identity changed; refusing closure.' }
[TerminalViews]::CloseTestWindow($Window)
""", encoding="utf-8-sig")

    def close_owned():
        nonlocal closed
        if window is None or closed:
            return
        tabs = [tab for tab in state()["tabs"] if tab["window"] == window]
        if not tabs:
            closed = True
            return
        if len(tabs) != 1 or tabs[0]["runtime_id"] != runtime or tabs[0]["title"] != nonce:
            raise RuntimeError("Owned window changed; refusing to close other tabs")
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(close_script), "-Helper", str(helper), "-Window", str(window), "-Nonce", nonce, "-Runtime", runtime],
                       check=True, timeout=12, creationflags=NO_WINDOW)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if not any(tab["window"] == window for tab in state()["tabs"]):
                closed = True
                return
            time.sleep(.1)
        raise TimeoutError("Owned Terminal window did not close")

    try:
        added = subprocess.run([str(executable), "--data-dir", str(folder / "data"),
                                "machines", "add", "window-fixture.invalid", "--json"],
                               capture_output=True, timeout=10, creationflags=NO_WINDOW, check=True)
        machine = json.loads(added.stdout)["machine"]
        # Only `machines pick` exposes a directory in its public JSON result.
        # This fresh isolated catalog stores added machines under their IDs.
        assert len(machine["id"]) == 32 and all(c in "0123456789abcdef" for c in machine["id"])
        directory = folder / "data" / "machines" / machine["id"]
        assert (directory / "forwards.json").is_file(), "Fixture settings were not created"
        assert directory.resolve().is_relative_to(folder), "Fixture machine escaped its owned root"
        original_forwards = json.loads((directory / "forwards.json").read_text(encoding="utf-8"))["forwards"]
        assert not (directory / "endpoint.json").exists(), "No controller may exist before Terminal"
        before = state()
        evidence["previous_foreground"] = before["foreground"]
        launched = True
        subprocess.run(["wt.exe", "-w", nonce, "--size", "70,18", "--pos", "12,160",
                        "new-tab", "-p", PWSH, "--title", nonce, sys.executable, "-E", "-s",
                        str(Path(__file__).resolve()), "--worker", str(folder), str(executable), machine["id"]],
                       check=True, timeout=8, creationflags=NO_WINDOW)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            current = state()
            matches = [tab for tab in current["tabs"] if tab["title"] == nonce]
            if matches:
                assert len(matches) == 1, "Bootstrap title must identify exactly one tab"
                window, runtime = matches[0]["window"], matches[0]["runtime_id"]
                break
            time.sleep(.1)
        assert window is not None, "Owned bootstrap tab did not appear"
        assert window not in {tab["window"] for tab in before["tabs"]}, "Expected a new window"
        rectangle = wintypes.RECT()
        assert user32.GetWindowRect(window, ctypes.byref(rectangle))
        width, height = rectangle.right - rectangle.left, rectangle.bottom - rectangle.top
        evidence["window"] = window
        evidence["runtime_id"] = runtime
        evidence["measured_size"] = [width, height]
        assert not user32.IsZoomed(window) and 100 < width <= 1100 and 100 < height <= 650, "Window is not small; aborting before test action"
        # This fixture sends no keyboard input: its save is gated by a file.
        # Keep the user's current app focused instead of requiring activation.
        evidence["foreground_during_test"] = user32.GetForegroundWindow()
        deadline = time.monotonic() + 10
        while not (folder / "worker-start.json").exists() and time.monotonic() < deadline:
            time.sleep(.05)
        worker_identity = json.loads((folder / "worker-start.json").read_text(encoding="utf-8"))
        worker_witness = ProcessWitness(worker_identity, python_image)
        assert not worker_witness.wait(0), "Worker exited before the save gate"
        (folder / "go").write_text("go", encoding="ascii")
        deadline = time.monotonic() + 20
        while not (folder / "result.json").exists() and time.monotonic() < deadline:
            time.sleep(.1)
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        evidence["save"] = result
        child_identity = json.loads((folder / "child-start.json").read_text(encoding="utf-8"))
        child_witness = ProcessWitness(child_identity, executable)
        assert child_witness.wait(0), "Captured first-save CLI must already have exited"
        assert result.get("code") == 0 and "error" not in result, result
        saved = json.loads(result["stdout"])
        assert saved["ok"] is True
        first = rpc(directory, "status")
        expected = original_forwards + [{"id": saved["id"], "local_port": 18763,
                                         "remote_port": 18763, "name": "Owned OFF fixture"}]
        assert first["forwards"] == expected and not first["running"], first
        assert all(value == "OFF" for value in first["states"].values()), first
        evidence["controller_pid_before_close"] = first["pid"]
        close_owned()
        after = rpc(directory, "status")
        assert after["pid"] == first["pid"], "Original controller did not survive window closure"
        evidence["controller_pid_after_close"] = after["pid"]
        evidence["foreground_after_close"] = user32.GetForegroundWindow()
        evidence["ok"] = True
    finally:
        (folder / "STOP").write_text("stop", encoding="ascii")
        closure_error = None
        try:
            close_owned()
        except Exception as error:
            closure_error = error
        # A disappearing HWND is not proof that its worker or a just-started CLI
        # exited. Cache/verify those identities and wait before controller RPC.
        if worker_witness is None and (folder / "worker-start.json").exists():
            worker_witness = ProcessWitness(json.loads((folder / "worker-start.json").read_text(encoding="utf-8")), python_image)
        if launched and worker_witness is None:
            raise RuntimeError(f"Worker identity unavailable; retained fixture {folder}")
        if worker_witness is not None and not worker_witness.wait(20):
            raise RuntimeError(f"Owned worker did not exit; retained fixture {folder}")
        if child_witness is None and (folder / "child-start.json").exists():
            child_witness = ProcessWitness(json.loads((folder / "child-start.json").read_text(encoding="utf-8")), executable)
        if child_witness is not None and not child_witness.wait(15):
            raise RuntimeError(f"Owned CLI did not exit; retained fixture {folder}")
        if (folder / "spawn-started").exists() and child_witness is None and not (folder / "cli-reaped").exists():
            raise RuntimeError(f"CLI spawn identity unavailable; retained fixture {folder}")
        if directory is not None and (directory / "endpoint.json").exists():
            rpc(directory, "shutdown")
            deadline = time.monotonic() + 5
            while (directory / "endpoint.json").exists() and time.monotonic() < deadline:
                time.sleep(.05)
            assert not (directory / "endpoint.json").exists(), "Owned controller did not shut down"
        for witness in (worker_witness, child_witness):
            if witness is not None:
                witness.close()
        if options.output:
            options.output.parent.mkdir(parents=True, exist_ok=True)
            options.output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        assert folder.parent == temp_parent and folder.name.startswith("native-window-save-")
        shutil.rmtree(folder)
        if closure_error:
            raise closure_error
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
