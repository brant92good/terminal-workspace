using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Windows.Forms;

public static class WorkspaceLauncher {
    static string Quote(string value) {
        return "\"" + Regex.Replace(value, "(\\\\*)\"", "$1$1\\\"") +
            new string('\\', value.Reverse().TakeWhile(c => c == '\\').Count()) + "\"";
    }
    [STAThread]
    public static int Main(string[] args) {
        try {
            if (args.Length == 2 && args[0] == "--create-shortcut") {
                WorkspaceShortcut.Create(args[1], System.Reflection.Assembly.GetExecutingAssembly().Location);
                TaskbarIdentity.RegisterShortcut(args[1]);
                return 0;
            }
            if (args.Length == 2 && args[0] == "--register-pins") {
                WorkspaceShortcut.RegisterMatchingPins(args[1], System.Reflection.Assembly.GetExecutingAssembly().Location);
                return 0;
            }
            if (args.Length == 2 && args[0] == "--register-shortcut") {
                TaskbarIdentity.RegisterShortcut(args[1]);
                return 0;
            }
            if (args.Length == 2 && args[0] == "--identify-origin") {
                TaskbarIdentity.IdentifyOrigin(args[1], System.Reflection.Assembly.GetExecutingAssembly().Location);
                return 0;
            }
            var root = Directory.GetParent(AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\')).FullName;
            var python = Path.Combine(root, "apps", "port-forward-tui", ".venv", "Scripts", "python.exe");
            var script = Path.Combine(root, "scripts", "workspace.py");
            var window = "workspace-" + Guid.NewGuid().ToString("N");
            Process.Start(new ProcessStartInfo {
                FileName = "wt.exe",
                Arguments = "-w " + window + " new-tab -p \"{a9a0b421-7dd6-4425-9843-59b5f5d6c2d1}\" " +
                    Quote(python) + " -E -s " + Quote(script) + " --taskbar-identity --window " + window + " " + String.Join(" ", args.Select(Quote)),
                UseShellExecute = true
            });
            return 0;
        } catch (Exception error) {
            // Helpers must not create a surprise dialog or activate a window.
            if (args.Length > 0 && new[] { "--register-shortcut", "--identify-origin", "--create-shortcut", "--register-pins" }.Contains(args[0])) {
                var log = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "TerminalWorkspace");
                try {
                    Directory.CreateDirectory(log);
                    File.AppendAllText(Path.Combine(log, "taskbar.log"), DateTime.UtcNow.ToString("o") + " " + error.Message + Environment.NewLine);
                } catch { }
                return 1;
            }
            MessageBox.Show(error.Message, "Terminal Workspace", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
