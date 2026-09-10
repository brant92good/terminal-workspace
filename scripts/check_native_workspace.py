"""Opt-in, owned small-window qualification of native workspace composition/focus.

Uses extracted release bytes, two .invalid catalog entries and a compiled Herdr
stand-in. Never edits installed profiles, pins, SSH files or production catalogs.
This measures programmatic routing, not physical hotkeys or taskbar pin clicks.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from check_native_window_persistence import ProcessWitness, receipt, rpc, NO_WINDOW, PWSH


def current_identity():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    return ProcessWitness.identity(os.getpid(), kernel.GetCurrentProcess())


def parent_pid(pid):
    class Entry(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD),
                    ('pid', wintypes.DWORD), ('heap', ctypes.c_size_t),
                    ('module', wintypes.DWORD), ('threads', wintypes.DWORD),
                    ('parent', wintypes.DWORD), ('priority', wintypes.LONG),
                    ('flags', wintypes.DWORD), ('name', wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        available = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while available:
            if entry.pid == pid:
                return entry.parent
            available = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        raise RuntimeError('Owned parent exited before identity capture')
    finally:
        kernel.CloseHandle(snapshot)


def live_identity(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000 | 0x100000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ProcessWitness.identity(pid, handle)
    finally:
        kernel.CloseHandle(handle)


def json_read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def wait_for(check, label, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.05)
    raise TimeoutError(label)


def pending_requests(control, handled):
    return [path for path in sorted(control.glob('request-*.json'))
            if re.fullmatch(r'request-[0-9a-f]{32}\.json', path.name)
            and path.name not in handled]


def standin(folder, argv):
    """Runs only behind the fixture's compiled Herdr executable."""
    wrapper = parent_pid(os.getpid())
    owner = parent_pid(wrapper)
    control = folder / 'workers' / str(os.getpid())
    control.mkdir(parents=True)
    details = dict(worker=current_identity(), wrapper=live_identity(wrapper),
                   owner=live_identity(owner), argv=argv,
                   conda=os.environ.get('CONDA_PREFIX'),
                   herdr_context={k: v for k, v in os.environ.items()
                                  if k in ('HERDR_ENV', 'HERDR_PANE_ID')})
    receipt(control, 'ready.json', details)
    deadline = time.monotonic() + 240
    handled = set()
    while not (folder / 'STOP').exists() and time.monotonic() < deadline:
        for request in pending_requests(control, handled):
            handled.add(request.name)
            data = json_read(request)
            executable = folder / 'bin' / data['executable']
            assert data['executable'] in ('ports.exe', 'terminal-workspace.exe')
            args = [str(executable), *data['args']]
            started = time.perf_counter()
            (control/(request.stem+'-spawn-started')).write_text('starting',encoding='ascii')
            child = subprocess.Popen(args)
            result = {'argv': args}
            try:
                receipt(control, request.stem + '-child.json',
                        ProcessWitness.identity(child.pid, int(child._handle), executable))
                try:
                    result['code'] = child.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    result['error'] = 'Return command opened a session instead of finding its view'
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=3)
                receipt(control,request.stem+'-reaped.json',{'pid':child.pid})
            result['milliseconds'] = (time.perf_counter() - started) * 1000
            receipt(control, request.stem + '-result.json', result)
        time.sleep(.05)
    receipt(control, 'finished.json', {'pid': os.getpid()})


def bootstrap(folder, token):
    spec = json_read(folder / (token + '.json'))
    control = folder / token
    control.mkdir()
    receipt(control, 'worker.json', current_identity())
    deadline = time.monotonic() + 30
    while not (control / 'go').exists():
        if (folder / 'STOP').exists() or time.monotonic() > deadline:
            return
        time.sleep(.05)
    if (folder / 'STOP').exists():
        return
    environment = dict(os.environ, CONDA_PREFIX='owned developer environment',
                       HERDR_ENV='owned stale pane', HERDR_PANE_ID='owned stale pane')
    (control/'spawn-started').write_text('starting',encoding='ascii')
    child = subprocess.Popen(spec['argv'], env=environment)
    try:
        receipt(control, 'child.json', ProcessWitness.identity(child.pid, int(child._handle), spec['argv'][0]))
        code = child.wait(timeout=240)
        receipt(control, 'finished.json', {'code': code})
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)
        receipt(control,'child-reaped.json',{'pid':child.pid})


