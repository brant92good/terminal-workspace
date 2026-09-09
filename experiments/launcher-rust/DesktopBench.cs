// Benchmark-only driver. Never activates a pre-existing user window.
using System;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Automation;

public static class DesktopBench {
    [DllImport("user32.dll")] static extern void keybd_event(byte key, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int width, int height, uint flags);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr window, int command);

    public static string Describe(long window) {
        var root = AutomationElement.FromHandle(new IntPtr(window));
        var texts = root.FindAll(TreeScope.Descendants, new AndCondition(
            new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Text),
            new PropertyCondition(AutomationElement.IsOffscreenProperty, false)));
        var result = new System.Collections.Generic.List<string>();
        foreach (AutomationElement element in texts) {
            object pattern;
            if (element.TryGetCurrentPattern(TextPattern.Pattern, out pattern)) {
                var text = ((TextPattern)pattern).DocumentRange.GetText(-1);
                result.Add(text.Substring(Math.Max(0, text.Length - 4000)));
            }
        }
        return new JavaScriptSerializer().Serialize(result);
    }

    public static string Run(string targetId, string sourceId, long expectedWindow, byte shortcut) {
        var tabs = TerminalViews.Tabs();
        var target = tabs.Single(t => t.runtime_id == targetId);
        var source = tabs.Single(t => t.runtime_id == sourceId);
        if (target.window != expectedWindow || source.window != expectedWindow)
            throw new Exception("Both benchmark tabs must belong to the owned test window");
        var handle = new IntPtr(expectedWindow);
        if (TerminalViews.GetForegroundWindow() != handle)
            throw new Exception("Test paused: another app has focus; no activation attempted");
        // Restore/size only the freshly created, explicitly supplied test window.
        ShowWindow(handle, 4); // SHOWNOACTIVATE
        SetWindowPos(handle, IntPtr.Zero, 12, 160, 700, 400, 0x0014); // NOZORDER | NOACTIVATE
        if (TerminalViews.GetForegroundWindow() != handle)
            throw new Exception("Test paused: another app has focus; no activation attempted");
        var selection = (SelectionItemPattern)target.element.GetCurrentPattern(SelectionItemPattern.Pattern);
        var samples = new object[2];
        for (int i = 0; i < samples.Length; i++) {
            Prime(targetId, expectedWindow);
            Thread.Sleep(350); // Let the MRU tracker observe priming; outside timer.
            Prime(sourceId, expectedWindow);
            Thread.Sleep(120);
            if (TerminalViews.GetForegroundWindow() != handle)
                throw new Exception("Test paused: another app has focus before keypress");
            var clock = Stopwatch.StartNew();
            try {
                keybd_event(0x11, 0, 0, UIntPtr.Zero);
                keybd_event(0x12, 0, 0, UIntPtr.Zero);
                keybd_event(shortcut, 0, 0, UIntPtr.Zero);
                Thread.Sleep(20);
            } finally {
                keybd_event(shortcut, 0, 2, UIntPtr.Zero);
                keybd_event(0x12, 0, 2, UIntPtr.Zero);
                keybd_event(0x11, 0, 2, UIntPtr.Zero);
            }
            while (true) {
                if (TerminalViews.GetForegroundWindow() != handle)
                    throw new Exception("Test paused: another app gained focus during measurement");
                var focused = AutomationElement.FocusedElement;
                if (selection.Current.IsSelected && focused != null && focused.Current.ControlType == ControlType.Text) break;
                if (clock.ElapsedMilliseconds > 5000) throw new Exception("Shortcut never focused target content");
                Thread.Sleep(5);
            }
            samples[i] = new { milliseconds = clock.Elapsed.TotalMilliseconds };
            Thread.Sleep(500);
        }
        return new JavaScriptSerializer().Serialize(samples);
    }
    static void Prime(string runtimeId, long window) {
        if (!TerminalViews.Activate(runtimeId, window))
            throw new Exception("Test paused: target unavailable or another app has focus");
    }
}
