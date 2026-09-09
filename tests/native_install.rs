#![cfg(windows)]
//! Opt-in test of a real parent release bundle; never configures the desktop.
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Path, PathBuf},
    process::{Command, Output},
};

fn run(script: &Path, args: &[String]) -> Output {
    use std::os::windows::process::CommandExt;
    let powershell = PathBuf::from(std::env::var_os("SystemRoot").unwrap())
        .join("System32/WindowsPowerShell/v1.0/powershell.exe");
    Command::new(powershell)
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
        ])
        .arg(script)
        .args(args)
        .env("PYTHONHOME", "Z:/no-python-here")
        .env("PYTHONPATH", "Z:/no-packages-here")
        .env("CONDA_PREFIX", "Z:/no-conda-here")
        .env("VIRTUAL_ENV", "Z:/no-venv-here")
        .creation_flags(0x08000000)
        .output()
        .unwrap()
}
fn check(output: Output) {
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
#[ignore = "Set WORKSPACE_TEST_BUNDLE to the actual release ZIP and run explicitly"]
fn actual_bundle_fresh_update_integrity_ownership_and_settings() {
    let archive = PathBuf::from(
        std::env::var_os("WORKSPACE_TEST_BUNDLE").expect("WORKSPACE_TEST_BUNDLE is required"),
    );
    let checksum = format!("{:x}", Sha256::digest(fs::read(&archive).unwrap()));
    let project = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let script = project.join("scripts/install-native.ps1");
    let sandbox = tempfile::tempdir().unwrap();
    let destination = sandbox.path().join("space 測試 O'Brien");
    let arguments = vec![
        "-InstallDir".into(),
        destination.to_string_lossy().into_owned(),
        "-Bundle".into(),
        archive.to_string_lossy().into_owned(),
        "-Sha256".into(),
        checksum,
        "-NoConfigure".into(),
        "-NoShortcuts".into(),
    ];
    check(run(&script, &arguments));
    let executable = destination.join("bin/terminal-workspace.exe");
    assert!(executable.is_file());
    let preferences = json!({"integration_only":true,"session_picker":true,"shortcuts":{"newTab":"ctrl+n"},"custom":"preserve"});
    fs::write(
        destination.join(".machine.json"),
        serde_json::to_vec(&preferences).unwrap(),
    )
    .unwrap();
    fs::write(destination.join("notes.txt"), b"user data").unwrap();
    check(run(&script, &arguments));
    assert_eq!(
        fs::read(destination.join("notes.txt")).unwrap(),
        b"user data"
    );
    let after: Value =
        serde_json::from_slice(&fs::read(destination.join(".machine.json")).unwrap()).unwrap();
    assert_eq!(after, preferences);
    let before = fs::read(&executable).unwrap();
    let data = sandbox.path().join("ports-data");
    check(
        Command::new(destination.join("bin/ports.exe"))
            .args([
                "machines",
                "add",
                "demo.invalid",
                "--name",
                "Demo",
                "--data-dir",
            ])
            .arg(&data)
            .arg("--json")
            .output()
            .unwrap(),
    );
    let selected = terminal_workspace::launch::select(&destination, &data, None, false, false)
        .unwrap()
        .unwrap();
    assert_eq!(selected.target, "demo.invalid");
    assert!(selected.directory.is_absolute());
    let mut corrupt = arguments.clone();
    corrupt[5] = "0".repeat(64);
    assert!(!run(&script, &corrupt).status.success());
    assert_eq!(fs::read(&executable).unwrap(), before);
    let unowned = sandbox.path().join("unowned");
    fs::create_dir(&unowned).unwrap();
    fs::write(unowned.join("precious.txt"), b"keep").unwrap();
    let mut wrong = arguments.clone();
    wrong[1] = unowned.to_string_lossy().into_owned();
    assert!(!run(&script, &wrong).status.success());
    assert_eq!(fs::read(unowned.join("precious.txt")).unwrap(), b"keep");
    let terminal = sandbox.path().join("settings.json");
    fs::write(
        &terminal,
        b"{/*keep backup*/\"theme\":\"light\",\"profiles\":{\"list\":[]},}",
    )
    .unwrap();
    for _ in 0..2 {
        let result = Command::new(&executable)
            .args(["configure", "--root"])
            .arg(&destination)
            .arg("--settings")
            .arg(&terminal)
            .arg("--session-picker")
            .arg("--json")
            .output()
            .unwrap();
        check(result);
    }
    let settings: Value = serde_json::from_slice(&fs::read(&terminal).unwrap()).unwrap();
    assert_eq!(settings["theme"], "light");
    assert_eq!(
        settings["defaultProfile"],
        terminal_workspace::settings::SESSIONS
    );
    assert!(settings.to_string().contains("ssh-sessions.exe"));
    assert!(!settings.to_string().contains("python.exe"));
    let doctor = Command::new(&executable)
        .args(["doctor", "--root"])
        .arg(&destination)
        .arg("--json")
        .output()
        .unwrap();
    let doctor: Value = serde_json::from_slice(&doctor.stdout).unwrap();
    assert_eq!(doctor["schema_version"], 1);
    assert!(
        doctor["checks"]
            .as_array()
            .unwrap()
            .iter()
            .all(|c| !c["name"].as_str().unwrap_or("").contains("python"))
    );
}

#[test]
fn explorer_plan_keeps_modern_entry_and_default_profile_independent() {
    let script = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("scripts/explorer.ps1");
    let result = run(&script, &["-Plan".into()]);
    assert!(result.status.success());
    let plan: Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(plan["modernBuiltInChanged"], false);
    assert!(
        plan["command"]
            .as_str()
            .unwrap()
            .contains(terminal_workspace::settings::PWSH)
    );
    assert!(plan["command"].as_str().unwrap().contains("%V\\."));
    assert_eq!(plan["keys"].as_array().unwrap().len(), 3);
    assert!(
        plan["keys"]
            .as_array()
            .unwrap()
            .iter()
            .all(|v| v.as_str().unwrap().contains("TerminalWorkspace.PowerShell"))
    );
}

#[test]
fn invalid_native_arguments_have_json_error() {
    let output = Command::new(env!("CARGO_BIN_EXE_terminal-workspace"))
        .args(["--json", "missing-command"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    let data: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(data["error"]["code"], "invalid_arguments");
}
