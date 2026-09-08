"""Profiling restores shortcut settings even on failure or concurrent edits."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import profile_focus


class ProfileRestoreTests(unittest.TestCase):
    def test_failure_restores_exact_original_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            original = b'{"actions":[{"id":"User.TerminalWorkspace.Herdr","command":{"commandline":"herdr_launcher.py --focus-existing"}}]}\r\n'
            path.write_bytes(original)
            with patch.object(profile_focus, "settings_path", return_value=path), patch.object(profile_focus.time, "sleep"):
                with self.assertRaisesRegex(RuntimeError, "test failure"):
                    with profile_focus.trace_herdr(Path(folder) / "trace"):
                        self.assertIn(b"--trace-dir", path.read_bytes())
                        raise RuntimeError("test failure")
            self.assertEqual(path.read_bytes(), original)

    def test_concurrent_unrelated_edit_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            command = "herdr_launcher.py --focus-existing"
            path.write_text(json.dumps({"actions": [{"id": "User.TerminalWorkspace.Herdr", "command": {"commandline": command}}]}))
            with patch.object(profile_focus, "settings_path", return_value=path), patch.object(profile_focus.time, "sleep"):
                with profile_focus.trace_herdr(Path(folder) / "trace"):
                    data = json.loads(path.read_text())
                    data["copyOnSelect"] = True
                    path.write_text(json.dumps(data))
            restored = json.loads(path.read_text())
            self.assertTrue(restored["copyOnSelect"])
            self.assertEqual(profile_focus.action(restored)["command"]["commandline"], command)
