// Use the Unicode Shell Link interface directly; WScript.Shell rejects some
// Unicode target paths on hosted Windows even when the executable exists.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

public static class WorkspaceShortcut {
    [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
    class ShellLink { }
    [ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IShellLinkW {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int count, IntPtr findData, uint flags);
        void GetIDList(out IntPtr items);
        void SetIDList(IntPtr items);
        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder text, int count);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string text);
        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int count);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string path);
        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder text, int count);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string text);
        void GetHotkey(out short key);
        void SetHotkey(short key);
        void GetShowCmd(out int command);
        void SetShowCmd(int command);
        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int count, out int index);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path, int index);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
        void Resolve(IntPtr window, uint flags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
    }

    public static void Create(string path, string launcher) {
        path = Path.GetFullPath(path);
        launcher = Path.GetFullPath(launcher);
        if (!String.Equals(Path.GetExtension(path), ".lnk", StringComparison.OrdinalIgnoreCase)
                || !Directory.Exists(Path.GetDirectoryName(path)) || !File.Exists(launcher))
            throw new ArgumentException("Expected a shortcut directory and an existing launcher.");
        var instance = new ShellLink();
        try {
            var link = (IShellLinkW)instance;
            link.SetPath(launcher);
            link.SetWorkingDirectory(Directory.GetParent(Path.GetDirectoryName(launcher)).FullName);
            link.SetArguments("");
            link.SetDescription("Open the remote workspace and Ports, with the remote tab selected");
            link.SetIconLocation(launcher, 0);
            link.SetShowCmd(1);
            ((IPersistFile)instance).Save(path, true);
        } finally { Marshal.ReleaseComObject(instance); }
        if (!String.Equals(ReadTarget(path), launcher, StringComparison.OrdinalIgnoreCase))
            throw new IOException("Shortcut target did not round-trip correctly.");
    }

    public static string ReadTarget(string path) {
        var instance = new ShellLink();
        try {
            ((IPersistFile)instance).Load(Path.GetFullPath(path), 0);
            var target = new StringBuilder(32768);
            // Read the saved path without resolution, prompts or network access.
            ((IShellLinkW)instance).GetPath(target, target.Capacity, IntPtr.Zero, 4);
            return target.ToString();
        } finally { Marshal.ReleaseComObject(instance); }
    }

    public static void RegisterMatchingPins(string directory, string launcher) {
        if (!Directory.Exists(directory)) return;
        foreach (var path in Directory.GetFiles(directory, "*.lnk")) {
            string target;
            try { target = ReadTarget(path); }
            catch (COMException) { continue; } // An unrelated malformed pin is not ours to repair.
            catch (IOException) { continue; }
            if (String.Equals(target, Path.GetFullPath(launcher), StringComparison.OrdinalIgnoreCase))
                TaskbarIdentity.RegisterShortcut(path);
        }
    }
}
