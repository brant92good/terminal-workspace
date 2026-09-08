import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from doctor import workspace_checks


class WorkspaceDoctorTests(unittest.TestCase):
    def test_missing_or_malformed_machine_settings_do_not_crash_or_create_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch('doctor.app_checks', return_value=[]):
                checks = workspace_checks(root)
                self.assertFalse((root / '.machine.json').exists())
                self.assertEqual(next(c['status'] for c in checks if c['id'] == 'workspace_installed'), 'error')
                (root / '.machine.json').write_text('[]')
                checks = workspace_checks(root)
                self.assertTrue(any(c['id'] == 'machine_settings' and c['status'] == 'error' for c in checks))
                self.assertEqual((root / '.machine.json').read_text(), '[]')
