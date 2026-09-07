"""Verify return-shortcut origin identity without changing desktop focus."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import herdr_launcher


class HerdrFocusTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
