"""Opt-in small-window check of installed new-tab picker, SSH handoff and local shell."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from check_interactive import ROOT, small_test_window, state, wait_for
from configure import PWSH, SESSIONS, parse_settings, settings_path


DRIVER = r'''param([string]$Root,[long]$Window,[string]$Action,[string]$Value)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase
$refs = @('System.dll','System.Core.dll',[System.Windows.Automation.AutomationElement].Assembly.Location,
 [System.Windows.Automation.ControlType].Assembly.Location,[System.Windows.Threading.Dispatcher].Assembly.Location)
Add-Type -Path (Join-Path $Root 'tests/desktop/SessionPickerCheck.cs') -ReferencedAssemblies $refs
if ($Action -eq 'text') { [SessionPickerCheck]::Type($Window,$Value) }
elseif ($Action -eq 'has') { [SessionPickerCheck]::HasText($Window,$Value) }
else { [SessionPickerCheck]::Press($Window,$Action) }
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/session-picker-desktop.json')
    options = parser.parse_args()
    if not options.yes:
        parser.error('--yes is required for small test windows, key input and an SSH marker command')
    settings = parse_settings(settings_path().read_bytes())
    if settings.get('defaultProfile') != SESSIONS:
        parser.error('Enable the session picker as the default profile first')
    sys.path.insert(0, str(ROOT / 'apps/ssh-session-tui'))
    from ssh_sessions.catalog import Catalog
    from ssh_sessions.cli import default_directory
    machine = json.loads((ROOT / '.machine.json').read_text(encoding='utf-8-sig'))
    catalog = Catalog(machine['session_catalog'], default_directory() / 'device')
    snapshot = catalog.load()
    if len(snapshot.machines) != 1 or catalog.preferred(snapshot.machines[0]) is None:
        parser.error('This real SSH check needs exactly one machine with an explicit or single available route')
    before = state()
    with tempfile.TemporaryDirectory(prefix='session-picker-desktop-') as name:
        folder = Path(name)
        stub = folder / 'stub.py'
        stub.write_text("import time\nprint('Small selector test window',flush=True)\ntime.sleep(180)\n", encoding='utf-8')
        driver = folder / 'driver.ps1'
        driver.write_text(DRIVER, encoding='utf-8')
        with small_test_window([(PWSH, [sys.executable, '-E', '-s', str(stub)])]) as window:
            def act(action, value=''):
                return subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(driver),
                    '-Root', str(ROOT), '-Window', str(window), '-Action', action, '-Value', value],
                    capture_output=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=12, check=True).stdout.strip()
            def wait_text(text, message, timeout=25):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if act('has', text) == 'True':
                        print('PASS: ' + message, flush=True)
                        return
                    time.sleep(.2)
                raise AssertionError(message)
            act('newTab')
            wait_text('Choose a machine.', 'Ctrl+Shift+T opens the installed picker')
            act('enter')
            wait_text('Connecting to ', 'Enter hands the selected route to SSH')
            act('text', "printf 'SESSION_%s\\n' PICKER_REMOTE_OK")
            act('enter')
            wait_text('SESSION_PICKER_REMOTE_OK', 'real SSH session receives typed input and returns the marker')
            act('text', 'exit')
            act('enter')
            wait_text('Choose a machine.', 'ending SSH returns to the picker')
            act('local')
            wait_for(lambda s: len([t for t in s['tabs'] if t['window'] == window]) == 3, 'Ctrl+Alt+N opens a separate local tab')
            act('text', "Write-Output ('SESSION_' + $PSVersionTable.PSEdition + '_LOCAL_OK')")
            act('enter')
            wait_text('SESSION_Core_LOCAL_OK', 'local shortcut runs PowerShell Core')
    after = state()
    assert {t['runtime_id'] for t in after['tabs']} == {t['runtime_id'] for t in before['tabs']}, 'Original tabs changed'
    result = {'default_new_tab_picker': True, 'keyboard_ssh_handoff': True, 'remote_marker_received': True,
              'returns_to_picker': True, 'local_pwsh_hotkey': True, 'original_tabs_preserved': True,
              'test_window_initial_cells': [70, 18], 'date': time.strftime('%Y-%m-%d')}
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('PASS: owned test window closed; original tabs preserved', flush=True)


if __name__ == '__main__':
    main()
