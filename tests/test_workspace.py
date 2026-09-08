import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import configure
import workspace
from port_forward_tui.machines import Catalog


class WorkspaceTests(unittest.TestCase):
    def test_generic_ssh_install_needs_no_host_or_herdr(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'config').mkdir()
            (root / 'config/terminal.json').write_bytes((ROOT / 'config/terminal.json').read_bytes())
            app = root / 'apps/port-forward-tui'
            python = app / '.venv/Scripts/python.exe'
            python.parent.mkdir(parents=True)
            python.touch()
            data = root / 'data'
            settings = root / 'settings.json'
            with patch.object(configure, 'ROOT', root), patch.object(configure, 'PORT_APP', app), \
                    patch.object(configure, 'DATA_DIR', data), \
                    patch.object(sys, 'argv', ['configure', '--settings', str(settings), '--integration-only', '--herdr', str(root / 'missing.exe')]):
                configure.main()
            saved = json.loads(settings.read_text())
            remote = next(p for p in saved['profiles']['list'] if p['guid'] == configure.HERDR)
            self.assertIn('--client ssh', remote['commandline'])
            self.assertNotIn('--host', remote['commandline'])
            self.assertEqual(Catalog(data).list(), [])
            self.assertFalse(data.exists())

    def test_optional_local_herdr_has_separate_profile_shortcuts_and_return_command(self):
        shared = json.loads((ROOT / 'config/terminal.json').read_text())
        value = configure.render({}, shared, '', Path('C:/python.exe'), Path('C:/herdr.exe'), local_herdr=True)
        self.assertEqual(configure.render(value, shared, '', Path('C:/python.exe'), Path('C:/herdr.exe'), local_herdr=True), value)
        profiles = {p['guid']: p for p in value['profiles']['list']}
        self.assertIn('--local', profiles[configure.LOCAL]['commandline'])
        self.assertNotIn('--machine', profiles[configure.LOCAL]['commandline'])
        actions = {a['id']: a['command'] for a in value['actions']}
        self.assertIn('--focus-existing', actions[configure.LOCAL_ACTIONS['local']]['commandline'])
        self.assertEqual(len({k['keys'] for k in value['keybindings']}), 6)
        self.assertEqual({k['keys'] for k in value['keybindings']},
                         {'ctrl+alt+r', 'ctrl+alt+shift+r', 'ctrl+alt+p', 'ctrl+alt+shift+p', 'ctrl+alt+l', 'ctrl+alt+shift+l'})

    def test_companion_tabs_share_machine_and_named_window_and_focus_remote(self):
        for local in (False, True):
            args = workspace.tab_command('workspace-example', 'machine-123', Path('C:/python.exe'),
                                         data_dir=Path('C:/data'), local_herdr=local, herdr='C:/herdr.exe')
            self.assertEqual(args[:3], ['wt.exe', '-w', 'workspace-example'])
            self.assertEqual(args[args.index('--machine') + 1], 'machine-123')
            self.assertEqual(args[-4:], [';', 'focus-tab', '-t', '0'])
            self.assertEqual(args.count('new-tab'), 2 if local else 1)
            self.assertEqual('--local' in args, local)

    def test_local_hotkey_conflict_is_rejected_before_mutating_settings(self):
        original = {'keybindings': [{'id': 'user-command', 'keys': 'ctrl+alt+l'}]}
        before = json.dumps(original)
        shared = json.loads((ROOT / 'config/terminal.json').read_text())
        with self.assertRaisesRegex(ValueError, 'already assigned'):
            configure.render(original, shared, '', Path('python.exe'), Path('herdr.exe'), local_herdr=True)
        self.assertEqual(json.dumps(original), before)
