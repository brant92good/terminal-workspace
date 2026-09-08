"""Desktop regression: switch applications while a real focus lookup is pending."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/port-forward-tui"))


def worker(app, gate):
    original_run = subprocess.run

    def wait_at_probe():
        gate.with_suffix(".ready").write_text("ready")
        deadline = time.monotonic() + 20
        while not gate.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("Desktop test did not release the probe")
            time.sleep(.05)

    def hold_probe(command, *args, **kwargs):
        if "-ProbeOnly" in command or ("-Mode" in command and command[command.index("-Mode") + 1] == "Probe"):
            wait_at_probe()
        return original_run(command, *args, **kwargs)

    subprocess.run = hold_probe
    if app == "ports":
        from port_forward_tui.ui import main
        from port_forward_tui import views as focus_module
        sys.argv = ["app.py", "--focus-existing"]
    else:
        from herdr_launcher import main
        import herdr_launcher as focus_module
        machine = json.loads((ROOT / ".machine.json").read_text())
        sys.argv = ["herdr_launcher.py", "--focus-existing", "--host", machine["ssh_host"], "--herdr", machine["herdr"]]
    original_native = focus_module.native_focus

    def hold_native_probe(command, *args, **kwargs):
        wait_at_probe()
        return original_native(command, *args, **kwargs)

    focus_module.native_focus = hold_native_probe
    raise SystemExit(main())


def check_handoff(app, target, machine):
    from check_interactive import state, wait_for
    from herdr_launcher import helper
    with tempfile.TemporaryDirectory(prefix="terminal-focus-check-") as folder:
        directory = Path(folder)
        gate = directory / "probe.release"
        before = {t["window"] for t in state()["tabs"]}
        other_app = None
        created = set()
        try:
            subprocess.Popen(["wt.exe", "-w", "new", "new-tab", "--",
                sys.executable, str(Path(__file__).resolve()), "--worker", app, str(gate)])
            deadline = time.monotonic() + 15
            while not gate.with_suffix(".ready").exists():
                if time.monotonic() >= deadline:
                    raise AssertionError("Focus launcher did not reach its actual probe")
                time.sleep(.05)
            current = state()
            created = {t["window"] for t in current["tabs"]} - before
            if len(created) != 1:
                raise AssertionError("Expected one temporary shortcut window")
            form_script = directory / "other-app.ps1"
            form_script.write_text("""param([string]$HandleFile)
Add-Type -AssemblyName System.Windows.Forms
$focusForm = New-Object System.Windows.Forms.Form
$focusForm.Text = 'Other app - Terminal focus regression'
$focusForm.Width = 440
$focusForm.Height = 140
$focusButton = New-Object System.Windows.Forms.Button
$focusButton.Text = 'Focus must stay here'
$focusButton.Dock = 'Fill'
$focusForm.Controls.Add($focusButton)
$focusForm.Add_Shown({
    $focusForm.Activate()
    $focusButton.Focus()
    [IO.File]::WriteAllText($HandleFile, $focusForm.Handle.ToInt64().ToString())
})
[System.Windows.Forms.Application]::Run($focusForm)
""", encoding="utf-8")
            handle_file = directory / "other-app.handle"
            other_app = subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(form_script), "-HandleFile", str(handle_file)],
                creationflags=subprocess.CREATE_NO_WINDOW)
            deadline = time.monotonic() + 12
            while not handle_file.exists():
                if other_app.poll() is not None or time.monotonic() >= deadline:
                    raise AssertionError("Non-Terminal test application did not open")
                time.sleep(.05)
            handle = int(handle_file.read_text())
            if state()["foreground"] != handle:
                subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                    "Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes; "
                    f"$testRoot = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]{handle}); "
                    "$testButton = $testRoot.FindFirst([System.Windows.Automation.TreeScope]::Descendants, "
                    "(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, "
                    "[System.Windows.Automation.ControlType]::Button))); $testButton.SetFocus()"],
                    check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            wait_for(lambda s: s["foreground"] == handle, f"{app}: another application has focus while lookup is paused")
            gate.write_text("continue")
            wait_for(lambda s: not any(t["window"] in created for t in s["tabs"]), f"{app}: lookup launcher exits")
            # Cover the detached helper's startup, UIA enumeration, and activation.
            for _ in range(8):
                current = state()
                if current["foreground"] != handle:
                    raise AssertionError(f"{app} stole foreground focus")
                if any(t["runtime_id"] == target["runtime_id"] and t["selected"] for t in current["tabs"]):
                    raise AssertionError(f"{app} changed the target tab after the user switched applications")
                time.sleep(.3)
            print(f"PASS: {app} leaves the other application and target tab unchanged after a delayed lookup", flush=True)
        finally:
            gate.write_text("continue")
            for window in created:
                if any(t["window"] == window for t in state()["tabs"]):
                    subprocess.run(helper("CloseTestWindow", "-WindowHandle", window), timeout=12,
                        creationflags=subprocess.CREATE_NO_WINDOW)
            if other_app:
                other_app.terminate()
                other_app.wait(timeout=5)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        worker(sys.argv[2], Path(sys.argv[3]))
    else:
        raise SystemExit("Run scripts/check_interactive.py --yes to use this desktop check")