STANDIN = r'''
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using System.Runtime.InteropServices;
public static class FixtureGuard {
    [StructLayout(LayoutKind.Sequential)] public struct Rect { public int left, top, right, bottom; }
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out Rect r);
    [DllImport("user32.dll")] static extern bool IsZoomed(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    public static void Small(long h) {
        Rect r;
        if (!GetWindowRect(new IntPtr(h), out r) || IsZoomed(new IntPtr(h)) ||
            r.right-r.left <=100 || r.right-r.left >1100 || r.bottom-r.top<=100 || r.bottom-r.top>650)
            throw new InvalidOperationException("Owned window is not small and normal");
    }
}
public static class HerdrFixture {
    static string Quote(string v) {
        return "\"" + Regex.Replace(v, "(\\\\*)\"", "$1$1\\\"") +
            new string('\\', v.Reverse().TakeWhile(c=>c=='\\').Count()) + "\"";
    }
    public static int Main(string[] args) {
        string root=AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        var spec=new JavaScriptSerializer().Deserialize<System.Collections.Generic.Dictionary<string,string>>(
            File.ReadAllText(Path.Combine(root,"fixture-runtime.json")));
        using(var child=Process.Start(new ProcessStartInfo {
            FileName=spec["python"], UseShellExecute=false,
            Arguments=String.Join(" ",new[]{"-E","-s",Path.Combine(root,"check_native_workspace.py"),"--standin",root,"--"}.Concat(args).Select(Quote))
        })) { child.WaitForExit(); return child.ExitCode; }
    }
}
'''

BRIDGE = r'''param([string]$Root,[string]$Mode,[long]$Window,[string]$Runtime,[long]$Origin,[string]$OriginRuntime)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
[void][Reflection.Assembly]::LoadFrom((Join-Path $Root 'HerdrFixture.exe'))
[void][Reflection.Assembly]::LoadFrom((Join-Path $Root 'bin\TerminalViews.exe'))
$allowed=[IO.File]::ReadAllText((Join-Path $Root 'allowed.json')) | ConvertFrom-Json
$tabs=@([TerminalViews]::Tabs())
foreach($entry in $allowed) {
  if(@($tabs | Where-Object window -eq $entry.window).Count -gt 0) { [FixtureGuard]::Small([long]$entry.window) }
  foreach($tab in @($tabs | Where-Object window -eq $entry.window)) {
    if($entry.tabs -cnotcontains $tab.runtime_id) { throw 'Unknown tab in owned window; refusing action.' }
  }
}
if($Mode -eq 'check') {
  if([FixtureGuard]::GetForegroundWindow().ToInt64() -ne $Origin -or @($tabs | Where-Object { $_.window -eq $Origin -and $_.runtime_id -ceq $OriginRuntime -and $_.selected }).Count -ne 1) { throw 'Origin changed before command gate' }
} elseif($Mode -eq 'identity') {
  [void][Reflection.Assembly]::LoadFrom((Join-Path $Root 'build\TerminalWorkspace.exe'))
  @{app_id=[TaskbarIdentity]::ReadWindow([IntPtr]$Window,5); command=[TaskbarIdentity]::ReadWindow([IntPtr]$Window,2); icon=[TaskbarIdentity]::ReadWindow([IntPtr]$Window,3)} | ConvertTo-Json -Compress
} elseif($Mode -eq 'activate') {
  $target=@($tabs | Where-Object { $_.runtime_id -ceq $Runtime -and $_.window -eq $Window })
  if($target.Count -ne 1) { throw 'Exact target disappeared' }
  if([FixtureGuard]::GetForegroundWindow().ToInt64() -ne $Origin) { throw 'User changed foreground; no activation' }
  if($OriginRuntime -and @($tabs | Where-Object { $_.window -eq $Origin -and $_.runtime_id -ceq $OriginRuntime -and $_.selected }).Count -ne 1) { throw 'Origin selection changed' }
  if(-not [TerminalViews]::Activate($Runtime,$Origin)) { throw 'Owned activation was refused' }
} elseif($Mode -eq 'close') {
  $entry=@($allowed | Where-Object window -eq $Window)
  $owned=@($tabs | Where-Object window -eq $Window)
  if($entry.Count -ne 1) { throw 'Unknown window' }
  if($owned.Count -gt 0) { [TerminalViews]::CloseTestWindow($Window) }
} else { throw 'Unknown fixture bridge operation' }
'''


