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
from port_forward_tui.forwarding import Store, DATA_DIR, validate_host
from port_forward_tui.machines import Catalog

HERDR = "{a9a0b421-7dd6-4425-9843-59b5f5d6c2d1}"
PORTS = "{5e483274-6f37-40d5-b42b-1eaef7f9da82}"
PWSH = "{574e775e-4f2a-5b96-ac1e-a2962a402336}"
LOCAL = "{f7c9cd21-fd21-429b-93ac-bd21e5ef8b11}"
SESSIONS = "{2ab64c44-ef5c-48d2-8f4d-678473aae748}"
SHELL_ACTION = 'User.TerminalWorkspace.LocalShell'
ACTIONS = {"herdr": "User.TerminalWorkspace.Herdr", "newHerdr": "User.TerminalWorkspace.NewHerdr",
           "ports": "User.TerminalWorkspace.Ports", "newPorts": "User.TerminalWorkspace.NewPorts"}
LOCAL_ACTIONS = {'local': 'User.TerminalWorkspace.Local', 'newLocal': 'User.TerminalWorkspace.NewLocal'}
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


def settings_bytes(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def parse_settings(contents):
    try:
        data = json.loads(contents)
    except json.JSONDecodeError:
        # PowerShell 7 is an installer prerequisite and includes Newtonsoft's
        # JSONC reader. Read stdin as data and keep date-like strings as strings.
        command = '''$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$reader = [Newtonsoft.Json.JsonTextReader]::new([System.IO.StringReader]::new([Console]::In.ReadToEnd()))
$reader.DateParseHandling = [Newtonsoft.Json.DateParseHandling]::None
while ($reader.Read() -and $reader.TokenType -eq [Newtonsoft.Json.JsonToken]::Comment) { }
$value = [Newtonsoft.Json.Linq.JToken]::ReadFrom($reader)
while ($reader.Read()) { if ($reader.TokenType -ne [Newtonsoft.Json.JsonToken]::Comment) { throw 'Unexpected content after settings' } }
$value.ToString([Newtonsoft.Json.Formatting]::None)
'''
        result = subprocess.run(["pwsh.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                                input=contents.decode("utf-8-sig").encode("utf-8"), capture_output=True, timeout=15,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise ValueError("Windows Terminal settings contain invalid JSON; the file was left unchanged")
        data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError("Windows Terminal settings must be a JSON object")
    return data


def write_json(path, data, backup=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path.with_name(path.name + ".before-workspace-" + stamp + ".bak").write_bytes(path.read_bytes())
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def render(original, shared, host, python, herdr, root=ROOT, integration_only=False,
           remote_client='herdr', local_herdr=False, shortcuts=None,
           session_picker=False, session_catalog=None, apply_default=False):
    data = deepcopy(original)
    if not integration_only:
        for key in PORTABLE:
            data.pop(key, None)
        data.update(shared.get("terminal", {}))
    if not integration_only or apply_default:
        data['defaultProfile'] = SESSIONS if session_picker else PWSH
    profiles = data.setdefault("profiles", {})
    if not integration_only:
        profiles["defaults"] = shared.get("profileDefaults", {})
    entries = profiles.setdefault("list", [])
    wsl = [p for p in entries if p.get("source") == "Microsoft.WSL"]
    if not integration_only and shared.get("compactMenu", True):
        keep = {PWSH, HERDR, PORTS} | ({LOCAL} if local_herdr else set()) | ({SESSIONS} if session_picker else set()) | {p["guid"] for p in wsl}
        for entry in entries:
            entry["hidden"] = entry.get("guid") not in keep
    commands = {
        "herdr": subprocess.list2cmdline([str(python), "-E", "-s", str(root / "scripts/herdr_launcher.py"),
                                         "--client", remote_client, "--herdr", str(herdr)]),
        "local": subprocess.list2cmdline([str(python), "-E", "-s", str(root / "scripts/herdr_launcher.py"),
                                         "--local", "--herdr", str(herdr)]),
        "ports": subprocess.list2cmdline([str(python), "-E", "-s", str(root / "apps/port-forward-tui/app.py")])
    }
    session_args = [str(python), '-E', '-s', str(root / 'apps/ssh-session-tui/app.py')]
    if session_catalog:
        session_args += ['--catalog', str(session_catalog)]
    commands['sessions'] = subprocess.list2cmdline(session_args)
    desired = [
        {"guid": PWSH, "name": "PowerShell", "source": "Windows.Terminal.PowershellCore", "hidden": False},
        {"guid": HERDR, "name": "Remote Herdr" if remote_client == 'herdr' else 'Remote SSH', "commandline": commands["herdr"], "icon": str(root / "build/herdr.ico") if remote_client == 'herdr' else '\U0001f5a5',
         "tabTitle": "Remote", "suppressApplicationTitle": False, "closeOnExit": "automatic", "hidden": False,
         "startingDirectory": "%USERPROFILE%"},
        {"guid": PORTS, "name": "Ports", "commandline": commands["ports"], "icon": "\U0001f50c",
         "tabTitle": "Ports", "suppressApplicationTitle": False, "closeOnExit": "automatic", "hidden": False,
         "startingDirectory": "%USERPROFILE%"}]
    if session_picker:
        desired.append({'guid': SESSIONS, 'name': 'SSH Sessions', 'commandline': commands['sessions'],
                        'icon': '\U0001f5a5', 'tabTitle': 'SSH Sessions', 'suppressApplicationTitle': False,
                        'closeOnExit': 'automatic', 'hidden': False, 'startingDirectory': '%USERPROFILE%'})
    else:
        for entry in entries:
            if entry.get('guid') == SESSIONS:
                entry['hidden'] = True
    if local_herdr:
        desired.append({'guid': LOCAL, 'name': 'Local Herdr', 'commandline': commands['local'],
                        'icon': str(root / 'build/herdr.ico'), 'tabTitle': 'Local Herdr',
                        'suppressApplicationTitle': False, 'closeOnExit': 'automatic', 'hidden': False,
                        'startingDirectory': '%USERPROFILE%'})
    else:
        for entry in entries:
            if entry.get('guid') == LOCAL:
                entry['hidden'] = True
    for profile in desired:
        existing = next((p for p in entries if p.get("guid") == profile["guid"]), None)
        if integration_only and profile["guid"] == PWSH:
            if existing is None and (session_picker or apply_default):
                entries.append({'guid': PWSH, 'name': 'PowerShell', 'commandline': 'pwsh.exe -NoLogo', 'hidden': False})
            continue
        if existing is None:
            entries.append(profile)
        else:
            existing.update(profile)
    if not integration_only:
        data["newTabMenu"] = [{"type": "remainingProfiles"}]
    actions = data.setdefault("actions", [])
    bindings = data.setdefault("keybindings", [])
    managed_ids = {a.get("id") for a in actions if isinstance(a.get("command"), dict)
                   and a["command"].get("profile") in (HERDR, PORTS, LOCAL, SESSIONS)} | set(ACTIONS.values()) | set(LOCAL_ACTIONS.values()) | {SHELL_ACTION}
    actions[:] = [a for a in actions if a.get("id") not in managed_ids]
    bindings[:] = [b for b in bindings if b.get("id") not in managed_ids]
    enabled = dict(ACTIONS, **(LOCAL_ACTIONS if local_herdr else {}))
    if session_picker:
        enabled['shell'] = SHELL_ACTION
    chosen_shortcuts = dict(shared['shortcuts'], **(shortcuts or {}))
    chosen_shortcuts.setdefault('local', 'ctrl+alt+l')
    chosen_shortcuts.setdefault('newLocal', 'ctrl+alt+shift+l')
    chosen_shortcuts.setdefault('shell', 'ctrl+alt+n')
    if len({chosen_shortcuts[k] for k in enabled}) != len(enabled):
        raise ValueError('Each workspace action needs a different shortcut.')
    for key, action_id in enabled.items():
        chord = chosen_shortcuts[key]
        if any(k.get("keys") == chord and k.get("id") not in enabled.values() for k in bindings):
            raise ValueError(f"Shortcut {chord} is already assigned to another action")
        is_herdr = key in ("herdr", "newHerdr")
        is_local = key in ('local', 'newLocal')
        command = {"action": "newTab", "profile": PWSH if key == 'shell' else LOCAL if is_local else HERDR if is_herdr else PORTS}
        if key in ("herdr", "ports", 'local'):
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


def install_mode(machine, requested):
    """Keep this computer's install choice on updates; preserve legacy defaults."""
    mode = machine.get("integration_only", False) if requested is None else requested
    if not isinstance(mode, bool):
        raise ValueError("integration_only in .machine.json must be true or false")
    return mode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-host")
    parser.add_argument("--herdr", type=Path)
    parser.add_argument('--remote-client', choices=('ssh', 'herdr'))
    picker_mode = parser.add_mutually_exclusive_group()
    picker_mode.add_argument('--session-picker', action='store_const', const=True, default=None, dest='session_picker', help='Make new tabs show the SSH machine picker; Ctrl+Alt+N opens PowerShell')
    picker_mode.add_argument('--no-session-picker', action='store_const', const=False, dest='session_picker')
    parser.add_argument('--session-catalog', type=Path, help='Metadata file in a private repo; keys stay with the existing SSH client')
    local_mode = parser.add_mutually_exclusive_group()
    local_mode.add_argument('--local-herdr', action='store_const', const=True, default=None, dest='local_herdr')
    local_mode.add_argument('--no-local-herdr', action='store_const', const=False, dest='local_herdr')
    parser.add_argument("--settings", type=Path, default=settings_path())
    parser.add_argument("--export", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--integration-only", dest="integration_only", action="store_const", const=True,
                      default=None, help="Add app profiles and shortcuts; keep existing Terminal preferences")
    mode.add_argument("--apply-shared-settings", dest="integration_only", action="store_const", const=False,
                      help="Also apply shared appearance, PowerShell default and menu preferences")
    options = parser.parse_args()
    shared_path = ROOT / "config/terminal.json"
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    original = settings_bytes(options.settings)
    if options.export and original is None:
        raise ValueError("Open Windows Terminal before exporting its settings")
    data = parse_settings(original) if original is not None else {}
    if options.export:
        write_json(shared_path, export_shared(data, shared))
        print("Exported portable Terminal preferences to config/terminal.json")
        return
    machine_path = ROOT / ".machine.json"
    machine = json.loads(machine_path.read_text()) if machine_path.exists() else {}
    integration_only = install_mode(machine, options.integration_only)
    host = options.ssh_host or machine.get("ssh_host")
    if host:
        validate_host(host)
    remote_client = options.remote_client or machine.get('remote_client') or ('herdr' if machine.get('herdr') and machine.get('ssh_host') else 'ssh')
    local_herdr = machine.get('local_herdr', False) if options.local_herdr is None else options.local_herdr
    session_picker = machine.get('session_picker', False) if options.session_picker is None else options.session_picker
    if not isinstance(session_picker, bool):
        raise ValueError('session_picker in .machine.json must be true or false')
    session_catalog = options.session_catalog or machine.get('session_catalog')
    if session_catalog is not None:
        if not isinstance(session_catalog, (str, Path)):
            raise ValueError('session_catalog must be a file path')
        session_catalog = str(Path(session_catalog).resolve())
    if session_picker and not (ROOT / 'apps/ssh-session-tui/app.py').is_file():
        raise ValueError('Initialize the SSH Sessions submodule before enabling the picker')
    if remote_client not in ('ssh', 'herdr') or not isinstance(local_herdr, bool):
        raise ValueError('Invalid remote_client or local_herdr in .machine.json')
    herdr = options.herdr or Path(machine.get("herdr", str(Path(os.environ["LOCALAPPDATA"]) / "Programs/Herdr/bin/herdr.exe")))
    if (remote_client == 'herdr' or local_herdr) and not herdr.is_file():
        raise ValueError("Install Herdr first or pass --herdr PATH")
    python = PORT_APP / ".venv/Scripts/python.exe"
    if not python.is_file():
        raise ValueError("Run install.ps1 to create the port app environment")
    if host:
        Catalog(DATA_DIR).add(host)
    updated = render(data, shared, host, python, herdr, root=ROOT, integration_only=integration_only,
                     remote_client=remote_client, local_herdr=local_herdr, shortcuts=machine.get('shortcuts'),
                     session_picker=session_picker, session_catalog=session_catalog, apply_default=options.session_picker is not None)
    if settings_bytes(options.settings) != original:
        raise ValueError("Terminal settings changed while preparing the update; retry")
    write_json(options.settings, updated, backup=True)
    machine.update({"ssh_host": host, "herdr": str(herdr), "integration_only": integration_only,
                    'remote_client': remote_client, 'local_herdr': local_herdr,
                    'session_picker': session_picker, 'session_catalog': session_catalog})
    write_json(machine_path, machine)
    if integration_only:
        preserved = 'appearance and menu' if options.session_picker is not None else 'appearance, default shell and menu'
        print('Remote and Ports profiles and shortcuts are ready. Kept existing Terminal ' + preserved + '.')
    else:
        print('Applied shared Terminal settings. Default new tabs open ' + ('SSH Sessions' if session_picker else 'PowerShell') + '; remote and Ports shortcuts are ready.')
    if session_picker:
        print('SSH Sessions is enabled. Ctrl+Alt+N opens local PowerShell; R/P/L workspace shortcuts keep their existing behavior.')
    if local_herdr:
        print("Local Herdr is enabled as the third workspace tab, with its own return and new-view shortcuts.")


if __name__ == "__main__":
    main()
