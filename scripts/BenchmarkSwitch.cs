using System;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Automation;

public static class BenchmarkSwitch {
    [DllImport("user32.dll")] static extern void keybd_event(byte key, byte scan, uint flags, UIntPtr extra);

    public static string Run(string targetId, string sourceId, int count) {
        var target = TerminalViews.Tabs().First(t => t.runtime_id == targetId);
        var selection = (SelectionItemPattern)target.element.GetCurrentPattern(SelectionItemPattern.Pattern);
        var samples = new double[count];
        for (int i = 0; i < count; i++) {
            if (!TerminalViews.Activate(targetId)) throw new Exception("Could not prime target focus");
            Thread.Sleep(120);
            if (!TerminalViews.Activate(sourceId)) throw new Exception("Could not focus source");
            Thread.Sleep(120);
            var clock = Stopwatch.StartNew();
            try {
                keybd_event(0x11, 0, 0, UIntPtr.Zero);
                keybd_event(0x12, 0, 0, UIntPtr.Zero);
                keybd_event(0x50, 0, 0, UIntPtr.Zero);
                Thread.Sleep(20);
            } finally {
                keybd_event(0x50, 0, 2, UIntPtr.Zero);
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
            samples[i] = clock.Elapsed.TotalMilliseconds;
            // The old helper can still be pending after Terminal momentarily
            // restores an adjacent tab. Keep it out of the following sample.
            Thread.Sleep(1000);
        }
        return new JavaScriptSerializer().Serialize(samples);
    }
}