class Fixture:
    def __init__(self, root):
        self.root = root
        self.windows = {}
        self.names = {}
        self.launches = []
        self.targets = {}
        self.witnesses = {}
        self.identities = {}
        self.evidence = {'ssh_started': False, 'kind': 'native-workspace-programmatic-focus', 'cases': []}
        self.python_image = Path(current_identity()['image'])

    def state(self):
        return json.loads(subprocess.check_output([str(self.root/'bin/TerminalViews.exe'), '-Mode', 'State'], timeout=10, creationflags=NO_WINDOW))

    def remember(self, identity, image):
        pid = identity['pid']
        if pid in self.witnesses:
            assert self.identities[pid] == identity, 'Fixture PID was reused'
        else:
            self.witnesses[pid] = ProcessWitness(identity, image)
            self.identities[pid] = identity

    def records(self):
        records = []
        for path in (self.root/'data').rglob('*.json'):
            try:
                record = json_read(path)
            except (OSError, ValueError):
                continue
            if not isinstance(record, dict) or not all(k in record for k in ('runtime_id','pid','started','window')):
                continue
            if 'window-views' in path.parts:
                continue
            expected = self.root/'bin'/('ports.exe' if path.parent.name == 'views' else 'terminal-workspace.exe')
            identity = live_identity(record['pid'])
            assert identity['created'] + 504911232000000000 == record['started'], 'View owner PID reused'
            self.remember(identity, expected)
            record['_path'] = path
            record['_kind'] = 'ports' if path.parent.name == 'views' else ('local' if path.parent.name == 'local-herdr-views' else 'remote')
            records.append(record)
        return records

    def allow(self):
        receipt(self.root, 'allowed.json', [{'window': h, 'tabs': sorted(ids)} for h, ids in self.windows.items()])

    def bridge(self, mode, window, runtime='', origin=0, origin_runtime=''):
        self.allow()
        return subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(self.root/'bridge.ps1'),
            '-Root',str(self.root),'-Mode',mode,'-Window',str(window),'-Runtime',runtime,'-Origin',str(origin),'-OriginRuntime',origin_runtime], timeout=12, creationflags=NO_WINDOW)

    def owned_state(self):
        state = self.state()
        assert state['foreground'] in self.windows, 'User left the owned windows; no reactivation'
        for h, allowed in self.windows.items():
            tabs = [t for t in state['tabs'] if t['window'] == h]
            assert all(t['runtime_id'] in allowed for t in tabs), 'User added a tab; retaining window'
        return state

    def selected(self, state=None):
        state = state or self.owned_state()
        matches = [t for t in state['tabs'] if t['window'] == state['foreground'] and t['selected']]
        assert len(matches) == 1
        return matches[0]

    def activate(self, record, initial=False):
        state = self.state() if initial else self.owned_state()
        origin = '' if initial else self.selected(state)['runtime_id']
        before = json_read(record['_path'])['last_focus']
        self.bridge('activate', record['window'], record['runtime_id'], state['foreground'], origin)
        def focused():
            selected = self.selected()
            current = json_read(record['_path'])
            return selected['runtime_id'] == record['runtime_id'] and current['last_focus'] > before
        wait_for(focused, 'Target/MRU registration did not update')

    def worker_for(self, record):
        for ready in (self.root/'workers').glob('*/ready.json'):
            item = json_read(ready)
            if item['owner']['pid'] == record['pid']:
                self.remember(item['worker'], self.python_image)
                self.remember(item['wrapper'], self.root/'HerdrFixture.exe')
                self.remember(item['owner'], self.root/'bin/terminal-workspace.exe')
                assert not item['herdr_context'], 'Verified new Herdr view inherited stale pane IDs'
                assert item['conda'] == 'owned developer environment', 'Developer environment was lost'
                assert item['argv'] == ([] if record['_kind'] == 'local' else ['--remote', self.targets[record['machine']]])
                return ready.parent
        return None

    def invoke(self, origin, target, executable, args, label):
        state = self.owned_state()
        assert self.selected(state)['runtime_id'] == origin['runtime_id'], 'Origin is not selected'
        # Bridge performs the immediate size/identity check before the file gate.
        self.bridge('check', origin['window'], origin=origin['window'], origin_runtime=origin['runtime_id'])
        control = wait_for(lambda: self.worker_for(origin), 'Stand-in worker did not register')
        target_focus=json_read(target['_path'])['last_focus']
        request = 'request-' + uuid.uuid4().hex
        receipt(control, request+'.json', {'executable':executable,'args':args})
        result = wait_for(lambda: json_read(control/(request+'-result.json')) if (control/(request+'-result.json')).exists() else None, 'Return command did not exit', 16)
        child=json_read(control/(request+'-child.json'))
        self.remember(child,self.root/'bin'/executable)
        assert self.witnesses[child['pid']].wait(0), 'Return process has not exited'
        assert result.get('code') == 0 and 'error' not in result, result
        wait_for(lambda: self.selected()['runtime_id'] == target['runtime_id'] and
                 json_read(target['_path'])['last_focus'] > target_focus,
                 'Target selection/MRU update missing')
        self.evidence['cases'].append({'name':label,'origin':origin['runtime_id'],'target':target['runtime_id'],**result})

    def add_window(self, machine):
        token = 'workspace-' + uuid.uuid4().hex
        title = 'Owned workspace ' + uuid.uuid4().hex
        argv = [str(self.root/'bin/terminal-workspace.exe'),'--root',str(self.root),'workspace','--window',token,'--machine',machine['id'],'--data-dir',str(self.root/'data'),'--taskbar-identity']
        receipt(self.root, token+'.json', {'argv':argv})
        self.launches.append(token)
        subprocess.run(['wt.exe','-w',token,'--size','70,18','--pos','12,160','new-tab','-p',PWSH,'--title',title,
            str(self.python_image),'-E','-s',str(self.root/'check_native_workspace.py'),'--bootstrap',str(self.root),token], check=True, timeout=10, creationflags=NO_WINDOW)
        bootstrap_tab = wait_for(lambda: next((t for t in self.state()['tabs'] if t['title'] == title), None), 'Bootstrap tab was not found')
        h = bootstrap_tab['window']
        assert h not in self.windows
        self.windows[h] = {bootstrap_tab['runtime_id']}
        self.names[h] = token
        assert len([t for t in self.state()['tabs'] if t['window']==h]) == 1, 'Bootstrap is not the only tab'
        # Small-window and exact-ID checks happen inside bridge before GO.
        self.bridge('identity', h)
        worker_file = self.root/token/'worker.json'
        wait_for(worker_file.exists, 'Bootstrap worker missing')
        self.remember(json_read(worker_file), self.python_image)
        (self.root/token/'go').write_text('go',encoding='ascii')
        def registered():
            records = [r for r in self.records() if r['window']==h]
            if len(records) != 3:
                return None
            assert {r['_kind'] for r in records} == {'remote','ports','local'}
            by_kind = {r['_kind']:r for r in records}
            assert by_kind['remote']['runtime_id'] == bootstrap_tab['runtime_id']
            assert all(r.get('machine') == machine['id'] for r in records if r['_kind']!='local')
            return by_kind
        views = wait_for(registered, 'Production workspace did not register three views', 25)
        self.windows[h] = {r['runtime_id'] for r in views.values()}
        tabs = [t for t in self.state()['tabs'] if t['window']==h]
        assert {t['runtime_id'] for t in tabs} == self.windows[h]
        assert next(t for t in tabs if t['selected'])['runtime_id'] == views['remote']['runtime_id']
        identity = json.loads(self.bridge('identity',h))
        assert identity['app_id'] == 'TerminalWorkspace.Desktop', identity
        assert str(self.root/'build/TerminalWorkspace.exe') in identity['command'], identity
        for kind in ('remote','local'):
            wait_for(lambda: self.worker_for(views[kind]), 'Herdr stand-in did not report its environment')
        self.evidence.setdefault('windows',[]).append({'window':h,'runtime_ids':sorted(self.windows[h]),'taskbar':identity})
        return views

    def add_tab(self, window, machine, kind):
        token='tab-'+uuid.uuid4().hex
        title='Owned additional tab '+uuid.uuid4().hex
        if kind=='remote':
            argv=[str(self.root/'bin/terminal-workspace.exe'),'--root',str(self.root),'remote',
                  '--machine',machine['id'],'--data-dir',str(self.root/'data')]
        else:
            assert kind=='ports'
            argv=[str(self.root/'bin/ports.exe'),'--data-dir',str(self.root/'data'),'--machine',machine['id']]
        receipt(self.root,token+'.json',{'argv':argv})
        self.launches.append(token)
        self.bridge('identity',window)
        subprocess.run(['wt.exe','-w',self.names[window],'new-tab','-p',PWSH,'--title',title,
            str(self.python_image),'-E','-s',str(self.root/'check_native_workspace.py'),'--bootstrap',str(self.root),token],
            check=True,timeout=10,creationflags=NO_WINDOW)
        tab=wait_for(lambda: next((t for t in self.state()['tabs'] if t['title']==title),None),'Added bootstrap tab missing')
        assert tab['window']==window and tab['runtime_id'] not in self.windows[window]
        self.windows[window].add(tab['runtime_id'])
        self.bridge('identity',window)
        worker_file=self.root/token/'worker.json'
        wait_for(worker_file.exists,'Added bootstrap worker missing')
        self.remember(json_read(worker_file),self.python_image)
        (self.root/token/'go').write_text('go',encoding='ascii')
        record=wait_for(lambda: next((r for r in self.records() if r['runtime_id']==tab['runtime_id']),None),'Added view did not register')
        assert record['_kind']==kind and record['machine']==machine['id']
        if kind=='remote':
            wait_for(lambda:self.worker_for(record),'Added remote stand-in missing')
        return record

    def cleanup(self):
        (self.root/'STOP').write_text('stop',encoding='ascii')
        # A bootstrap only ever spawns once. A recorded child proves it has
        # passed that spawn; otherwise wait for STOP to make the worker exit.
        for token in self.launches:
            control=self.root/token
            worker_file=control/'worker.json'
            if not worker_file.exists():
                raise RuntimeError(f'Bootstrap identity unavailable; retain {self.root}')
            identity=json_read(worker_file)
            self.remember(identity,self.python_image)
            child_file=control/'child.json'
            if not child_file.exists():
                if not self.witnesses[identity['pid']].wait(18):
                    raise RuntimeError(f'Bootstrap may still spawn; retain {self.root}')
                if (control/'spawn-started').exists() and not child_file.exists() and not (control/'child-reaped.json').exists():
                    raise RuntimeError(f'Bootstrap child identity unavailable; retain {self.root}')
            if child_file.exists():
                child=json_read(child_file)
                executable=Path(json_read(self.root/(token+'.json'))['argv'][0])
                self.remember(child,executable)
                # A receipt is not quiescence: STOP must release the stand-in
                # and the actual tab-spawning workspace must exit before close.
                if executable.name=='terminal-workspace.exe' and not self.witnesses[child['pid']].wait(25):
                    raise RuntimeError(f'Native workspace may still create tabs; retain {self.root}')
        # All stand-ins stop accepting commands and finish their owned children.
        for ready in (self.root/'workers').glob('*/ready.json'):
            data = json_read(ready)
            self.remember(data['worker'], self.python_image)
            self.remember(data['wrapper'],self.root/'HerdrFixture.exe')
            self.remember(data['owner'],self.root/'bin/terminal-workspace.exe')
            if not self.witnesses[data['worker']['pid']].wait(18):
                raise RuntimeError(f'Stand-in still running; retain {self.root}')
            for started in ready.parent.glob('request-*-spawn-started'):
                stem=started.name.removesuffix('-spawn-started')
                if not (ready.parent/(stem+'-child.json')).exists() and not (ready.parent/(stem+'-reaped.json')).exists():
                    raise RuntimeError(f'Request child ownership is unknown; retain {self.root}')
            for child_file in ready.parent.glob('request-*-child.json'):
                request=child_file.with_name(child_file.name.replace('-child.json','.json'))
                executable=json_read(request)['executable']
                assert executable in ('ports.exe','terminal-workspace.exe')
                self.remember(json_read(child_file),self.root/'bin'/executable)
        for h in self.windows:
            self.bridge('close',h)
        wait_for(lambda: not any(t['window'] in self.windows for t in self.state()['tabs']), 'Owned windows did not close')
        # Tab closure is not sufficient: verify cached app/worker handles exited.
        for pid, witness in self.witnesses.items():
            if not witness.wait(12):
                raise RuntimeError(f'Owned process {pid} remains; retain {self.root}')
        for endpoint in (self.root/'data/machines').glob('*/endpoint.json'):
            rpc(endpoint.parent,'shutdown')
            wait_for(lambda: not endpoint.exists(), 'Fixture controller did not stop')
        for witness in self.witnesses.values():
            witness.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yes',action='store_true')
    parser.add_argument('--bundle-dir',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--standin',type=Path)
    parser.add_argument('--bootstrap',nargs=2)
    parser.add_argument('tail',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if args.standin:
        standin(args.standin, args.tail[1:] if args.tail[:1]==['--'] else args.tail)
        return
    if args.bootstrap:
        bootstrap(Path(args.bootstrap[0]),args.bootstrap[1])
        return
    if not args.yes or not args.bundle_dir:
        parser.error('Use --yes --bundle-dir EXTRACTED_RELEASE for explicit desktop qualification')
    source=args.bundle_dir.resolve(strict=True)
    manifest=json_read(source/'release.json')
    runtime_files=['bin/terminal-workspace.exe','bin/ports.exe','bin/ssh-sessions.exe',
                   'bin/PortsFocus.exe','bin/TerminalViews.exe','build/TerminalWorkspace.exe']
    runtime_hashes={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in runtime_files}
    assert all(manifest['files'][name]==digest for name,digest in runtime_hashes.items()), 'Extracted release runtime changed'
    temp_parent=Path(tempfile.gettempdir()).resolve()
    folder=Path(tempfile.mkdtemp(prefix='native-workspace-',dir=temp_parent)).resolve()
    fixture=Fixture(folder)
    fixture.evidence.update(release_version=manifest['version'],runtime_sha256=runtime_hashes,
                           manifest_sha256=hashlib.sha256((source/'release.json').read_bytes()).hexdigest())
    cleaned=False
    try:
        for name in ('bin','build','config'):
            shutil.copytree(source/name,folder/name)
        for name in ('check_native_workspace.py','check_native_window_persistence.py'):
            shutil.copy2(Path(__file__).parent/name,folder/name)
        receipt(folder,'fixture-runtime.json',{'python':str(fixture.python_image)})
        (folder/'standin.cs').write_text(STANDIN,encoding='utf-8')
        (folder/'bridge.ps1').write_text(BRIDGE,encoding='utf-8-sig')
        framework=Path(os.environ['SystemRoot'])/'Microsoft.NET/Framework64/v4.0.30319'
        subprocess.run([str(framework/'csc.exe'),'/nologo','/target:exe','/platform:x64','/reference:System.Web.Extensions.dll',
                        '/out:'+str(folder/'HerdrFixture.exe'),str(folder/'standin.cs')],check=True,timeout=20,creationflags=NO_WINDOW)
        receipt(folder,'.machine.json',{'remote_client':'herdr','local_herdr':True,'herdr':str(folder/'HerdrFixture.exe')})
        machines=[]
        for alias in ('alpha.invalid','beta.invalid'):
            result=subprocess.run([str(folder/'bin/ports.exe'),'--data-dir',str(folder/'data'),'machines','add',alias,'--json'],capture_output=True,check=True,timeout=10,creationflags=NO_WINDOW)
            machine=json.loads(result.stdout)['machine']
            assert not machine.get('ssh_port') and not machine.get('ssh_config'), 'Fixture could fall through to real SSH'
            machines.append(machine)
            fixture.targets[machine['id']]=machine['target']
        assert json_read(folder/'.machine.json')['remote_client']=='herdr'
        first=fixture.add_window(machines[0])
        second=fixture.add_window(machines[0])
        remote_duplicate=fixture.add_tab(first['remote']['window'],machines[0],'remote')
        ports_duplicate=fixture.add_tab(first['remote']['window'],machines[0],'ports')
        other_remote=fixture.add_tab(second['remote']['window'],machines[1],'remote')
        other_ports=fixture.add_tab(second['remote']['window'],machines[1],'ports')
        fixture.activate(first['local'],initial=True)
        remote=['--root',str(folder),'remote','--data-dir',str(folder/'data'),'--focus-existing']
        ports=['--data-dir',str(folder/'data'),'--focus-existing']
        fixture.activate(first['remote'])
        fixture.activate(remote_duplicate)
        fixture.activate(first['local'])
        fixture.invoke(first['local'],remote_duplicate,'terminal-workspace.exe',remote,'remote duplicate MRU in one window')
        fixture.activate(first['ports'])
        fixture.activate(ports_duplicate)
        fixture.activate(first['local'])
        fixture.invoke(first['local'],ports_duplicate,'ports.exe',ports,'Ports duplicate MRU in one window')
        # Make the second window's remote newest, then invoke from first/local.
        fixture.activate(second['remote'])
        fixture.activate(first['local'])
        fixture.invoke(first['local'],second['remote'],'terminal-workspace.exe',remote,'remote across windows')
        receipt(folder/'data/machines'/machines[0]['id'],'ui-settings.json',{'focus_scope':'window'})
        fixture.activate(first['local'])
        fixture.invoke(first['local'],remote_duplicate,'terminal-workspace.exe',remote,'remote within originating window')
        receipt(folder/'data/machines'/machines[0]['id'],'ui-settings.json',{'focus_scope':'all'})
        fixture.activate(second['ports'])
        fixture.activate(first['local'])
        fixture.invoke(first['local'],second['ports'],'ports.exe',ports,'Ports across windows')
        receipt(folder/'data/machines'/machines[0]['id'],'ui-settings.json',{'focus_scope':'window'})
        fixture.activate(first['local'])
        fixture.invoke(first['local'],ports_duplicate,'ports.exe',ports,'Ports within originating window')
        receipt(folder/'data/machines'/machines[0]['id'],'ui-settings.json',{'focus_scope':'all'})
        fixture.activate(other_remote)
        fixture.activate(first['local'])
        fixture.invoke(first['local'],remote_duplicate,'terminal-workspace.exe',remote,'remote excludes newer different machine')
        fixture.activate(other_ports)
        fixture.activate(first['local'])
        fixture.invoke(first['local'],ports_duplicate,'ports.exe',ports,'Ports excludes newer different machine')
        fixture.activate(second['local'])
        fixture.activate(first['remote'])
        fixture.invoke(first['remote'],second['local'],'terminal-workspace.exe',remote+['--local'],'local Herdr across windows')
        receipt(folder/'data','ui-settings.json',{'focus_scope':'window'})
        fixture.activate(first['remote'])
        fixture.invoke(first['remote'],first['local'],'terminal-workspace.exe',remote+['--local'],'local Herdr within originating window')
        fixture.evidence['ok']=True
    finally:
        try:
            fixture.cleanup()
            cleaned=True
        finally:
            fixture.evidence['cleanup_complete']=cleaned
            fixture.evidence['fixture_root']=str(folder)
            if args.output:
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(fixture.evidence,indent=2,default=str),encoding='utf-8')
        if cleaned:
            assert folder.parent==temp_parent and folder.name.startswith('native-workspace-')
            shutil.rmtree(folder)
    print(json.dumps(fixture.evidence,indent=2,default=str))


if __name__=='__main__':
    main()
