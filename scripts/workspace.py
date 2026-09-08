"""Select one machine, then open its remote session, Ports, and optional local tab."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'apps/port-forward-tui'
sys.path.insert(0, str(APP))
from port_forward_tui.forwarding import DATA_DIR
from port_forward_tui.machines import Catalog
from port_forward_tui.window_context import choose_machine
from configure import HERDR, PORTS, LOCAL


def tab_command(window, machine, python, *, root=ROOT, data_dir=DATA_DIR, local_herdr=False, herdr=''):
    command = ['wt.exe', '-w', window, 'new-tab', '-p', PORTS, str(python), '-E', '-s',
               str(root / 'apps/port-forward-tui/app.py'), '--data-dir', str(data_dir), '--machine', machine]
    if local_herdr:
        command += [';', 'new-tab', '-p', LOCAL, str(python), '-E', '-s',
                    str(root / 'scripts/herdr_launcher.py'), '--local', '--herdr', herdr,
                    '--data-dir', str(data_dir)]
    return command + [';', 'focus-tab', '-t', '0']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window', required=True)
    parser.add_argument('--machine')
    parser.add_argument('--machines', action='store_true')
    parser.add_argument('--data-dir', type=Path, default=DATA_DIR)
    options = parser.parse_args()
    settings = json.loads((ROOT / '.machine.json').read_text(encoding='utf-8-sig'))
    catalog = Catalog(options.data_dir)
    machine = choose_machine(catalog, options.machine, picker=options.machines,
                             use_window=False, purpose='Choose a machine for this Terminal workspace')
    if not machine:
        return 0
    # This first tab becomes the remote session; append its companion tabs to
    # the explicitly named window, then leave this tab selected.
    subprocess.run(tab_command(options.window, machine.id, sys.executable,
                              data_dir=options.data_dir, local_herdr=settings.get('local_herdr', False),
                              herdr=settings.get('herdr', '')), check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    import herdr_launcher
    sys.argv = ['remote', '--machine', machine.id, '--data-dir', str(options.data_dir),
                '--client', settings.get('remote_client', 'ssh'), '--herdr', settings.get('herdr', '')]
    return herdr_launcher.main()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Workspace: {error}', file=sys.stderr)
        raise SystemExit(1)
