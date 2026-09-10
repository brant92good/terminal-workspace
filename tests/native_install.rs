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
    let powershell = PathBuf::from(std::env::var_os("SystemRoot").unwrap())
        .join("System32/WindowsPowerShell/v1.0/powershell.exe");
    run_shell(&powershell, script, args)
}
fn run_shell(powershell: &Path, script: &Path, args: &[String]) -> Output {
    use std::os::windows::process::CommandExt;
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
    files_bundle::verify_installed(&destination, sandbox.path());
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
    files_bundle::reject_incomplete_update(&script, &arguments, &destination, sandbox.path());
    assert!(destination.join("scripts/invoke-native.ps1").is_file());
    let wrapper_data = sandbox.path().join("wrapper catalog space");
    for (index, name) in [
        "\u{958b}\u{767c}\u{1f680}",
        "He said \"hello\"",
        "space and trailing slash\\",
        "",
    ]
    .iter()
    .enumerate()
    {
        let target = format!("wrapper-{index}.invalid");
        let output = run(
            &destination.join("ports.ps1"),
            &[
                "--data-dir".into(),
                format!("{}\\", wrapper_data.display()),
                "machines".into(),
                "add".into(),
                target.clone(),
                "--name".into(),
                (*name).into(),
                "--json".into(),
            ],
        );
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let result: Value = serde_json::from_slice(&output.stdout).unwrap();
        assert_eq!(
            result["machine"]["name"],
            if name.is_empty() {
                target.as_str()
            } else {
                *name
            }
        );
    }
    let session_catalog = sandbox.path().join("session catalog.json");
    fs::write(
        &session_catalog,
        serde_json::to_vec(&json!({"version":2,"machines":[{
            "id":"wrapper","name":"Fixture","user":"u","group":"Old",
            "routes":[{"id":"direct","name":"Direct","host":"fixture.invalid","port":22}]
        }]}))
        .unwrap(),
    )
    .unwrap();
    let group = "He said \"hello\"";
    check(run(
        &destination.join("sessions.ps1"),
        &[
            "--catalog".into(),
            session_catalog.to_string_lossy().into_owned(),
            "groups".into(),
            "rename".into(),
            "Old".into(),
            group.into(),
            "--json".into(),
        ],
    ));
    let catalog: Value = serde_json::from_slice(&fs::read(session_catalog).unwrap()).unwrap();
    assert_eq!(catalog["machines"][0]["group"], group);
    let pipeline_script = destination.join("pipeline-check.ps1");
    fs::write(&pipeline_script, br#"param([string]$Data,[string]$Catalog)
$ErrorActionPreference = 'Stop'
$ports = & (Join-Path $PSScriptRoot 'ports.ps1') --data-dir $Data machines list --json | ConvertFrom-Json
$sessions = & (Join-Path $PSScriptRoot 'sessions.ps1') --catalog $Catalog list --json | ConvertFrom-Json
if (-not $ports.ok -or -not $sessions.ok) { throw 'Native JSON bypassed the PowerShell pipeline.' }
$unicode = [string][char]0x958b + [char]0x767c + [char]::ConvertFromUtf32(0x1f680)
if (@($ports.machines | Where-Object { $_.name -ceq $unicode }).Count -ne 1) { throw 'Unicode was lost in the PowerShell pipeline.' }
[PSCustomObject]@{ok=$true;ports=@($ports.machines).Count;sessions=@($sessions.machines).Count} | ConvertTo-Json
"#).unwrap();
    let pipeline_args = [
        "-Data".into(),
        wrapper_data.to_string_lossy().into_owned(),
        "-Catalog".into(),
        sandbox
            .path()
            .join("session catalog.json")
            .to_string_lossy()
            .into_owned(),
    ];
    for shell in [
        PathBuf::from(std::env::var_os("SystemRoot").unwrap())
            .join("System32/WindowsPowerShell/v1.0/powershell.exe"),
        std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default())
            .map(|p| p.join("pwsh.exe"))
            .find(|p| p.is_file())
            .expect("PowerShell 7 is required for the opt-in wrapper gate"),
    ] {
        if !shell.is_file() {
            continue;
        }
        let pipeline = run_shell(&shell, &pipeline_script, &pipeline_args);
        assert!(
            pipeline.status.success(),
            "{}",
            String::from_utf8_lossy(&pipeline.stderr)
        );
        let pipeline: Value = serde_json::from_slice(&pipeline.stdout).unwrap();
        assert_eq!(pipeline["ports"], 4);
        assert_eq!(pipeline["sessions"], 1);
    }
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

#[path = "support/wrapper.rs"]
mod wrapper;

#[path = "support/files_bundle.rs"]
mod files_bundle;
