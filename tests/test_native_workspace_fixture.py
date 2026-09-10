"""Headless checks for the opt-in desktop fixture's request protocol."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('workspace_fixture', SCRIPTS/'check_native_workspace.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class RequestProtocol(unittest.TestCase):
    def test_completed_request_receipts_are_never_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stem = 'request-' + 'a'*32
            next_stem = 'request-' + 'b'*32
            for name in (stem+'.json', stem+'-child.json', stem+'-reaped.json',
                         stem+'-result.json', stem+'-spawn-started',
                         next_stem+'.json', 'request-invalid.json'):
                (root/name).write_text('{}', encoding='ascii')
            self.assertEqual([p.name for p in fixture.pending_requests(root, set())],
                             [stem+'.json', next_stem+'.json'])
            self.assertEqual([p.name for p in fixture.pending_requests(root, {stem+'.json'})],
                             [next_stem+'.json'])
            self.assertEqual(fixture.pending_requests(root, {stem+'.json', next_stem+'.json'}), [])

    def test_reused_pid_cannot_reuse_old_process_witness(self):
        owner = object.__new__(fixture.Fixture)
        original = {'pid':123, 'created':10, 'image':'owned.exe'}
        owner.witnesses = {123:object()}
        owner.identities = {123:original}
        owner.remember(dict(original), Path('owned.exe'))
        with self.assertRaisesRegex(AssertionError, 'PID was reused'):
            owner.remember(dict(original, created=11), Path('owned.exe'))


if __name__ == '__main__':
    unittest.main()
