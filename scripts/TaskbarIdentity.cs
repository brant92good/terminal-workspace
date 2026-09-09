// Give only explicitly launched workspace windows their own taskbar group.
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Automation;

public static class TaskbarIdentity {
    public const string AppId = "TerminalWorkspace.Desktop";

    [StructLayout(LayoutKind.Sequential)] public struct PropertyKey {
        public Guid format;
        public uint id;
        public PropertyKey(uint value) {
            format = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"); id = value;
        }
    }
    // PROPVARIANT has an eight-byte header and a pointer-sized payload.
    // The largest 64-bit variant occupies 24 bytes; this assembly runs as x64.
    [StructLayout(LayoutKind.Explicit, Size = 24)] public struct PropertyValue {
        [FieldOffset(0)] public ushort type;
        [FieldOffset(8)] public IntPtr text;
    }
    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface PropertyStore {
        [PreserveSig] int GetCount(out uint count);
        [PreserveSig] int GetAt(uint index, out PropertyKey key);
        [PreserveSig] int GetValue(ref PropertyKey key, out PropertyValue value);
        [PreserveSig] int SetValue(ref PropertyKey key, ref PropertyValue value);
        [PreserveSig] int Commit();
    }
    [DllImport("shell32.dll")] static extern int SHGetPropertyStoreForWindow(IntPtr window, ref Guid iid, out PropertyStore store);
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)] static extern int SHGetPropertyStoreFromParsingName(string path, IntPtr bind, uint flags, ref Guid iid, out PropertyStore store);
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)] static extern void SHChangeNotify(uint eventId, uint flags, string path, IntPtr unused);
    [DllImport("ole32.dll")] static extern int PropVariantClear(ref PropertyValue value);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr window, StringBuilder name, int count);

    static PropertyStore ForWindow(IntPtr window) {
        var iid = typeof(PropertyStore).GUID;
        PropertyStore store;
        Marshal.ThrowExceptionForHR(SHGetPropertyStoreForWindow(window, ref iid, out store));
        return store;
    }
    static PropertyStore ForShortcut(string path, bool write) {
        if (!File.Exists(path) || !String.Equals(Path.GetExtension(path), ".lnk", StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("Expected an existing shortcut.");
        var iid = typeof(PropertyStore).GUID;
        PropertyStore store;
        Marshal.ThrowExceptionForHR(SHGetPropertyStoreFromParsingName(Path.GetFullPath(path), IntPtr.Zero, write ? 2U : 0U, ref iid, out store));
        return store;
    }
    static string Read(PropertyStore store, uint id) {
        var key = new PropertyKey(id);
        var value = new PropertyValue();
        try {
            Marshal.ThrowExceptionForHR(store.GetValue(ref key, out value));
            if (value.type == 0) return null;
            if (value.type != 31) throw new InvalidOperationException("Unexpected taskbar property type.");
            return Marshal.PtrToStringUni(value.text);
        } finally { PropVariantClear(ref value); }
    }
    static void Write(PropertyStore store, uint id, string text) {
        var key = new PropertyKey(id);
        var value = new PropertyValue();
        if (text != null) { value.type = 31; value.text = Marshal.StringToCoTaskMemUni(text); }
        try { Marshal.ThrowExceptionForHR(store.SetValue(ref key, ref value)); }
        finally { PropVariantClear(ref value); }
    }
    public static string ReadShortcut(string path) {
        var store = ForShortcut(path, false);
        try { return Read(store, 5); } finally { Marshal.ReleaseComObject(store); }
    }
    public static void RegisterShortcut(string path) {
        var store = ForShortcut(path, true);
        try {
            Write(store, 5, AppId);
            Marshal.ThrowExceptionForHR(store.Commit());
        } finally { Marshal.ReleaseComObject(store); }
        SHChangeNotify(0x2000, 0x0005, Path.GetFullPath(path), IntPtr.Zero);
        if (ReadShortcut(path) != AppId) throw new IOException("Shortcut identity was not saved.");
    }
    public static string ReadWindow(IntPtr window, uint property) {
        var store = ForWindow(window);
        try { return Read(store, property); } finally { Marshal.ReleaseComObject(store); }
    }
    // This low-level method is also exercised on a hidden test-owned window.
    public static void ApplyWindow(IntPtr window, string launcher) {
        var store = ForWindow(window);
        var previous = new Dictionary<uint, string>();
        var ids = new uint[] { 2, 3, 4, 5 };
        try {
            foreach (var id in ids) previous[id] = Read(store, id);
            try {
                // Relaunch metadata also covers a newly pinned running window.
                Write(store, 2, "\"" + Path.GetFullPath(launcher) + "\"");
                Write(store, 3, Path.GetFullPath(launcher) + ",0");
                Write(store, 4, "Terminal Workspace");
                Write(store, 5, AppId); // Set identity last, after its icon/command.
                if (Read(store, 5) != AppId) throw new IOException("Window identity was not applied.");
            } catch {
                foreach (var id in ids) Write(store, id, previous[id]);
                throw;
            }
        } finally { Marshal.ReleaseComObject(store); }
    }
    public static void IdentifyOrigin(string title, string launcher) {
        if (!title.StartsWith("Shortcut | ", StringComparison.Ordinal) || title.Length != 43)
            throw new ArgumentException("Expected a unique launcher marker.");
        Guid token;
        if (!Guid.TryParseExact(title.Substring(11), "N", out token))
            throw new ArgumentException("Invalid launcher marker.");
        var deadline = DateTime.UtcNow.AddSeconds(4);
        while (DateTime.UtcNow < deadline) {
            var matches = new List<AutomationElement>();
            var windows = AutomationElement.RootElement.FindAll(TreeScope.Children,
                new PropertyCondition(AutomationElement.ClassNameProperty, "CASCADIA_HOSTING_WINDOW_CLASS"));
            foreach (AutomationElement window in windows) {
                try {
                    var tabs = window.FindAll(TreeScope.Descendants, new AndCondition(
                        new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.TabItem),
                        new PropertyCondition(AutomationElement.NameProperty, title)));
                    foreach (AutomationElement tab in tabs) matches.Add(window);
                } catch (ElementNotAvailableException) { }
            }
            if (matches.Count > 1) throw new InvalidOperationException("Ambiguous workspace window; identity unchanged.");
            if (matches.Count == 1) {
                var window = matches[0];
                var handle = new IntPtr(window.Current.NativeWindowHandle);
                var name = new StringBuilder(100);
                GetClassName(handle, name, name.Capacity);
                if (name.ToString() != "CASCADIA_HOSTING_WINDOW_CLASS")
                    throw new InvalidOperationException("Workspace window no longer exists.");
                // Resolve again immediately before writing; never infer from foreground.
                if (window.FindAll(TreeScope.Descendants, new AndCondition(
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.TabItem),
                    new PropertyCondition(AutomationElement.NameProperty, title))).Count != 1)
                    throw new InvalidOperationException("Workspace marker changed; identity unchanged.");
                ApplyWindow(handle, launcher);
                return;
            }
            Thread.Sleep(50);
        }
        throw new TimeoutException("Could not identify the workspace window; ordinary Terminal grouping retained.");
    }
}
