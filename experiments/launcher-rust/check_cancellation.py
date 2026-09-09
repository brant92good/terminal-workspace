"""Opt-in, isolated focus regression; uses a 440x140 mini app and small test tabs."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

from measure import CONTROL, FLAGS, PYTHON, ROOT, RUST
from check_interactive import state, wait_for
from herdr_launcher import helper
from port_forward_tui.views import focus_command


def wait_file(path, child=None):
    deadline = time.monotonic() + 15
    while not path.exists():
        if (child and child.poll() is not None) or time.monotonic() > deadline:
            raise AssertionError(f'Test did not create {path.name}')
        time.sleep(.05)


def check(folder, variant, mode):
    executable = folder / 'CancelBench.exe'
    compile_script = folder / 'compile.ps1'
    compile_script.write_text(r'''param([string]$Root,[string]$Output)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase,System.Web.Extensions,System.Windows.Forms,System.Drawing
$refs = @('System.dll','System.Core.dll','System.Windows.Forms.dll','System.Drawing.dll',
 [System.Windows.Automation.AutomationElement].Assembly.Location,
 [System.Windows.Automation.ControlType].Assembly.Location,[System.Windows.Threading.Dispatcher].Assembly.Location,
 [System.Web.Script.Serialization.JavaScriptSerializer].Assembly.Location)
Add-Type -Path @((Join-Path $Root 'scripts/TerminalViews.cs'),(Join-Path $Root 'scripts/BenchmarkSwitch.cs'),(Join-Path $Root 'experiments/launcher-rust/DesktopBench.cs'),(Join-Path $Root 'experiments/launcher-rust/CancelBench.cs')) -ReferencedAssemblies $refs -OutputAssembly $Output -OutputType WindowsApplication
''', encoding='utf-8')
    subprocess.run(['powershell.exe', '-NoProfile', '-File', str(compile_script), '-Root', str(ROOT), '-Output', str(executable)],
                   creationflags=FLAGS, check=True, timeout=20)
    native = focus_command()
    assert len(native) == 1, 'Build the native helper first'
    (folder / 'helper.txt').write_text(native[0], encoding='utf-8')
    (folder / 'ui-settings.json').write_text('{"focus_scope":"window"}', encoding='utf-8')
    views = folder / 'views'
    views.mkdir()
    stub = folder / 'stub.py'
    stub.write_text("import os,time\nfrom pathlib import Path\nimport sys\nPath(sys.argv[1]).write_text(str(os.getpid()))\nprint('Isolated focus test',flush=True)\ntime.sleep(60)\n", encoding='utf-8')
    owner_file = folder / 'owner.pid'
    nonce = uuid.uuid4().hex[:8]
    title = 'Ports | Cancel test | ' + nonce
    window_name = 'cancel-test-' + nonce
    created = set()
    watcher = None
    before = {t['window'] for t in state()['tabs']}
    try:
        subprocess.run(['wt.exe', '-w', window_name, '--size', '70,18', '--pos', '12,160',
            'new-tab', '--title', title, '--suppressApplicationTitle', *PYTHON, str(stub), str(owner_file),
            ';', 'new-tab', '--title', 'Cancel source ' + nonce, '--suppressApplicationTitle',
            *PYTHON, str(stub), str(folder / 'source.pid')], check=True, timeout=5)
        current = wait_for(lambda s: sum(t['window'] not in before and nonce in t['title'] for t in s['tabs']) == 2,
                           'small isolated cancellation tabs opened')
        created = {t['window'] for t in current['tabs'] if t['window'] not in before and nonce in t['title']}
        assert len(created) == 1
        window = next(iter(created))
        target = next(t for t in current['tabs'] if t['window'] == window and t['title'] == title)
        wait_file(owner_file)
        owner = int(owner_file.read_text())
        started = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command',
            f'(Get-Process -Id {owner}).StartTime.ToUniversalTime().Ticks'], creationflags=FLAGS, text=True, timeout=8)
        (views / 'target.json').write_text(json.dumps({'pid': owner, 'started': int(started), 'runtime_id': target['runtime_id'],
            'title': title, 'last_focus': 1}), encoding='utf-8')
        plan = folder / 'plan.json'
        plan.write_text(json.dumps({'mode': mode, 'views': str(views), 'settings': str(folder), 'helper': str(executable)}), encoding='utf-8')
        watcher = subprocess.Popen([str(executable), '--watch', str(window), target['runtime_id']], creationflags=FLAGS)
        wait_file(folder / 'watch.ready', watcher)
        command = [str(RUST)] if variant == 'rust' else CONTROL
        # This named test window is ours; no key is sent to the user's application.
        subprocess.run(['wt.exe', '-w', window_name, 'new-tab', *command, str(plan)], check=True, timeout=5)
        watcher.wait(timeout=25)
        result = (folder / 'result.txt').read_text(encoding='utf-8')
        assert watcher.returncode == 0, result
        print(f'{variant}/{mode}: {result}', flush=True)
        return {'variant': variant, 'mode': mode, 'result': result}
    finally:
        (folder / 'probe.release').write_text('continue', encoding='utf-8')
        try:
            for window in created:
                subprocess.run(helper('CloseTestWindow', '-WindowHandle', window), creationflags=FLAGS, timeout=12)
        finally:
            if watcher and watcher.poll() is None:
                watcher.terminate()
                watcher.wait(timeout=5)
            time.sleep(.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    if not options.yes:
        parser.error('--yes is required for small test windows and focus changes')
    results = []
    for variant in ('thin_python', 'rust'):
        for mode in ('ports', 'records'):
            with tempfile.TemporaryDirectory(prefix='launcher-cancel-') as name:
                results.append(check(Path(name), variant, mode))
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps({'checks': results}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
