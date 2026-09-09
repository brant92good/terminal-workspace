use portable_pty::{CommandBuilder, PtySize, native_pty_system};
use std::{
    fs,
    io::{Read, Write},
    path::PathBuf,
    process::Command,
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};

struct Child(Box<dyn portable_pty::Child + Send + Sync>);
impl Drop for Child {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

#[test]
#[ignore = "Set WORKSPACE_TEST_BUNDLE to the actual release ZIP and run explicitly"]
fn packaged_wrappers_preserve_console_and_interactive_json_pipeline() {
    let archive = PathBuf::from(
        std::env::var_os("WORKSPACE_TEST_BUNDLE").expect("WORKSPACE_TEST_BUNDLE is required"),
    );
    let fixture = tempfile::tempdir().unwrap();
    let unzip = fixture.path().join("unzip.ps1");
    fs::write(&unzip, b"param([string]$Archive,[string]$Destination)\nAdd-Type -AssemblyName System.IO.Compression.FileSystem\n[IO.Compression.ZipFile]::ExtractToDirectory($Archive,$Destination)\n").unwrap();
    let root = fixture.path().join("bundle");
    super::check(super::run(
        &unzip,
        &[
            archive.to_string_lossy().into_owned(),
            root.to_string_lossy().into_owned(),
        ],
    ));
    let ports = root.join("bin/ports.exe");
    let data = root.join("data");
    for target in ["fixture.invalid", "second.invalid"] {
        let added = Command::new(&ports)
            .arg("--data-dir")
            .arg(&data)
            .args(["machines", "add", target, "--json"])
            .output()
            .unwrap();
        super::check(added);
    }
    let picker = root.join("pick-pipeline.ps1");
    fs::write(&picker, br#"$ErrorActionPreference = 'Stop'
$value = & (Join-Path $PSScriptRoot 'ports.ps1') --data-dir (Join-Path $PSScriptRoot 'data') machines pick --json | ConvertFrom-Json
if (-not $value.ok -or $value.machine.target -ne 'fixture.invalid') { throw 'Interactive JSON did not reach the PowerShell pipeline.' }
Write-Output 'PICKED:fixture.invalid'
"#).unwrap();
    for shell in [
        PathBuf::from(std::env::var_os("SystemRoot").unwrap())
            .join("System32/WindowsPowerShell/v1.0/powershell.exe"),
        PathBuf::from("pwsh.exe"),
    ] {
        for pick in [false, true] {
            let pair = native_pty_system()
                .openpty(PtySize {
                    rows: 32,
                    cols: 120,
                    pixel_width: 0,
                    pixel_height: 0,
                })
                .unwrap();
            let mut command = CommandBuilder::new(&shell);
            command.args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]);
            command.arg(if pick {
                picker.clone()
            } else {
                root.join("ports.ps1")
            });
            if !pick {
                command.args(["--foreground", "--machine", "fixture.invalid", "--data-dir"]);
                command.arg(&data);
            }
            command.env_remove("WT_SESSION");
            let mut child = Child(pair.slave.spawn_command(command).unwrap());
            let mut reader = pair.master.try_clone_reader().unwrap();
            let mut input = pair.master.take_writer().unwrap();
            let (sender, output) = mpsc::channel();
            thread::spawn(move || {
                let mut bytes = [0; 8192];
                while let Ok(count) = reader.read(&mut bytes) {
                    if count == 0 || sender.send(bytes[..count].to_vec()).is_err() {
                        break;
                    }
                }
            });
            let mut parser = vt100::Parser::new(32, 120, 0);
            let mut pending = Vec::new();
            let mut expect = |text: &str, absent: bool, input: &mut Box<dyn Write + Send>| {
                let deadline = Instant::now() + Duration::from_secs(10);
                loop {
                    if let Ok(bytes) = output.recv_timeout(Duration::from_millis(50)) {
                        parser.process(&bytes);
                        pending.extend_from_slice(&bytes);
                    }
                    if let Some(index) = pending.windows(4).position(|part| part == b"\x1b[6n") {
                        pending.drain(..index + 4);
                        input.write_all(b"\x1b[1;1R").unwrap();
                        input.flush().unwrap();
                    }
                    if parser.screen().contents().contains(text) != absent {
                        break;
                    }
                    assert!(
                        Instant::now() < deadline,
                        "Missing interactive state {text:?}, absent={absent}: {}",
                        parser.screen().contents()
                    );
                }
            };
            if pick {
                expect("Choose a machine for Ports", false, &mut input);
                input.write_all(b"\r").unwrap();
                input.flush().unwrap();
                expect("PICKED:fixture.invalid", false, &mut input);
            } else {
                expect("Saved connections", false, &mut input);
                input.write_all(b"a").unwrap();
                input.flush().unwrap();
                expect("Add favorite", false, &mut input);
                input.write_all(b"\x1b").unwrap();
                input.flush().unwrap();
                expect("Add favorite", true, &mut input);
                input.write_all(b"q").unwrap();
                input.flush().unwrap();
            }
            let deadline = Instant::now() + Duration::from_secs(5);
            loop {
                if let Some(status) = child.0.try_wait().unwrap() {
                    assert!(status.success(), "{status:?}");
                    break;
                }
                assert!(
                    Instant::now() < deadline,
                    "Wrapper did not return after TUI quit."
                );
                thread::sleep(Duration::from_millis(25));
            }
            drop(input);
            drop(pair);
        }
    }
}
