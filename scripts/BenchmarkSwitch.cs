using System;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Automation;

public static class BenchmarkSwitch {
    [DllImport("user32.dll")] static extern void keybd_event(byte key, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int width, int height, uint flags);

    public static string Run(string targetId, string sourceId, int count, byte shortcut, long expectedWindow) {
        var tabs = TerminalViews.Tabs();
        var target = tabs.Single(t => t.runtime_id == targetId && t.window == expectedWindow);
        if (!tabs.Any(t => t.runtime_id == sourceId && t.window == expectedWindow))
            throw new Exception("Source must belong to the owned test window");
        EnsureForeground(expectedWindow);
        SetWindowPos(new IntPtr(expectedWindow), IntPtr.Zero, 12, 160, 700, 400, 0x0014);
        var selection = (SelectionItemPattern)target.element.GetCurrentPattern(SelectionItemPattern.Pattern);
        var samples = new object[count];
        for (int i = 0; i < count; i++) {
            Prime(targetId, expectedWindow);
            Thread.Sleep(120);
            Prime(sourceId, expectedWindow);
            Thread.Sleep(120);
            EnsureForeground(expectedWindow);
            double started = Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency;
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
                EnsureForeground(expectedWindow);
                var focused = AutomationElement.FocusedElement;
                if (TerminalViews.GetForegroundWindow().ToInt64() == target.window && selection.Current.IsSelected
                    && focused != null && focused.Current.ControlType == ControlType.Text) break;
                if (clock.ElapsedMilliseconds > 10000) throw new Exception("Shortcut never focused target content");
                Thread.Sleep(5);
            }
            samples[i] = new { started = started, focused = Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency,
                milliseconds = clock.Elapsed.TotalMilliseconds };
            // The old helper can still be pending after Terminal momentarily
            // restores an adjacent tab. Keep it out of the following sample.
            Thread.Sleep(1000);
        }
        return new JavaScriptSerializer().Serialize(samples);
    }
    static void EnsureForeground(long window) {
        if (TerminalViews.GetForegroundWindow().ToInt64() != window)
            throw new Exception("Test stopped: another app has focus; no activation attempted");
    }
    static void Prime(string runtimeId, long window) {
        EnsureForeground(window);
        if (!TerminalViews.Activate(runtimeId, window))
            throw new Exception("Test stopped: target unavailable or another app has focus");
    }
}
