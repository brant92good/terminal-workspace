"""Reproduce the experiment; --desktop --yes uses small test windows and temporary F9-F11 bindings."""
import argparse
from contextlib import contextmanager, ExitStack
import itertools
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'apps/port-forward-tui')]
RUST = HERE / 'target/release/launcher-experiment.exe'
PYTHON = [sys.executable, '-E', '-s']
CONTROL = [*PYTHON, str(HERE / 'python_control.py')]
FLAGS = subprocess.CREATE_NO_WINDOW


def summarize(values):
    return {'n': len(values), 'median_ms': round(statistics.median(values), 3),
            'mean_ms': round(statistics.mean(values), 3), 'min_ms': round(min(values), 3),
            'max_ms': round(max(values), 3), 'samples_ms': [round(x, 3) for x in values]}


def execute(command):
    return subprocess.run(command, capture_output=True, creationflags=FLAGS, timeout=15)


def fixture(folder, mode='ports'):
    views = folder / 'views'
    views.mkdir(exist_ok=True)
    plan = {'views': str(views), 'settings': str(folder), 'mode': mode, 'helper': 'unused-in-prepare'}
    path = folder / 'plan.json'
    path.write_text(json.dumps(plan), encoding='utf-8')
    return path, views


def contract_checks(folder):
    plan, views = fixture(folder)
    cases = 0
    def equivalent(expected_count=None, error=False):
        nonlocal cases
        results = [execute([*prefix, str(plan), '--prepare']) for prefix in (CONTROL, [str(RUST)])]
        if error:
            assert all(r.returncode == 2 for r in results), [r.stderr for r in results]
        else:
            assert all(r.returncode == 0 for r in results), [r.stderr for r in results]
            decoded = [json.loads(r.stdout) for r in results]
            assert decoded[0] == decoded[1], decoded
            if expected_count is not None:
                assert len(decoded[0]['payload']) == expected_count, decoded
        cases += 1
    equivalent(0)
    for i in range(8):
        (views / f'{i}.json').write_text(json.dumps({'pid': os.getpid(), 'title': f'Ports | Demo 開發 | {i}',
            'last_focus': i, 'started': 12345, 'runtime_id': f'1.2.{i}'}), encoding='utf-8')
    equivalent(8)
    (views / 'broken.json').write_text('{broken', encoding='utf-8')
    (views / 'invalid.json').write_text(json.dumps({'pid': os.getpid(), 'title': 'Unrelated'}), encoding='utf-8')
    equivalent(8)
    (folder / 'ui-settings.json').write_text('{"focus_scope":"window"}', encoding='utf-8')
    equivalent(8)
    (folder / 'ui-settings.json').write_text('{"focus_scope":"wrong"}', encoding='utf-8')
    equivalent(error=True)
    (folder / 'ui-settings.json').write_text('{broken', encoding='utf-8')
    equivalent(error=True)
    (folder / 'ui-settings.json').unlink()
    (views / 'invalid.json').unlink()
    data = json.loads(plan.read_text())
    data['mode'] = 'records'
    plan.write_text(json.dumps(data), encoding='utf-8')
    equivalent(8)
    # A truly exited PID, rather than a guessed/reusable "dead" PID.
    child = subprocess.Popen([*PYTHON, '-c', 'pass'], creationflags=FLAGS)
    child.wait(timeout=10)
    for prefix in (CONTROL, [str(RUST)]):
        dead = views / 'dead.json'
        dead.write_text(json.dumps({'pid': child.pid, 'title': 'Ports | dead'}))
        result = execute([*prefix, str(plan), '--prepare'])
        assert result.returncode == 0 and len(json.loads(result.stdout)['payload']) == 8
        assert not dead.exists()
    cases += 1
    data['mode'] = 'ports'
    plan.write_text(json.dumps(data), encoding='utf-8')
    return cases, plan


