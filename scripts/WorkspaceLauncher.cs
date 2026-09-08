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
    public static void Main(string[] args) {
        try {
            var root = Directory.GetParent(AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\')).FullName;
            var python = Path.Combine(root, "apps", "port-forward-tui", ".venv", "Scripts", "python.exe");
            var script = Path.Combine(root, "scripts", "workspace.py");
            var window = "workspace-" + Guid.NewGuid().ToString("N");
            Process.Start(new ProcessStartInfo {
                FileName = "wt.exe",
                Arguments = "-w " + window + " new-tab -p \"{a9a0b421-7dd6-4425-9843-59b5f5d6c2d1}\" " +
                    Quote(python) + " -E -s " + Quote(script) + " --window " + window + " " + String.Join(" ", args.Select(Quote)),
                UseShellExecute = true
            });
        } catch (Exception error) {
            MessageBox.Show(error.Message, "Terminal Workspace", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
