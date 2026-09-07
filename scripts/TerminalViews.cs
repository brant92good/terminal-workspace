// Track Windows Terminal tab identity independently of its changing display name.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Automation;

public class TerminalViewRecord {
    public int pid;
    public long started;
    public string runtime_id;
    public long window;
    public long last_focus;
}

public class TerminalTabInfo {
    public string title;
    public string runtime_id;
    public long window;
    public bool selected;
    [ScriptIgnore] public AutomationElement element;
}

public static class TerminalViews {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr window);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr window, int command);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr window, uint message, IntPtr w, IntPtr l);
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();

    public static TerminalTabInfo[] Tabs() {
        var found = new List<TerminalTabInfo>();
        var windows = AutomationElement.RootElement.FindAll(TreeScope.Children,
            new PropertyCondition(AutomationElement.ClassNameProperty, "CASCADIA_HOSTING_WINDOW_CLASS"));
        foreach (AutomationElement window in windows) {
            try {
                var tabs = window.FindAll(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.TabItem));
                foreach (AutomationElement tab in tabs) {
                    object selection;
                    if (!tab.TryGetCurrentPattern(SelectionItemPattern.Pattern, out selection)) continue;
                    found.Add(new TerminalTabInfo {
                        title = tab.Current.Name,
                        runtime_id = String.Join(".", tab.GetRuntimeId()),
                        window = window.Current.NativeWindowHandle,
                        selected = ((SelectionItemPattern)selection).Current.IsSelected,
                        element = tab
                    });
                }
            } catch (ElementNotAvailableException) { }
        }
        return found.ToArray();
    }

    public static string Snapshot() { return Json.Serialize(Tabs()); }

    public static bool Activate(string runtimeId) {
        var tab = Tabs().FirstOrDefault(t => t.runtime_id == runtimeId);
        if (tab == null) return false;
        var window = new IntPtr(tab.window);
        if (IsIconic(window)) ShowWindow(window, 9);
        ((SelectionItemPattern)tab.element.GetCurrentPattern(SelectionItemPattern.Pattern)).Select();
        return GetForegroundWindow() == window || SetForegroundWindow(window);
    }

    public static void CloseTestWindow(long handle) {
        var window = new IntPtr(handle);
        PostMessage(window, 0x0010, IntPtr.Zero, IntPtr.Zero);
        Thread.Sleep(300);
        try {
            var root = AutomationElement.FromHandle(window);
            var confirm = root.FindFirst(TreeScope.Descendants, new AndCondition(
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button),
                new PropertyCondition(AutomationElement.AutomationIdProperty, "PrimaryButton")));
            if (confirm != null) ((InvokePattern)confirm.GetCurrentPattern(InvokePattern.Pattern)).Invoke();
        } catch (ElementNotAvailableException) { }
    }

    public static bool Alive(TerminalViewRecord record) {
        try {
            using (var process = Process.GetProcessById(record.pid))
                return !process.HasExited && process.StartTime.ToUniversalTime().Ticks == record.started;
        } catch (ArgumentException) { return false; }
          catch (System.ComponentModel.Win32Exception) { return false; }
          catch (InvalidOperationException) { return false; }
    }

    public static string Focus(string recordsJson, string scope, string originTitle, bool probe) {
        var records = Json.Deserialize<TerminalViewRecord[]>(recordsJson);
        var tabs = Tabs();
        long origin = 0;
        if (scope == "window") {
            var launcher = tabs.FirstOrDefault(t => t.title == originTitle);
            if (launcher == null) return "";
            origin = launcher.window;
        }
        foreach (var record in records.OrderByDescending(r => r.last_focus)) {
            if (!Alive(record)) continue;
            var tab = tabs.FirstOrDefault(t => t.runtime_id == record.runtime_id
                && (scope != "window" || t.window == origin));
            if (tab == null) continue;
            if (!probe) {
                var window = new IntPtr(tab.window);
                if (IsIconic(window)) ShowWindow(window, 9);
                ((SelectionItemPattern)tab.element.GetCurrentPattern(SelectionItemPattern.Pattern)).Select();
                if (GetForegroundWindow() != window && !SetForegroundWindow(window)) return "";
            }
            return Json.Serialize(tab);
        }
        return "";
    }

    public static void Track(string path, string title, string runtimeId, int pid) {
        TerminalTabInfo tab = null;
        var deadline = DateTime.UtcNow.AddSeconds(6);
        while (DateTime.UtcNow < deadline && tab == null) {
            tab = Tabs().FirstOrDefault(t => String.IsNullOrEmpty(runtimeId) ? t.title == title : t.runtime_id == runtimeId);
            if (tab == null) Thread.Sleep(100);
        }
        if (tab == null) throw new InvalidOperationException("Could not identify the Herdr Terminal tab.");
        long started;
        using (var owner = Process.GetProcessById(pid)) started = owner.StartTime.ToUniversalTime().Ticks;
        var record = new TerminalViewRecord { pid = pid, started = started, runtime_id = tab.runtime_id,
            window = tab.window, last_focus = DateTime.UtcNow.Ticks };
        var gate = new object();
        bool stopping = false;
        bool wasActive = false;
        Action save = () => {
            var temporary = path + ".tmp";
            File.WriteAllText(temporary, Json.Serialize(record), new UTF8Encoding(false));
            if (File.Exists(path)) File.Replace(temporary, path, null);
            else File.Move(temporary, path);
        };
        Action<bool> observe = (force) => {
            lock (gate) {
                if (stopping) return;
                try {
                    var pattern = (SelectionItemPattern)tab.element.GetCurrentPattern(SelectionItemPattern.Pattern);
                    bool active = GetForegroundWindow().ToInt64() == record.window && pattern.Current.IsSelected;
                    if (active && (force || !wasActive)) {
                        record.last_focus = DateTime.UtcNow.Ticks;
                        save();
                    }
                    wasActive = active;
                } catch (ElementNotAvailableException) { }
                  catch (IOException) { }
                  catch (InvalidOperationException) { }
            }
        };
        AutomationFocusChangedEventHandler focus = (sender, args) => observe(true);
        AutomationEventHandler selection = (sender, args) => observe(true);
        try {
            save();
            Automation.AddAutomationFocusChangedEventHandler(focus);
            Automation.AddAutomationEventHandler(SelectionItemPattern.ElementSelectedEvent,
                tab.element, TreeScope.Element, selection);
            while (Alive(record)) {
                observe(false);
                Thread.Sleep(250);
            }
        } finally {
            lock (gate) stopping = true;
            Automation.RemoveAutomationFocusChangedEventHandler(focus);
            Automation.RemoveAutomationEventHandler(SelectionItemPattern.ElementSelectedEvent, tab.element, selection);
            if (File.Exists(path)) File.Delete(path);
        }
    }
}
