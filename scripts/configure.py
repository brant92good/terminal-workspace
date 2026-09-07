"""Render portable Terminal preferences using this machine's app paths."""
import argparse
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PORT_APP = ROOT / "apps/port-forward-tui"
sys.path.insert(0, str(PORT_APP))
from forwarding import Store, DATA_DIR, validate_host

HERDR = "{a9a0b421-7dd6-4425-9843-59b5f5d6c2d1}"
PORTS = "{5e483274-6f37-40d5-b42b-1eaef7f9da82}"
PWSH = "{574e775e-4f2a-5b96-ac1e-a2962a402336}"
ACTIONS = {"herdr": "User.TerminalWorkspace.Herdr", "newHerdr": "User.TerminalWorkspace.NewHerdr",
           "ports": "User.TerminalWorkspace.Ports", "newPorts": "User.TerminalWorkspace.NewPorts"}
# Export presentation preferences, never shell commands, addresses, or paths.
PORTABLE = {"copyFormatting", "copyOnSelect", "schemes", "themes", "theme", "tabWidthMode",
            "alwaysShowTabs", "showTabsInTitlebar", "useAcrylicInTabRow", "confirmCloseAllTabs",
            "initialRows", "initialCols", "launchMode", "windowingBehavior", "language",
            "focusFollowMouse", "wordDelimiters", "trimBlockSelection", "trimPaste",
            "snapToGridOnResize", "newTabPosition"}
PORTABLE_PROFILE = {"font", "colorScheme", "useAcrylic", "opacity", "padding", "cursorShape",
                    "cursorColor", "antialiasingMode", "historySize", "scrollbarState", "bellStyle"}


def settings_path():
    local = Path(os.environ["LOCALAPPDATA"])
    paths = [local / "Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json",
             local / "Microsoft/Windows Terminal/settings.json"]
    return next((p for p in paths if p.exists()), paths[0])


def write_json(path, data, backup=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path.with_name(path.name + ".before-workspace-" + stamp + ".bak").write_bytes(path.read_bytes())
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def render(original, shared, host, python, herdr, root=ROOT):
    data = deepcopy(original)
    data.update(shared.get("terminal", {}))
    data["defaultProfile"] = PWSH
    profiles = data.setdefault("profiles", {})
    profiles["defaults"] = shared.get("profileDefaults", {})
    entries = profiles.setdefault("list", [])
    wsl = [p for p in entries if p.get("source") == "Microsoft.WSL"]
    if shared.get("compactMenu", True):
        keep = {PWSH, HERDR, PORTS} | {p["guid"] for p in wsl}
        for entry in entries:
            entry["hidden"] = entry.get("guid") not in keep
    commands = {
        "herdr": subprocess.list2cmdline([str(python), str(root / "scripts/herdr_launcher.py"),
                                         "--host", host, "--herdr", str(herdr)]),
        "ports": subprocess.list2cmdline([str(python), str(root / "apps/port-forward-tui/app.py")])
    }
    desired = [
        {"guid": PWSH, "name": "PowerShell", "source": "Windows.Terminal.PowershellCore", "hidden": False},
        {"guid": HERDR, "name": "Herdr", "commandline": commands["herdr"], "icon": str(root / "build/herdr.ico"),
         "tabTitle": "Herdr", "suppressApplicationTitle": False, "closeOnExit": "automatic", "hidden": False,
         "startingDirectory": "%USERPROFILE%"},
        {"guid": PORTS, "name": "Ports", "commandline": commands["ports"], "icon": "\U0001f50c",
         "tabTitle": "Ports", "suppressApplicationTitle": False, "closeOnExit": "automatic", "hidden": False,
         "startingDirectory": "%USERPROFILE%"}]
    for profile in desired:
        existing = next((p for p in entries if p.get("guid") == profile["guid"]), None)
        if existing is None:
            entries.append(profile)
        else:
            existing.update(profile)
    data["newTabMenu"] = [{"type": "remainingProfiles"}]
    actions = data.setdefault("actions", [])
    bindings = data.setdefault("keybindings", [])
    managed_ids = {a.get("id") for a in actions if isinstance(a.get("command"), dict)
                   and a["command"].get("profile") in (HERDR, PORTS)} | set(ACTIONS.values())
    actions[:] = [a for a in actions if a.get("id") not in managed_ids]
    bindings[:] = [b for b in bindings if b.get("id") not in managed_ids]
    for key, action_id in ACTIONS.items():
        chord = shared["shortcuts"][key]
        if any(k.get("keys") == chord and k.get("id") not in ACTIONS.values() for k in bindings):
            raise ValueError(f"Shortcut {chord} is already assigned to another action")
        is_herdr = key in ("herdr", "newHerdr")
        command = {"action": "newTab", "profile": HERDR if is_herdr else PORTS}
        if key in ("herdr", "ports"):
            command["commandline"] = commands[key] + " --focus-existing"
        actions[:] = [a for a in actions if a.get("id") != action_id]
        actions.append({"id": action_id, "command": command})
        bindings[:] = [k for k in bindings if k.get("id") != action_id]
        bindings.append({"id": action_id, "keys": chord})
    return data


def export_shared(data, shared):
    result = deepcopy(shared)
    result["terminal"] = {k: v for k, v in data.items() if k in PORTABLE}
    result["profileDefaults"] = {k: v for k, v in data.get("profiles", {}).get("defaults", {}).items()
                                 if k in PORTABLE_PROFILE}
    for key, action_id in ACTIONS.items():
        binding = next((b for b in data.get("keybindings", []) if b.get("id") == action_id), None)
        if binding:
            result["shortcuts"][key] = binding["keys"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-host")
    parser.add_argument("--herdr", type=Path)
    parser.add_argument("--settings", type=Path, default=settings_path())
    parser.add_argument("--export", action="store_true")
    options = parser.parse_args()
    shared_path = ROOT / "config/terminal.json"
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    original = options.settings.read_bytes()
    data = json.loads(original)
    if options.export:
        write_json(shared_path, export_shared(data, shared))
        print("Exported portable Terminal preferences to config/terminal.json")
        return
    machine_path = ROOT / ".machine.json"
    machine = json.loads(machine_path.read_text()) if machine_path.exists() else {}
    host = options.ssh_host or machine.get("ssh_host")
    validate_host(host)
    herdr = options.herdr or Path(machine.get("herdr", str(Path(os.environ["LOCALAPPDATA"]) / "Programs/Herdr/bin/herdr.exe")))
    if not herdr.is_file():
        raise ValueError("Install Herdr first or pass --herdr PATH")
    python = PORT_APP / ".venv/Scripts/python.exe"
    if not python.is_file():
        raise ValueError("Run install.ps1 to create the port app environment")
    store = Store(DATA_DIR)
    store.load()
    if store.host != host:
        from background import exchange
        try:
            running = exchange(DATA_DIR, "status")
        except (OSError, ValueError):
            running = None
        if running:
            raise ValueError("Stop the port supervisor before changing SSH targets")
        store.host = host
        store.save(store.forwards)
    updated = render(data, shared, host, python, herdr)
    if options.settings.read_bytes() != original:
        raise ValueError("Terminal settings changed while preparing the update; retry")
    write_json(options.settings, updated, backup=True)
    write_json(machine_path, {"ssh_host": host, "herdr": str(herdr)})
    print("Applied shared Terminal settings. PowerShell is default; Herdr and Ports shortcuts are ready.")


if __name__ == "__main__":
    main()
