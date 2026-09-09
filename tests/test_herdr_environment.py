"""Standalone views discard pane identity while preserving developer settings."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from herdr_launcher import herdr_view_environment


class HerdrEnvironmentTests(unittest.TestCase):
    def test_new_view_discards_only_runtime_context(self):
        environment = {
            'HERDR_ENV': '1', 'HERDR_PANE_ID': 'w1:p2', 'HERDR_TAB_ID': 't1',
            'HERDR_WORKSPACE_ID': 'w1', 'HERDR_SOCKET_PATH': 'old-socket',
            'HERDR_STARTUP_CWD': 'old-folder', 'HERDR_BIN_PATH': 'old-binary',
            'PATH': 'custom-python;custom-tools', 'CONDA_PREFIX': 'project-env',
            'PYTHONPATH': 'user-libraries', 'SSH_AUTH_SOCK': 'user-agent',
            'HERDR_CONFIG_PATH': 'custom-config.toml', 'WT_SESSION': 'terminal-session',
        }
        prepared = herdr_view_environment(environment)
        self.assertEqual(prepared, {key: environment[key] for key in (
            'PATH', 'CONDA_PREFIX', 'PYTHONPATH', 'SSH_AUTH_SOCK', 'HERDR_CONFIG_PATH', 'WT_SESSION')})
        self.assertEqual(environment['HERDR_ENV'], '1')

    def test_windows_environment_names_are_case_insensitive(self):
        self.assertEqual(herdr_view_environment({'herdr_env': '1', 'Path': 'tools'}), {'Path': 'tools'})


if __name__ == '__main__':
    unittest.main()
