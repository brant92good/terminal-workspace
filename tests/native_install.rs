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
    let local_data = tempfile::tempdir().unwrap();
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
        .env("LOCALAPPDATA", local_data.path())
        .creation_flags(0x08000000)
        .output()
        .unwrap()
}

#[test]
#[ignore = "Set WORKSPACE_TEST_BUNDLE to the actual release ZIP and run explicitly"]
fn legacy_owned_bootstrap_migrates_preferences_and_preserves_originals() {
    let archive = PathBuf::from(
        std::env::var_os("WORKSPACE_TEST_BUNDLE").expect("WORKSPACE_TEST_BUNDLE is required"),
    );
    let checksum = format!("{:x}", Sha256::digest(fs::read(&archive).unwrap()));
    let script = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("scripts/install-native.ps1");
    let sandbox = tempfile::tempdir().unwrap();
    let legacy = sandbox.path().join("old bootstrap 測試");
    let commit = "a".repeat(40);
    let source = legacy
        .join("downloads")
        .join(format!("terminal-workspace-{commit}"));
    fs::create_dir_all(source.join("config")).unwrap();
    fs::write(legacy.join(".workspace-installer"), b"terminal-workspace").unwrap();
    fs::write(source.join(".download-complete"), &commit).unwrap();
    let current = serde_json::to_vec(&json!({"workspace":source,"commit":commit})).unwrap();
    fs::write(legacy.join("current.json"), &current).unwrap();
    let preferences = b"{ /* keep exact bytes */ \"session_picker\":true,\"integration_only\":true,\"remote_client\":\"herdr\",\"herdr\":\"Z:/old-herdr.exe\",\"custom\":\"keep\",\"shortcuts\":{\"newTab\":\"ctrl+n\"}}";
    fs::write(source.join(".machine.json"), preferences).unwrap();
    let mut shared: Value = serde_json::from_str(include_str!("../config/terminal.json")).unwrap();
    shared["terminal"]["theme"] = json!("light");
    let shared = serde_json::to_vec(&shared).unwrap();
    fs::write(source.join("config/terminal.json"), &shared).unwrap();
    let destination = sandbox.path().join("new native O'Brien");
    let mut arguments = vec![
        "-InstallDir".into(),
        destination.to_string_lossy().into_owned(),
        "-Bundle".into(),
        archive.to_string_lossy().into_owned(),
        "-Sha256".into(),
        checksum,
        "-NoConfigure".into(),
        "-NoShortcuts".into(),
        "-LegacyInstallDir".into(),
        legacy.to_string_lossy().into_owned(),
    ];
    check(run(&script, &arguments));
    assert_eq!(
        fs::read(destination.join(".machine.json")).unwrap(),
        preferences
    );
    assert_eq!(
        fs::read(destination.join("config/terminal.json")).unwrap(),
        shared
    );
    assert_eq!(fs::read(legacy.join("current.json")).unwrap(), current);
    assert_eq!(fs::read(source.join(".machine.json")).unwrap(), preferences);
    let backup = fs::read_dir(destination.join("migration"))
        .unwrap()
        .next()
        .unwrap()
        .unwrap()
        .path();
    assert_eq!(fs::read(backup.join("current.json")).unwrap(), current);
    assert_eq!(fs::read(backup.join(".machine.json")).unwrap(), preferences);
    let changed =
        b"{\"integration_only\":true,\"remote_client\":\"ssh\",\"custom\":\"new native settings\"}";
    fs::write(destination.join(".machine.json"), changed).unwrap();
    check(run(&script, &arguments));
    assert_eq!(
        fs::read(destination.join(".machine.json")).unwrap(),
        changed
    );
    // Recorded paths cannot redirect import to another checkout, even one we own.
    fs::write(
        legacy.join("current.json"),
        serde_json::to_vec(&json!({"workspace":sandbox.path(),"commit":commit})).unwrap(),
    )
    .unwrap();
    let rejected = sandbox.path().join("bad destination");
    arguments[1] = rejected.to_string_lossy().into_owned();
    assert!(!run(&script, &arguments).status.success());
    assert!(!rejected.exists());
    fs::write(legacy.join("current.json"), &current).unwrap();
    fs::write(source.join(".machine.json"), b"{\"shortcuts\":42}").unwrap();
    assert!(!run(&script, &arguments).status.success());
    assert!(!rejected.exists());
    assert_eq!(
        fs::read(source.join(".machine.json")).unwrap(),
        b"{\"shortcuts\":42}"
    );
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
