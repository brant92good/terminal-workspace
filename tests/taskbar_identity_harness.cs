using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public static class TaskbarIdentityHarness {
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    static void Check(bool value, string message) {
        if (!value) throw new Exception(message);
    }
    [STAThread] public static int Main(string[] args) {
        var foreground = GetForegroundWindow();
        var launcher = Path.GetFullPath(args[0]);
        var shortcut = Path.GetFullPath(args[1]);
        using (var window = new Form())
        using (var unrelated = new Form()) {
            // Create handles without Show/Activate: no taskbar item or visible window.
            var handle = window.Handle;
            var other = unrelated.Handle;
            var previous = TaskbarIdentity.ReadWindow(other, 5);
            Check(TaskbarIdentity.ReadShortcut(shortcut) == null, "Fixture unexpectedly has an AppID");
            TaskbarIdentity.RegisterShortcut(shortcut);
            TaskbarIdentity.RegisterShortcut(shortcut);
            Check(TaskbarIdentity.ReadShortcut(shortcut) == TaskbarIdentity.AppId, "Shortcut AppID mismatch");
            TaskbarIdentity.ApplyWindow(handle, launcher);
            Check(TaskbarIdentity.ReadWindow(handle, 5) == TaskbarIdentity.ReadShortcut(shortcut), "Window and pin identities differ");
            Check(TaskbarIdentity.ReadWindow(handle, 2) == "\"" + launcher + "\"", "Relaunch command lost quoting");
            Check(TaskbarIdentity.ReadWindow(handle, 3) == launcher + ",0", "Relaunch icon differs");
            Check(TaskbarIdentity.ReadWindow(other, 5) == previous, "Unrelated window changed");
            TaskbarIdentity.ApplyWindow(handle, launcher);
            Check(TaskbarIdentity.ReadWindow(handle, 5) == TaskbarIdentity.AppId, "Repeated registration changed identity");
            try {
                TaskbarIdentity.IdentifyOrigin("Terminal", launcher);
                throw new Exception("Non-unique title was accepted");
            } catch (ArgumentException) { }
            try {
                TaskbarIdentity.IdentifyOrigin("Shortcut | " + Guid.NewGuid().ToString("N"), launcher);
                throw new Exception("Missing origin guessed another window");
            } catch (TimeoutException) { }
            Check(TaskbarIdentity.ReadWindow(other, 5) == previous, "Missing origin changed an unrelated window");
            Check(GetForegroundWindow() == foreground, "Taskbar operations moved focus");
        }
        Console.WriteLine("PASS: hidden-window identity, shortcut round-trip, relaunch/icon metadata, repeat registration, missing-origin refusal, unrelated window and foreground preserved.");
        return 0;
    }
}
