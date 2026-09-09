"""Explain which local Terminal setup steps need attention, without applying them."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/port-forward-tui'))
from port_forward_tui.diagnostics import app_checks, check, print_report, report


def workspace_checks(root=ROOT):
    checks = app_checks(root=root / 'apps/port-forward-tui')
    prerequisites = [('pwsh.exe', 'Install PowerShell 7 from Microsoft Store or winget.')]
    if (root / '.git').exists():
        prerequisites.append(('git.exe', 'Install Git for Windows to update this checkout.'))
    for name, fix in prerequisites:
        checks.append(check(name, bool(shutil.which(name)), name + ' is available.', fix))
    machine = {}
    path = root / '.machine.json'
    if path.exists():
        try:
            machine = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(machine, dict):
                raise ValueError('Expected object')
        except (OSError, ValueError):
            machine = {}
            checks.append(check('machine_settings', False, 'This checkout has unreadable machine settings.',
                                'Keep a backup of .machine.json and repair it before reinstalling.'))
    default_herdr = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Programs/Herdr/bin/herdr.exe'
    herdr = machine.get('herdr') or shutil.which('herdr.exe') or str(default_herdr)
    needs_herdr = machine.get('remote_client') == 'herdr' or machine.get('local_herdr', False) or (not machine.get('remote_client') and bool(machine.get('ssh_host')))
    checks.append(check('herdr', not needs_herdr or isinstance(herdr, str) and Path(herdr).is_file(), 'Herdr is available when enabled; ordinary SSH does not require it.',
                        'Install Herdr from https://herdr.dev, or pass install.ps1 -HerdrPath C:\\path\\herdr.exe.'))
    checks.append(check('workspace_installed', (root / 'build/TerminalWorkspace.exe').is_file(),
                        'This checkout has its workspace launcher.',
                        'Run .\\install.ps1; add machines when opening the app.'))
    if machine.get('session_picker'):
        checks.append(check('session_picker', (root / 'apps/ssh-session-tui/app.py').is_file(),
                            'The SSH session picker source is downloaded.',
                            'Run git submodule update --init --recursive, then reinstall.'))
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Print local checks as JSON for an agent')
    options = parser.parse_args()
    result = report(workspace_checks())
    print_report(result, options.json)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
