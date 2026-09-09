"""Exercise native taskbar properties without showing or activating a window."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import workspace


@unittest.skipUnless(sys.platform == 'win32', 'Windows taskbar integration')
class TaskbarIdentityTests(unittest.TestCase):
    def test_native_shortcut_and_hidden_window_share_identity(self):
        framework = Path(os.environ['SystemRoot']) / 'Microsoft.NET/Framework64/v4.0.30319'
        with tempfile.TemporaryDirectory(prefix='workspace-taskbar-') as name:
            folder = Path(name) / 'space 測試'
            folder.mkdir()
            # Keep comparisons independent of the runner's RUNNER~1 TEMP alias.
            folder = folder.resolve()
            executable = folder / 'taskbar-check.exe'
            shortcut = folder / 'Workspace.lnk'
            references = ['System.Windows.Forms.dll', 'System.Core.dll',
                *[str(framework / 'WPF' / dll) for dll in ('UIAutomationClient.dll', 'UIAutomationTypes.dll', 'WindowsBase.dll')]]
            subprocess.run([str(framework / 'csc.exe'), '/nologo', '/target:exe', '/platform:x64',
                '/out:' + str(executable), *['/reference:' + r for r in references],
                str(ROOT / 'scripts/TaskbarIdentity.cs'), str(ROOT / 'scripts/WorkspaceShortcut.cs'),
                str(ROOT / 'tests/taskbar_identity_harness.cs')],
                check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
            result = subprocess.run([str(executable), str(executable), str(shortcut)],
                capture_output=True, text=True, errors='replace', creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + '\n' + result.stderr)
            self.assertIn('foreground preserved', result.stdout)

    def test_grouping_failure_keeps_startup_available(self):
        with patch('port_forward_tui.views.mark_origin', return_value='Shortcut | ' + 'a' * 32), \
                patch.object(workspace.subprocess, 'run', side_effect=subprocess.TimeoutExpired('helper', 7)):
            self.assertFalse(workspace.identify_taskbar())
        with patch('port_forward_tui.views.mark_origin', side_effect=OSError('no terminal')):
            self.assertFalse(workspace.identify_taskbar())
