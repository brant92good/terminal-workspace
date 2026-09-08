import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from configure import ACTIONS, HERDR, PORTS, PWSH, render, export_shared
import configure


class TerminalSettingsTests(unittest.TestCase):
    def setUp(self):
        catalog = patch.object(configure, 'Catalog')
        catalog.start()
        self.addCleanup(catalog.stop)
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

    def test_integration_only_preserves_custom_terminal_setup(self):
        original = {
            "defaultProfile": "custom-shell", "theme": "light", "initialCols": 140,
            "profiles": {"defaults": {"font": {"face": "Custom Mono", "size": 15}},
                         "list": [{"guid": "custom-shell", "name": "My shell", "hidden": False},
                                  {"guid": PWSH, "name": "My PowerShell", "hidden": True}]},
            "newTabMenu": [{"type": "profile", "profile": "custom-shell"}],
            "actions": [{"id": "my-action", "command": "copy"}],
            "keybindings": [{"id": "my-action", "keys": "ctrl+shift+c"}],
        }
        before = json.dumps(original)
        updated = render(original, self.shared, "workbox", Path("C:/python.exe"),
                         Path("C:/herdr.exe"), integration_only=True)
        for key in ("defaultProfile", "theme", "initialCols", "newTabMenu"):
            self.assertEqual(updated[key], original[key])
        self.assertEqual(updated["profiles"]["defaults"], original["profiles"]["defaults"])
        self.assertEqual(updated["profiles"]["list"][:2], original["profiles"]["list"])
        self.assertEqual(updated["actions"][0], original["actions"][0])
        self.assertEqual(updated["keybindings"][0], original["keybindings"][0])
        self.assertEqual({p["guid"] for p in updated["profiles"]["list"][2:]}, {HERDR, PORTS})
        self.assertEqual({a["id"] for a in updated["actions"][1:]}, set(ACTIONS.values()))
        self.assertEqual(render(updated, self.shared, "workbox", Path("C:/python.exe"),
                                Path("C:/herdr.exe"), integration_only=True), updated)
        self.assertEqual(json.dumps(original), before)

    def test_integration_only_does_not_invent_a_default_shell_or_menu(self):
        updated = render({}, self.shared, "workbox", Path("C:/python.exe"),
                         Path("C:/herdr.exe"), integration_only=True)
        for key in ("defaultProfile", "theme", "newTabMenu", "initialCols"):
            self.assertNotIn(key, updated)
        self.assertNotIn("defaults", updated["profiles"])
        self.assertEqual({p["guid"] for p in updated["profiles"]["list"]}, {HERDR, PORTS})

    def test_install_mode_remembers_choice_and_allows_explicit_change(self):
        self.assertFalse(configure.install_mode({}, None))
        self.assertTrue(configure.install_mode({"integration_only": True}, None))
        self.assertFalse(configure.install_mode({"integration_only": True}, False))
        self.assertTrue(configure.install_mode({"integration_only": False}, True))
        with self.assertRaisesRegex(ValueError, "must be true or false"):
            configure.install_mode({"integration_only": "false"}, None)

    def test_integration_only_persists_on_reinstall_and_can_apply_shared_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root, settings, arguments = self.prepare_install(directory)
            original = {"defaultProfile": "custom-shell", "theme": "light"}
            settings.parent.mkdir()
            settings.write_text(json.dumps(original))
            with patch.object(configure, "ROOT", root), patch.object(configure, "PORT_APP", root / "app"), \
                    patch.object(configure, "Store", return_value=Mock(host="workbox")):
                for flags in (["--integration-only"], []):
                    with patch.object(sys, "argv", arguments + flags):
                        configure.main()
                    installed = json.loads(settings.read_text())
                    self.assertEqual(installed["defaultProfile"], "custom-shell")
                    self.assertEqual(installed["theme"], "light")
                    self.assertTrue(json.loads((root / ".machine.json").read_text())["integration_only"])
                with patch.object(sys, "argv", arguments + ["--apply-shared-settings"]):
                    configure.main()
                self.assertEqual(json.loads(settings.read_text())["defaultProfile"], PWSH)
                self.assertFalse(json.loads((root / ".machine.json").read_text())["integration_only"])

    def test_export_keeps_preferences_and_excludes_machine_values(self):
        settings = self.render(self.original)
        settings["profiles"]["defaults"] = {"font": {"size": 14}, "startingDirectory": "C:/private/project"}
        settings["startupActions"] = "private command"
        exported = export_shared(settings, self.shared)
        self.assertEqual(exported["profileDefaults"], {"font": {"size": 14}})
        serialized = json.dumps(exported)
        for private_value in ("workbox", "C:/private", "private command", "C:/herdr", "C:/app"):
            self.assertNotIn(private_value, serialized)

    def test_sync_removes_portable_overrides_absent_on_source_machine(self):
        shared = export_shared({}, self.shared)
        target = {"copyOnSelect": True, "initialCols": 160, "startupActions": "private command"}
        synced = render(target, shared, "workbox", Path("C:/app/python.exe"), Path("C:/herdr.exe"))
        self.assertNotIn("copyOnSelect", synced)
        self.assertNotIn("initialCols", synced)
        self.assertEqual(synced["startupActions"], "private command")

    def test_first_install_creates_missing_terminal_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root, settings, arguments = self.prepare_install(directory)
            store = Mock(host="workbox")
            with patch.object(configure, "ROOT", root), patch.object(configure, "PORT_APP", root / "app"), \
                    patch.object(configure, "Store", return_value=store), patch.object(sys, "argv", arguments):
                configure.main()
            installed = json.loads(settings.read_text())
            self.assertEqual(installed["defaultProfile"], PWSH)
            self.assertEqual({p["guid"] for p in installed["profiles"]["list"]}, {PWSH, HERDR, PORTS})
            self.assertEqual(len(installed["keybindings"]), 4)
            self.assertTrue((root / ".machine.json").is_file())

    def test_first_install_preserves_concurrently_created_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root, settings, arguments = self.prepare_install(directory)
            competing = b'{"initialCols": 123}'

            def concurrent_render(*args, **kwargs):
                settings.parent.mkdir(parents=True)
                settings.write_bytes(competing)
                return render(*args, **kwargs)

            with patch.object(configure, "ROOT", root), patch.object(configure, "PORT_APP", root / "app"), \
                    patch.object(configure, "Store", return_value=Mock(host="workbox")), \
                    patch.object(configure, "render", side_effect=concurrent_render), patch.object(sys, "argv", arguments):
                with self.assertRaisesRegex(ValueError, "settings changed"):
                    configure.main()
            self.assertEqual(settings.read_bytes(), competing)
            self.assertFalse((root / ".machine.json").exists())

    def test_existing_jsonc_settings_install_and_original_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root, settings, arguments = self.prepare_install(directory)
            settings.parent.mkdir()
            original = b'{ // user comment\n "profiles": {"list": [],}, "startupActions": "private command",}'
            settings.write_bytes(original)
            with patch.object(configure, "ROOT", root), patch.object(configure, "PORT_APP", root / "app"), \
                    patch.object(configure, "Store", return_value=Mock(host="workbox")), patch.object(sys, "argv", arguments):
                configure.main()
            self.assertEqual(json.loads(settings.read_text())["startupActions"], "private command")
            backups = list(settings.parent.glob("*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)

    def test_jsonc_parser_preserves_strings_and_rejects_invalid_data(self):
        data = {"url": "https://example.test/*literal*/", "date": "2026-09-08T12:00:00Z",
                "command": 'echo "$(literal)"', "items": [1, 2], "name": "終端機"}
        contents = ("/* comment */" + json.dumps(data, ensure_ascii=False)[:-1] + ",}// final comment").encode()
        self.assertEqual(configure.parse_settings(contents), data)
        for invalid in (b'{"broken":', b'{} {}', b'[]'):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    configure.parse_settings(invalid)

    def prepare_install(self, directory):
        root = Path(directory)
        (root / "config").mkdir()
        (root / "config/terminal.json").write_text(json.dumps(self.shared))
        python = root / "app/.venv/Scripts/python.exe"
        python.parent.mkdir(parents=True)
        python.touch()
        herdr = root / "herdr.exe"
        herdr.touch()
        settings = root / "LocalState/settings.json"
        return root, settings, ["configure.py", "--settings", str(settings), "--ssh-host", "workbox", "--herdr", str(herdr)]


if __name__ == "__main__":
    unittest.main()
