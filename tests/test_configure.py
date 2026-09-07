import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from configure import ACTIONS, HERDR, PORTS, PWSH, render, export_shared


class TerminalSettingsTests(unittest.TestCase):
    def setUp(self):
        self.shared = json.loads((ROOT / "config/terminal.json").read_text())
        self.original = {"profiles": {"list": [
            {"guid": "wsl", "source": "Microsoft.WSL", "name": "Ubuntu"},
            {"guid": "old", "name": "Old shell", "hidden": False}]},
            "actions": [{"id": "legacy", "command": {"action": "newTab", "profile": HERDR}}],
            "keybindings": [{"id": "legacy", "keys": "ctrl+alt+h"}]}

    def render(self, original):
        return render(original, self.shared, "workbox", Path("C:/app/python.exe"), Path("C:/herdr.exe"))

    def test_idempotent_profiles_shortcuts_and_default(self):
        first = self.render(self.original)
        self.assertEqual(self.render(first), first)
        self.assertEqual(first["defaultProfile"], PWSH)
        visible = {p["guid"] for p in first["profiles"]["list"] if not p.get("hidden")}
        self.assertEqual(visible, {PWSH, HERDR, PORTS, "wsl"})
        commands = {a["id"]: a["command"] for a in first["actions"]}
        for app in ("herdr", "ports"):
            self.assertIn("--focus-existing", commands[ACTIONS[app]]["commandline"])
        for app in ("newHerdr", "newPorts"):
            self.assertNotIn("commandline", commands[ACTIONS[app]])

    def test_unrelated_shortcut_conflict_does_not_change_original(self):
        self.original["keybindings"].append({"id": "my-action", "keys": "ctrl+alt+p"})
        before = json.dumps(self.original)
        with self.assertRaises(ValueError):
            self.render(self.original)
        self.assertEqual(json.dumps(self.original), before)

    def test_export_keeps_preferences_and_excludes_machine_values(self):
        settings = self.render(self.original)
        settings["profiles"]["defaults"] = {"font": {"size": 14}, "startingDirectory": "C:/private/project"}
        settings["startupActions"] = "private command"
        exported = export_shared(settings, self.shared)
        self.assertEqual(exported["profileDefaults"], {"font": {"size": 14}})
        serialized = json.dumps(exported)
        for private_value in ("workbox", "C:/private", "private command", "C:/herdr", "C:/app"):
            self.assertNotIn(private_value, serialized)


if __name__ == "__main__":
    unittest.main()
