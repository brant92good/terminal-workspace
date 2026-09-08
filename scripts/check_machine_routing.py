"""Opt-in desktop check using two machine profiles and an existing SSH login.

The profiles intentionally reach the same physical endpoint: this checks
machine identity and window routing, not availability of a second server.
Only the temporary profile and windows created here are removed afterward.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/port-forward-tui'))
from port_forward_tui.machines import Catalog, machine_id
from port_forward_tui.forwarding import DATA_DIR, SSH, ssh_options
from port_forward_tui.background import exchange
from port_forward_tui.focus_settings import save_scope
from port_forward_tui.views import process_alive
from check_interactive import state, activate, chord, wait_for, is_active
from herdr_launcher import helper, live_records, view_directory
from configure import PORTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--machine', required=True, help='An existing machine with a working key-based SSH login')
    options = parser.parse_args()
    if not options.yes:
        parser.error('This test opens SSH sessions and moves Terminal windows; pass --yes to run it.')
    catalog = Catalog(DATA_DIR)
    primary = catalog.get(options.machine)
    if primary.ssh_port is not None or primary.ssh_config is not None:
        parser.error('Select a machine using its default SSH configuration, without an explicit port override.')
    resolved = subprocess.check_output([SSH, '-G', primary.target], text=True,
                                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
    ssh_port = int(next(line.split()[1] for line in resolved.splitlines() if line.startswith('port ')))
    key = machine_id(primary.target, ssh_port)
    if any(m.id == key for m in catalog.list()):
        parser.error('A profile for the temporary port override already exists; it will not be changed.')
    originals = {m.directory / 'forwards.json': (m.directory / 'forwards.json').read_bytes() for m in catalog.list()}
    settings = json.loads((ROOT / '.machine.json').read_text(encoding='utf-8-sig'))
    remote_client = settings.get('remote_client', 'ssh')
    preferences = primary.directory / 'ui-settings.json'
    original_scope = preferences.read_bytes() if preferences.exists() else None
    before = {t['window'] for t in state()['tabs']}
    created = set()
    secondary = None
    try:
        secondary = catalog.add(primary.target, 'Temporary routing verification', ssh_port)
        save_scope(primary.directory, 'all')
        save_scope(secondary.directory, 'all')
        windows = []
        for label, machine in [('A', primary), ('B', secondary)]:
            existing = before | created
            subprocess.Popen([str(ROOT / 'build/TerminalWorkspace.exe'), '--machine', machine.id])
            current = wait_for(lambda s: any(t['window'] not in existing for t in s['tabs']), f'machine {label} workspace opens')
            window = next(t['window'] for t in current['tabs'] if t['window'] not in existing)
            created.add(window)
            remote_dir = (view_directory(DATA_DIR, primary.target) if machine == primary and remote_client == 'herdr'
                          else DATA_DIR / 'ssh-views' / machine.id)
            current = wait_for(lambda s: any(t['window'] == window and t['title'].startswith('Ports | ') for t in s['tabs'])
                and any(r['window'] == window for r in live_records(remote_dir)), f'machine {label} remote and Ports views register')
            remote_ids = {r['runtime_id'] for r in live_records(remote_dir)}
            remote = next(t for t in current['tabs'] if t['window'] == window and t['runtime_id'] in remote_ids)
            ports = next(t for t in current['tabs'] if t['window'] == window and t['title'].startswith('Ports | '))
            windows.append((remote, ports))
        (ra, pa), (rb, pb) = windows
        for target, wrong, origin, letter, description in [
            (pa, pb, ra, 'P', 'A remote returns to A Ports despite newer B Ports'),
            (rb, ra, pb, 'R', 'B Ports returns to B remote despite newer A remote'),
            (pb, pa, rb, 'P', 'B remote returns to B Ports despite newer A Ports'),
            (ra, rb, pa, 'R', 'A Ports returns to A remote despite newer B remote'),
        ]:
            activate(target)
            activate(wrong)
            activate(origin)
            chord(letter)
            wait_for(lambda s, t=target: is_active(s, t), description)
        previous = {t['runtime_id'] for t in state()['tabs']}
        activate(rb)
        subprocess.run(['wt.exe', '-w', '0', 'new-tab', '-p', PORTS,
                        sys.executable, '-E', '-s', str(ROOT / 'apps/port-forward-tui/app.py'),
                        '--machine', primary.id], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        current = wait_for(lambda s: any(t['runtime_id'] not in previous and t['title'].startswith('Ports | ') for t in s['tabs']),
                           'another A Ports view opens')
        mixed = next(t for t in current['tabs'] if t['runtime_id'] not in previous and t['title'].startswith('Ports | '))
        if mixed['window'] not in before:
            created.add(mixed['window'])
        assert mixed['window'] == rb['window'], 'The mixed-machine view must be in B\'s Terminal window'
        activate(mixed)
        chord('R')
        wait_for(lambda s: is_active(s, ra), 'an explicitly selected A view returns to A remote')
        for path, original in originals.items():
            assert path.read_bytes() == original, 'An existing favorites file changed'
        print('PASS: two-profile machine routing; physical SSH endpoint shared for this test', flush=True)
    finally:
        if original_scope is None:
            preferences.unlink(missing_ok=True)
        else:
            preferences.write_bytes(original_scope)
        for window in created:
            subprocess.run(helper('CloseTestWindow', '-WindowHandle', window), timeout=12,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        if secondary:
            try:
                snapshot = exchange(secondary.directory, 'shutdown')
                deadline = time.monotonic() + 8
                while process_alive(snapshot['pid']) and time.monotonic() < deadline:
                    time.sleep(.1)
                if process_alive(snapshot['pid']):
                    raise RuntimeError('Temporary supervisor is still exiting; keep its folder for cleanup.')
            except FileNotFoundError:
                pass
            target = secondary.directory.resolve()
            assert target.parent == (DATA_DIR / 'machines').resolve() and target.name == key
            shutil.rmtree(target)


if __name__ == '__main__':
    main()
