"""Download and prepare a source bundle without changing the desktop setup."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    options = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    root = Path(tempfile.mkdtemp(prefix='workspace-install-')) / 'space 測試'
    print('Isolated bootstrap: ' + ascii(str(root)), flush=True)
    command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
               str(source / 'bootstrap.ps1'), '-InstallDir', str(root),
               '-Revision', options.revision, '-NoConfigure']
    subprocess.run(command, check=True, timeout=600)
    workspace = root / 'downloads' / ('terminal-workspace-' + options.revision)
    python = workspace / 'apps/port-forward-tui/.venv/Scripts/python.exe'
    assert python.is_file()
    assert not (root / 'current.json').exists()
    assert not (workspace / '.machine.json').exists()
    data = root / 'test-catalog.json'
    env = dict(os.environ, PYTHONHOME=str(root / 'missing'), PYTHONPATH=str(root / 'missing'))
    result = subprocess.check_output([str(python), '-E', '-s',
        str(workspace / 'apps/ssh-session-tui/app.py'), '--catalog', str(data),
        '--state-dir', str(root / 'device'), 'list', '--json'], env=env)
    assert json.loads(result)['machines'] == []
    saved = b'{"ssh_host":"workbox","integration_only":true}'
    (workspace / '.machine.json').write_bytes(saved)
    subprocess.run(command, check=True, timeout=600)
    assert (workspace / '.machine.json').read_bytes() == saved
    assert not (root / 'current.json').exists()
    print('PASS: pinned source downloads, managed Python, app startup, repeated setup, local preferences preserved.')


if __name__ == '__main__':
    main()
