import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import configure


class SessionPickerSettingsTests(unittest.TestCase):
    def render(self, original, **options):
        shared = json.loads((ROOT / 'config/terminal.json').read_text())
        return configure.render(original, shared, None, Path('C:/Tools/python.exe'), Path('C:/Herdr/herdr.exe'),
            root=Path('C:/Workspace'), session_picker=True, session_catalog=Path('C:/Private catalog/hosts.json'), **options)

    def test_picker_default_and_local_shell_hotkey_are_distinct(self):
        data = self.render({}, local_herdr=True)
        self.assertEqual(data['defaultProfile'], configure.SESSIONS)
        profile = next(p for p in data['profiles']['list'] if p['guid'] == configure.SESSIONS)
        self.assertIn('ssh-session-tui', profile['commandline'])
        self.assertIn('"C:', profile['commandline'])
        self.assertIn('--catalog', profile['commandline'])
        shell = next(a for a in data['actions'] if a['id'] == configure.SHELL_ACTION)
        self.assertEqual(shell['command'], {'action': 'newTab', 'profile': configure.PWSH})
        keys = {k['keys'] for k in data['keybindings']}
        self.assertEqual(len(keys), 7)
        self.assertIn('ctrl+alt+n', keys)
        self.assertEqual(self.render(data, local_herdr=True), data)

    def test_integration_only_preserves_default_until_explicitly_requested(self):
        self.assertEqual(self.render({'defaultProfile': 'custom'}, integration_only=True)['defaultProfile'], 'custom')
        self.assertEqual(self.render({'defaultProfile': 'custom'}, integration_only=True, apply_default=True)['defaultProfile'], configure.SESSIONS)

    def test_local_shell_works_when_automatic_pwsh_profile_is_disabled(self):
        original = {'disabledProfileSources': ['Windows.Terminal.PowershellCore']}
        data = self.render(original, integration_only=True, apply_default=True)
        profile = next(p for p in data['profiles']['list'] if p['guid'] == configure.PWSH)
        self.assertEqual(profile['commandline'], 'pwsh.exe -NoLogo')
        self.assertNotIn('source', profile)
        self.assertEqual(data['disabledProfileSources'], original['disabledProfileSources'])

    def test_conflicting_local_shell_hotkey_preserves_original_settings(self):
        original = {'keybindings': [{'keys': 'ctrl+alt+n', 'id': 'other'}]}
        before = json.dumps(original)
        with self.assertRaisesRegex(ValueError, 'already assigned'):
            self.render(original)
        self.assertEqual(json.dumps(original), before)

    def test_catalog_path_does_not_export_to_public_preferences(self):
        data = self.render({})
        shared = json.loads((ROOT / 'config/terminal.json').read_text())
        self.assertNotIn('Private catalog', json.dumps(configure.export_shared(data, shared)))

    def test_optional_new_tab_shortcut_opens_default_profile_and_is_idempotent(self):
        data = self.render({}, shortcuts={'newTab': 'ctrl+n'})
        self.assertEqual(next(a['command'] for a in data['actions'] if a['id'] == configure.TAB_ACTION), {'action': 'newTab'})
        self.assertIn({'id': configure.TAB_ACTION, 'keys': 'ctrl+n'}, data['keybindings'])
        self.assertEqual(self.render(data, shortcuts={'newTab': 'ctrl+n'}), data)
        self.assertFalse(any(a['id'] == configure.TAB_ACTION for a in self.render(data)['actions']))

    def test_new_tab_shortcut_conflict_is_rejected_without_changing_input(self):
        original = {'keybindings': [{'keys': 'ctrl+n', 'id': 'User.Existing'}]}
        before = json.dumps(original)
        with self.assertRaisesRegex(ValueError, 'already assigned'):
            self.render(original, shortcuts={'newTab': 'ctrl+n'})
        self.assertEqual(json.dumps(original), before)
