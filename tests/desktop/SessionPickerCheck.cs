using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Automation;

public static class SessionPickerCheck {
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern void keybd_event(byte key, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32.dll", SetLastError=true)] static extern uint SendInput(uint count, Input[] input, int size);
    [StructLayout(LayoutKind.Sequential)] struct Keyboard { public ushort key, scan; public uint flags, time; public UIntPtr extra; }
    [StructLayout(LayoutKind.Explicit, Size=32)] struct Union { [FieldOffset(0)] public Keyboard keyboard; }
    [StructLayout(LayoutKind.Sequential)] struct Input { public uint type; public Union data; }

    static void Guard(long window) {
        if (GetForegroundWindow().ToInt64() != window)
            throw new Exception("Test stopped: another app has focus; no activation attempted");
    }

    public static void Press(long window, string name) {
        Guard(window);
        byte[] keys = name == "newTab" ? new byte[] {0x11,0x10,0x54} :
                      name == "local" ? new byte[] {0x11,0x12,0x4e} : new byte[] {0x0d};
        try {
            foreach (var key in keys) { Guard(window); keybd_event(key,0,0,UIntPtr.Zero); }
            Thread.Sleep(30);
        } finally {
            for (int i=keys.Length-1;i>=0;i--) keybd_event(keys[i],0,2,UIntPtr.Zero);
        }
    }

    public static void Type(long window, string text) {
        foreach (char character in text) {
            Guard(window);
            var input = new Input[2];
            input[0].type = input[1].type = 1;
            input[0].data.keyboard.scan = input[1].data.keyboard.scan = character;
            input[0].data.keyboard.flags = 4;
            input[1].data.keyboard.flags = 6;
            if (SendInput(2,input,Marshal.SizeOf(typeof(Input))) != 2)
                throw new Exception("Could not type into owned test window");
        }
    }

    public static bool HasText(long window, string expected) {
        Guard(window);
        var root = AutomationElement.FromHandle(new IntPtr(window));
        var elements = root.FindAll(TreeScope.Descendants, new AndCondition(
            new PropertyCondition(AutomationElement.ControlTypeProperty,ControlType.Text),
            new PropertyCondition(AutomationElement.IsOffscreenProperty,false)));
        foreach (AutomationElement element in elements) {
            object pattern;
            if (element.TryGetCurrentPattern(TextPattern.Pattern,out pattern) &&
                ((TextPattern)pattern).DocumentRange.GetText(-1).Contains(expected)) return true;
        }
        return false;
    }
}
