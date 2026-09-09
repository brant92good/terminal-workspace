// Test-only helper gate and mini focus target. No user window is activated.
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Automation;
using System.Windows.Forms;

public static class CancelBench {
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool AllowSetForegroundWindow(int pid);
    static string Folder { get { return Path.GetDirectoryName(Application.ExecutablePath); } }
    static string FileAt(string name) { return Path.Combine(Folder, name); }

    // These test arguments cannot contain quotes or end in a backslash.
    static string Quote(string value) {
        if (value.Contains("\"") || value.EndsWith("\\")) throw new ArgumentException("Unexpected test argument");
        return "\"" + value + "\"";
    }

    static int Proxy(string[] args) {
        File.WriteAllText(FileAt("probe.ready"), "ready");
        var deadline = DateTime.UtcNow.AddSeconds(4);
        while (!File.Exists(FileAt("probe.release"))) {
            if (DateTime.UtcNow > deadline) return 3;
            Thread.Sleep(10);
        }
        var info = new ProcessStartInfo(File.ReadAllText(FileAt("helper.txt")),
            String.Join(" ", args.Select(Quote))) { UseShellExecute = false, CreateNoWindow = true };
        using (var child = Process.Start(info)) {
            AllowSetForegroundWindow(child.Id);
            if (!child.WaitForExit(10000)) { child.Kill(); return 3; }
            File.WriteAllText(FileAt("probe.done"), child.ExitCode.ToString());
            return child.ExitCode;
        }
    }

    static int Watch(long window, string targetId) {
        var target = TerminalViews.Tabs().Single(t => t.runtime_id == targetId && t.window == window);
        var selection = (SelectionItemPattern)target.element.GetCurrentPattern(SelectionItemPattern.Pattern);
        using (var form = new Form())
        using (var button = new Button())
        using (var timer = new System.Windows.Forms.Timer()) {
            form.Text = "Launcher test: focus must stay here";
            form.StartPosition = FormStartPosition.Manual;
            form.SetBounds(12, 10, 440, 140);
            button.Text = "Simulating a switch to another application";
            button.Dock = DockStyle.Fill;
            form.Controls.Add(button);
            DateTime? switched = null;
            var deadline = DateTime.UtcNow.AddSeconds(20);
            string result = null;
            form.Shown += (s, e) => File.WriteAllText(FileAt("watch.ready"), "ready");
            timer.Interval = 20;
            timer.Tick += (s, e) => {
                try {
                    if (DateTime.UtcNow > deadline) throw new Exception("Timed out");
                    if (switched == null && File.Exists(FileAt("probe.ready"))) {
                        // Never reclaim Chrome or an existing user Terminal window.
                        if (GetForegroundWindow().ToInt64() != window)
                            throw new Exception("External focus change: test stopped without activation");
                        if (selection.Current.IsSelected) throw new Exception("Target must start unselected");
                        form.Activate();
                        button.Focus();
                        if (GetForegroundWindow() != form.Handle) throw new Exception("Mini target did not receive focus");
                        var source = TerminalViews.Tabs().First(t => t.window == window && t.runtime_id != targetId);
                        RefusesExternalFocus(() => DesktopBench.Run(targetId, source.runtime_id, window, 0x78));
                        RefusesExternalFocus(() => BenchmarkSwitch.Run(targetId, source.runtime_id, 1, 0x78, window));
                        switched = DateTime.UtcNow;
                        File.WriteAllText(FileAt("probe.release"), "continue");
                    }
                    if (switched != null) {
                        if (GetForegroundWindow() != form.Handle) throw new Exception("Mini target lost focus");
                        if (selection.Current.IsSelected) throw new Exception("Return helper selected the target after cancellation");
                        if (File.Exists(FileAt("probe.done")) && (DateTime.UtcNow - switched.Value).TotalSeconds > 2) {
                            if (File.ReadAllText(FileAt("probe.done")) != "1") throw new Exception("Expected native helper cancellation");
                            result = "PASS: mini app kept focus, target stayed unselected, both benchmark drivers refused external focus";
                        }
                    }
                } catch (Exception error) { result = "FAIL: " + error.Message; }
                if (result != null) { timer.Stop(); form.Close(); }
            };
            timer.Start();
            Application.Run(form);
            File.WriteAllText(FileAt("result.txt"), result ?? "FAIL: test window was closed");
            return result != null && result.StartsWith("PASS") ? 0 : 1;
        }
    }

    static void RefusesExternalFocus(Func<string> run) {
        try { run(); }
        catch (Exception error) {
            if (error.Message.Contains("another app has focus")) return;
            throw;
        }
        throw new Exception("Benchmark driver did not reject external focus");
    }

    [STAThread]
    public static int Main(string[] args) {
        try {
            return args.Length == 3 && args[0] == "--watch"
                ? Watch(Int64.Parse(args[1]), args[2]) : Proxy(args);
        } catch (Exception error) {
            File.WriteAllText(FileAt("failure.txt"), error.ToString());
            return 2;
        }
    }
}
