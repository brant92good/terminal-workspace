//! A first mutation must return EOF to a capturing shell while its daemon lives.
#![cfg(windows)]

use port_forward_tui::{background, machines::Catalog};
use serde_json::{Value, json};
use std::{
    ffi::OsString,
    io::{Read, Write},
    os::windows::process::CommandExt,
    path::Path,
    process::{Command, Stdio},
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};
static CAPTURE_PROCESS: std::sync::Mutex<()> = std::sync::Mutex::new(());

fn capture(
    executable: &Path,
    prefix: &[OsString],
    directory: &Path,
    args: &[&str],
) -> (bool, bool, bool, Value) {
    let mut child = Command::new(executable)
        .args(prefix)
        .arg("--data-dir")
        .arg(directory)
        .arg("--json")
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .creation_flags(0x08000000)
        .spawn()
        .unwrap();
    let mut input = child.stdin.take().unwrap();
    let (sender, receiver) = mpsc::channel();
    for (name, mut stream) in [
        (
            "stdout",
            Box::new(child.stdout.take().unwrap()) as Box<dyn Read + Send>,
        ),
        (
            "stderr",
            Box::new(child.stderr.take().unwrap()) as Box<dyn Read + Send>,
        ),
    ] {
        let sender = sender.clone();
        thread::spawn(move || {
            let mut bytes = Vec::new();
            let result = stream.read_to_end(&mut bytes);
            let _ = sender.send((name, result, bytes));
        });
    }
    drop(sender);
    let deadline = Instant::now() + Duration::from_secs(10);
    let exited = loop {
        if let Some(status) = child.try_wait().unwrap() {
            break status.success();
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            break false;
        }
        thread::sleep(Duration::from_millis(10));
    };
    // EOF is checked before shutting down the daemon. Reading directly here
    // would hang the regression itself on the bug it is meant to detect.
    let mut captured = Vec::new();
    for _ in 0..2 {
        if let Ok(value) = receiver.recv_timeout(Duration::from_millis(500)) {
            captured.push(value);
        }
    }
    let eof = captured.len() == 2 && captured.iter().all(|(_, result, _)| result.is_ok());
    let stdin_closed = input.write_all(b"no inherited reader").is_err();
    let output = captured
        .iter()
        .find(|(name, _, _)| *name == "stdout")
        .and_then(|(_, _, bytes)| serde_json::from_slice(bytes).ok())
        .unwrap_or(Value::Null);
    (exited, eof, stdin_closed, output)
}

struct ControllerCleanup(std::path::PathBuf);
impl Drop for ControllerCleanup {
    fn drop(&mut self) {
        // Authenticated endpoint inside this newly-created fixture only.
        let _ = background::exchange(&self.0, "shutdown", json!({}), Duration::from_secs(2));
    }
}

fn run_case(shell: Option<&str>) {
    // Keep one captured process chain active so unrelated sibling fixtures
    // cannot change the observed Windows handle lifetime under load.
    let _serial = CAPTURE_PROCESS
        .lock()
        .unwrap_or_else(|error| error.into_inner());
    let temporary = tempfile::tempdir().unwrap();
    let archive =
        std::env::var_os("WORKSPACE_TEST_BUNDLE").expect("WORKSPACE_TEST_BUNDLE is required");
    let install = temporary.path().join("bundle");
    let unpack = temporary.path().join("unpack.ps1");
    std::fs::write(&unpack, b"param([string]$Archive,[string]$Destination)\nAdd-Type -AssemblyName System.IO.Compression.FileSystem\n[IO.Compression.ZipFile]::ExtractToDirectory($Archive,$Destination)\n").unwrap();
    let extraction = Command::new("powershell.exe")
        .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
        .arg(&unpack)
        .arg(archive)
        .arg(&install)
        .creation_flags(0x08000000)
        .output()
        .unwrap();
    assert!(
        extraction.status.success(),
        "{}",
        String::from_utf8_lossy(&extraction.stderr)
    );
    let (executable, prefix) = match shell {
        Some(name) => (
            which::which(name).expect("Both PowerShell versions are required"),
            vec![
                OsString::from("-NoProfile"),
                OsString::from("-ExecutionPolicy"),
                OsString::from("Bypass"),
                OsString::from("-File"),
                install.join("ports.ps1").into_os_string(),
            ],
        ),
        None => (install.join("bin/ports.exe"), Vec::new()),
    };
    let catalog = Catalog::new(temporary.path()).unwrap();
    let machine = catalog
        .add("capture-fixture.invalid", "Capture fixture", None, None)
        .unwrap();
    let _cleanup = ControllerCleanup(machine.directory.clone());
    let first = capture(
        &executable,
        &prefix,
        temporary.path(),
        &[
            "--machine",
            &machine.id,
            "save",
            "--remote",
            "18763",
            "--name",
            "Capture",
        ],
    );
    let first_live = background::exchange(
        &machine.directory,
        "status",
        json!({}),
        Duration::from_secs(2),
    );
    let restart = if first.0 && first.1 && first.2 {
        Some(capture(
            &executable,
            &prefix,
            temporary.path(),
            &["--machine", &machine.id, "restart-manager"],
        ))
    } else {
        None
    };
    let final_live = background::exchange(
        &machine.directory,
        "status",
        json!({}),
        Duration::from_secs(2),
    );
    let cleanup = background::exchange(
        &machine.directory,
        "shutdown",
        json!({}),
        Duration::from_secs(2),
    );
    let deadline = Instant::now() + Duration::from_secs(5);
    while machine.directory.join("endpoint.json").exists() && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(20));
    }
    assert!(
        cleanup.is_ok() && !machine.directory.join("endpoint.json").exists(),
        "owned daemon cleanup failed; first={first:?}; first_live={first_live:?}; cleanup={cleanup:?}"
    );
    assert!(
        first_live.is_ok() && final_live.is_ok(),
        "daemon must remain live after each CLI exits"
    );
    assert!(first.0, "first save failed");
    assert!(
        first.1,
        "first save exited but its daemon retained captured stdout/stderr"
    );
    assert!(first.2, "first save's daemon retained captured stdin");
    assert_eq!(first.3["ok"], true);
    let restart = restart.unwrap();
    assert!(
        restart.0 && restart.1 && restart.2,
        "restart must release all incoming standard handles"
    );
    assert_eq!(restart.3["ok"], true);
    assert_ne!(first_live.unwrap()["pid"], final_live.unwrap()["pid"]);
}

#[test]
#[ignore = "Run directly outside Cargo's non-breakaway Windows job"]
fn released_binary_captured_save_and_restart() {
    run_case(None);
}
#[test]
#[ignore = "Run directly outside Cargo's non-breakaway Windows job"]
fn packaged_powershell51_wrapper_captured_save_and_restart() {
    run_case(Some("powershell.exe"));
}
#[test]
#[ignore = "Run directly outside Cargo's non-breakaway Windows job"]
fn packaged_powershell7_wrapper_captured_save_and_restart() {
    run_case(Some("pwsh.exe"));
}