def headless(folder):
    checks, plan = contract_checks(folder)
    commands = {
        'python_empty_process': [*PYTHON, '-c', 'pass'],
        'rust_empty_process': [str(RUST), '--noop'],
        'python_read_8_views': [*CONTROL, str(plan), '--prepare'],
        'rust_read_8_views': [str(RUST), str(plan), '--prepare'],
        'python_import_focus': [*PYTHON, '-c',
            'import sys; sys.path.insert(0, sys.argv[1]); import port_forward_tui.views', str(ROOT / 'apps/port-forward-tui')],
        'python_import_all_machines_ui': [*PYTHON, '-c',
            'import sys; sys.path.insert(0, sys.argv[1]); import port_forward_tui.all_machines_ui', str(ROOT / 'apps/port-forward-tui')],
    }
    for command in commands.values():
        result = execute(command)
        assert result.returncode == 0, result.stderr
    results = {name: [] for name in commands}
    randomizer = random.Random(923)
    for _ in range(40):
        names = list(commands)
        randomizer.shuffle(names)
        for name in names:
            started = time.perf_counter()
            result = execute(commands[name])
            elapsed = (time.perf_counter() - started) * 1000
            assert result.returncode == 0, result.stderr
            results[name].append(elapsed)
    return {'contract_checks_passed': checks, 'method': '40 shuffled warm runs per case; process creation through exit; captured stdout',
            'results': {name: summarize(values) for name, values in results.items()}}


@contextmanager
def test_shortcuts(app, commands):
    """Install all variants once; never reload settings between timed trials."""
    from configure import ACTIONS, parse_settings, settings_path
    from profile_focus import encode, write_settings
    path = settings_path()
    original = path.read_bytes()
    data = parse_settings(original.decode('utf-8-sig'))
    base = next(a['command'] for a in data['actions'] if a.get('id') == ACTIONS[app])
    ids = set()
    bindings = {}
    for index, (name, commandline) in enumerate(commands.items()):
        key = f'ctrl+alt+f{index+9}'
        if any(b.get('keys') == key for b in data.get('keybindings', [])):
            raise ValueError(f'{key} is already assigned; refusing to replace it')
        identifier = 'User.TerminalWorkspace.Benchmark.' + uuid.uuid4().hex
        ids.add(identifier)
        data['actions'].append({'id': identifier, 'command': {**base, 'commandline': commandline}})
        data.setdefault('keybindings', []).append({'id': identifier, 'keys': key})
        bindings[name] = 0x78 + index  # F9, F10, F11
    changed = encode(data)
    write_settings(path, changed)
    try:
        time.sleep(1)
        yield bindings
    finally:
        current = path.read_bytes()
        if current == changed:
            write_settings(path, original)
        else:
            data = parse_settings(current.decode('utf-8-sig'))
            data['actions'] = [a for a in data['actions'] if a.get('id') not in ids]
            data['keybindings'] = [b for b in data['keybindings'] if b.get('id') not in ids]
            write_settings(path, encode(data))


MEASURE = r'''param([string]$Root,[string]$Target,[string]$Source,[long]$Window,[byte]$Shortcut,[switch]$Describe)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase,System.Web.Extensions
$refs = @('System.dll','System.Core.dll',[System.Windows.Automation.AutomationElement].Assembly.Location,
 [System.Windows.Automation.ControlType].Assembly.Location,[System.Windows.Threading.Dispatcher].Assembly.Location,
 [System.Web.Script.Serialization.JavaScriptSerializer].Assembly.Location)
Add-Type -Path @((Join-Path $Root 'scripts/TerminalViews.cs'),(Join-Path $Root 'experiments/launcher-rust/DesktopBench.cs')) -ReferencedAssemblies $refs
if ($Describe) {
    [DesktopBench]::Describe($Window)
} else { [DesktopBench]::Run($Target,$Source,$Window,$Shortcut) }
'''


