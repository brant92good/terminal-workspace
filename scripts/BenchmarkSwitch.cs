using System;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Automation;

public static class BenchmarkSwitch {
    [DllImport("user32.dll")] static extern void keybd_event(byte key, byte scan, uint flags, UIntPtr extra);

    public static string Run(string targetId, string sourceId, int count, byte shortcut) {
        var target = TerminalViews.Tabs().First(t => t.runtime_id == targetId);
        var selection = (SelectionItemPattern)target.element.GetCurrentPattern(SelectionItemPattern.Pattern);
        var samples = new object[count];
        for (int i = 0; i < count; i++) {
            Prime(targetId);
            Thread.Sleep(120);
            Prime(sourceId);
            Thread.Sleep(120);
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
    static void Prime(string runtimeId) {
        var deadline = DateTime.UtcNow.AddSeconds(8);
        while (DateTime.UtcNow < deadline) {
            if (TerminalViews.Activate(runtimeId)) return;
            Thread.Sleep(100);
        }
        throw new Exception("Could not prepare tab content for measurement: " + runtimeId);
    }
}
