using System;
using System.Diagnostics;
using System.Windows.Forms;

public static class WorkspaceLauncher {
    [STAThread]
    public static void Main() {
        try {
            Process.Start(new ProcessStartInfo {
                FileName = "wt.exe",
                Arguments = "-w new new-tab -p \"{a9a0b421-7dd6-4425-9843-59b5f5d6c2d1}\" ; " +
                    "new-tab -p \"{5e483274-6f37-40d5-b42b-1eaef7f9da82}\" ; focus-tab -t 0",
                UseShellExecute = true
            });
        } catch (Exception error) {
            MessageBox.Show(error.Message, "Terminal Workspace", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
