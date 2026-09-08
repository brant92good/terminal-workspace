"""Verify return-shortcut origin identity without changing desktop focus."""
import json
import base64
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import herdr_launcher


class HerdrFocusTests(unittest.TestCase):
    def setUp(self):
        fallback = patch.object(herdr_launcher, "focus_command", return_value=["powershell.exe", "-File", "fallback.ps1"])
        fallback.start()
        self.addCleanup(fallback.stop)

    def test_handoff_uses_the_marker_window_for_both_scopes(self):
        for scope in ("all", "window"):
            with self.subTest(scope=scope), \
                    patch.object(herdr_launcher, "live_records", return_value=[{"pid": 1}]), \
                    patch.object(herdr_launcher.subprocess, "run") as probe, \
                    patch.object(herdr_launcher, "delayed_focus", return_value=True) as launch:
                probe.return_value.returncode = 0
                probe.return_value.stdout = json.dumps({"runtime_id": "target-tab", "window": 100, "origin": 200})
                self.assertTrue(herdr_launcher.try_focus(Path("unused"), scope, "launcher-marker"))
                probe_args = probe.call_args.args[0]
                self.assertEqual(probe_args[probe_args.index("-OriginTitle") + 1], "launcher-marker")
                self.assertEqual(probe_args[probe_args.index("-Scope") + 1], scope)
                args = launch.call_args.args[0]
                self.assertEqual(args[args.index("-RuntimeId") + 1], "target-tab")
                self.assertEqual(args[args.index("-InvokeWindow") + 1], "200")
                self.assertIn("-AfterPid", args)

    def test_activation_requires_an_origin_marker_and_resolved_window(self):
        with patch.object(herdr_launcher, "live_records", return_value=[{"pid": 1}]), \
                patch.object(herdr_launcher.subprocess, "run") as probe, \
                patch.object(herdr_launcher, "delayed_focus") as launch:
            self.assertFalse(herdr_launcher.try_focus(Path("unused"), "all"))
            probe.assert_not_called()
            probe.return_value.returncode = 0
            for origin in (None, 0):
                with self.subTest(origin=origin):
                    probe.return_value.stdout = json.dumps({"runtime_id": "target-tab", "origin": origin})
                    self.assertFalse(herdr_launcher.try_focus(Path("unused"), "all", "launcher-marker"))
            launch.assert_not_called()

    def test_read_only_probe_never_activates(self):
        with patch.object(herdr_launcher, "live_records", return_value=[{"pid": 1}]), \
                patch.object(herdr_launcher.subprocess, "run") as probe, \
                patch.object(herdr_launcher, "delayed_focus") as launch:
            probe.return_value.returncode = 0
            self.assertTrue(herdr_launcher.try_focus(Path("unused"), "all", probe=True))
            launch.assert_not_called()


class NativeHerdrFocusTests(unittest.TestCase):
    def test_native_handoff_preserves_record_identity_and_scope(self):
        records = [{"pid": 123, "started": 456, "runtime_id": "42.1.2", "last_focus": 789}]
        for scope in ("all", "window"):
            with self.subTest(scope=scope), \
                    patch.object(herdr_launcher, "live_records", return_value=records), \
                    patch.object(herdr_launcher, "focus_command", return_value=["FocusHelper.exe"]), \
                    patch.object(herdr_launcher, "native_focus", return_value=True) as launch, \
                    patch.object(herdr_launcher.subprocess, "run") as powershell:
                self.assertTrue(herdr_launcher.try_focus(Path("unused"), scope, "launcher-marker"))
                args = launch.call_args.args[0]
                self.assertEqual(json.loads(base64.b64decode(args[args.index("-RecordsBase64") + 1])), records)
                self.assertEqual(args[args.index("-OriginTitle") + 1], "launcher-marker")
                self.assertEqual(args[args.index("-Scope") + 1], scope)
                powershell.assert_not_called()

    def test_native_probe_never_starts_a_handoff(self):
        with patch.object(herdr_launcher, "live_records", return_value=[{"pid": 1}]), \
                patch.object(herdr_launcher, "focus_command", return_value=["FocusHelper.exe"]), \
                patch.object(herdr_launcher.subprocess, "run") as probe, \
                patch.object(herdr_launcher, "native_focus") as launch:
            probe.return_value.returncode = 0
            self.assertTrue(herdr_launcher.try_focus(Path("unused"), "all", probe=True))
            self.assertIn("-ProbeOnly", probe.call_args.args[0])
            launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