def desktop(app, folder, debug=False, debug_variant='rust'):
    from check_interactive import small_test_window, state, wait_for
    from configure import HERDR, PORTS, ACTIONS, parse_settings, settings_path
    from herdr_launcher import live_records, view_directory
    from port_forward_tui.machines import Catalog
    from port_forward_tui.forwarding import DATA_DIR
    from port_forward_tui.views import focus_command
    from port_forward_tui.focus_settings import save_scope
    machines = Catalog(DATA_DIR).list()
    if len(machines) != 1:
        raise ValueError('This language-isolation experiment requires exactly one saved machine; it does not modify the catalog.')
    original_machine = machines[0]
    # Isolated records make every return candidate a test-owned tab. Even the
    # global search cannot select one of the user's existing Herdr/Ports views.
    test_data = folder / 'data'
    machine = Catalog(test_data).add(original_machine.target, name='Launcher benchmark',
        ssh_port=original_machine.ssh_port, ssh_config=original_machine.ssh_config)
    settings = json.loads((ROOT / '.machine.json').read_text(encoding='utf-8-sig'))
    client = 'ssh' if machine.ssh_port or machine.ssh_config else settings.get('remote_client', 'ssh')
    records = view_directory(test_data, machine.target) if client == 'herdr' else test_data / 'ssh-views' / machine.id
    native = focus_command()
    if len(native) != 1:
        raise ValueError('Build the native helper before measuring')
    plan = folder / 'desktop-plan.json'
    plan.write_text(json.dumps({'views': str(machine.directory / 'views' if app == 'ports' else records),
        'settings': str(machine.directory), 'mode': 'ports' if app == 'ports' else 'records', 'helper': native[0]}))
    if debug:
        data = json.loads(plan.read_text())
        data['trace'] = str(ROOT / 'artifacts/language-benchmark/debug-native.json')
        plan.write_text(json.dumps(data))
    data = parse_settings(settings_path().read_text(encoding='utf-8-sig'))
    installed = next(a['command']['commandline'] for a in data['actions'] if a.get('id') == ACTIONS[app])
    if '--data-dir' in installed:
        raise ValueError('Expected normal installed command without a data-dir override')
    installed += ' --data-dir ' + subprocess.list2cmdline([str(test_data)])
    commands = {'installed_python': installed, 'thin_python': subprocess.list2cmdline([*CONTROL, str(plan)]),
                'rust': subprocess.list2cmdline([str(RUST), str(plan)])}
    if debug and app == 'herdr':
        commands['installed_python'] += ' --trace-dir ' + subprocess.list2cmdline([str(ROOT / 'artifacts/language-benchmark/installed-traces')])
    preferences = machine.directory / 'ui-settings.json'
    original = preferences.read_bytes() if preferences.exists() else None
    created = set()
    report = {'app': app, 'saved_machine_count': 1, 'remote_client': client, 'blocks': [],
              'focus_scope': 'window', 'isolated_data': True, 'test_window_pixels': [700, 400]}
    with test_shortcuts(app, commands) as bindings, ExitStack() as windows:
        try:
            save_scope(machine.directory, 'window')
            view_commands = {
                PORTS: [*PYTHON, str(ROOT / 'apps/port-forward-tui/app.py'), '--data-dir', str(test_data), '--machine', machine.id],
                HERDR: [*PYTHON, str(ROOT / 'scripts/herdr_launcher.py'), '--data-dir', str(test_data), '--machine', machine.id, '--client', client],
            }
            if settings.get('herdr'):
                view_commands[HERDR] += ['--herdr', settings['herdr']]
            profiles = (PORTS, HERDR) if app == 'ports' else (HERDR, PORTS)
            window = windows.enter_context(small_test_window([(profile, view_commands[profile]) for profile in profiles]))
            created = {window}
            current = wait_for(lambda s: any(t['window'] in created and t['title'].startswith('Ports | ') for t in s['tabs'])
                and any(r['window'] in created for r in live_records(records)), 'both experiment views ready')
            target_ids = {r['runtime_id'] for r in live_records(records) if r['window'] in created}
            initial_owners = [r['pid'] for r in live_records(records) if r['window'] in created]
            target = next(t for t in current['tabs'] if t['window'] in created and
                          (t['title'].startswith('Ports | ') if app == 'ports' else t['runtime_id'] in target_ids))
            source = next(t for t in current['tabs'] if t['window'] in created and t != target)
            report['terminal_windows'] = len({t['window'] for t in current['tabs']})
            report['terminal_tabs'] = len(current['tabs'])
            script = folder / 'measure.ps1'
            script.write_text(MEASURE, encoding='utf-8')
            orders = list(itertools.permutations(commands))
            random.Random(923).shuffle(orders)
            if debug:
                orders = [(debug_variant,)]
            for block, order in enumerate(orders):
                for name in order:
                    if app == 'herdr':
                        found = live_records(records)
                        if not found:
                            from port_forward_tui.views import process_alive
                            description = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                                '-Root', str(ROOT), '-Window', str(target['window']), '-Target', target['runtime_id'], '-Describe'], capture_output=True,
                                encoding='utf-8', errors='replace', creationflags=FLAGS, timeout=12)
                            diagnostic = {'owners_alive': {p: process_alive(p) for p in initial_owners},
                                'tracker_log': (records/'tracker.log').read_text(encoding='utf-8', errors='replace'),
                                'screen': description.stdout}
                            (ROOT/'artifacts/language-benchmark/tracker-failure.json').write_text(json.dumps(diagnostic, indent=2), encoding='utf-8')
                            raise RuntimeError('Herdr view registration disappeared; see artifacts/language-benchmark/tracker-failure.json')
                    if debug:
                        trace_path = ROOT / 'artifacts/language-benchmark/debug-native.json'
                        trace_path.unlink(missing_ok=True)
                        prepared = [execute([*prefix, str(plan), '--prepare']) for prefix in (CONTROL, [str(RUST)])]
                        decoded = [json.loads(p.stdout) for p in prepared]
                        print('Prepared records:', [len(d['payload']) for d in decoded], 'equal:', decoded[0] == decoded[1], flush=True)
                    measured = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                        '-Root', str(ROOT), '-Target', target['runtime_id'], '-Source', source['runtime_id'],
                        '-Window', str(target['window']),
                        '-Shortcut', str(bindings[name])], capture_output=True, encoding='utf-8',
                        errors='replace', creationflags=FLAGS, timeout=40)
                    if measured.returncode:
                        description = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                            '-Root', str(ROOT), '-Window', str(target['window']), '-Target', target['runtime_id'], '-Describe'], capture_output=True,
                            encoding='utf-8', errors='replace', creationflags=FLAGS, timeout=12)
                        (ROOT / 'artifacts/language-benchmark/failure-text.json').write_text(description.stdout, encoding='utf-8')
                        current = state()
                        print('Failure state:', json.dumps({'foreground': current['foreground'],
                            'target': target['runtime_id'], 'source': source['runtime_id'],
                            'tabs': [{k: t[k] for k in ('runtime_id', 'window', 'selected')} for t in current['tabs']]}))
                        raise RuntimeError(measured.stderr)
                    samples = [item['milliseconds'] for item in json.loads(measured.stdout)]
                    report['blocks'].append({'block': block, 'variant': name, 'samples_ms': samples})
                    print(f'{app} block {block + 1}/6 {name}: {samples}', flush=True)
            report['results'] = {name: summarize([x for block in report['blocks'] if block['variant'] == name for x in block['samples_ms']])
                                 for name in commands if any(b['variant'] == name for b in report['blocks'])}
            return report
        finally:
            if original is None:
                preferences.unlink(missing_ok=True)
            else:
                preferences.write_bytes(original)
            windows.close()
            # Closing a Terminal window is asynchronous. Its tracker must release
            # the log file before TemporaryDirectory removes this Windows folder.
            deadline = time.monotonic() + 8
            while live_records(records) and time.monotonic() < deadline:
                time.sleep(.1)
            time.sleep(.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desktop', choices=('ports', 'herdr'))
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--debug', action='store_true', help='One Rust block with native tracing; not a headline measurement')
    parser.add_argument('--debug-variant', choices=('rust','thin_python','installed_python'), default='rust')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.desktop and not args.yes:
        parser.error('--desktop requires --yes to permit temporary tabs and keyboard input')
    if not RUST.is_file():
        parser.error('Build with cargo build --release --locked first')
    with tempfile.TemporaryDirectory(prefix='launcher-language-') as name:
        report = desktop(args.desktop, Path(name), args.debug, args.debug_variant) if args.desktop else headless(Path(name))
    report['python'] = sys.version.split()[0]
    report['rust'] = subprocess.check_output(['rustc', '--version'], text=True).strip()
    report['date'] = time.strftime('%Y-%m-%d')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report.get('results', report), indent=2))


if __name__ == '__main__':
    main()
