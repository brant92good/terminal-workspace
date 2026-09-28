#![cfg(windows)]
use serde_json::{Value, json};
use std::{fs, path::Path, process::Command};
use terminal_workspace::{
    launch, preview,
    settings::{self, Preferences},
};
fn fixture(root: &Path) -> (std::path::PathBuf, std::path::PathBuf) {
    let exe = root.join("ports audio ; preview.exe");
    fs::write(&exe, b"unused by renderer").unwrap();
    let data = root.join("beta data ; isolated");
    fs::create_dir_all(&data).unwrap();
    fs::write(data.join(".ports-channel"), b"beta\n").unwrap();
    fs::write(
        root.join("ports-preview.json"),
        serde_json::to_vec(&json!({"schema_version":1,"executable":exe,"data_directory":data}))
            .unwrap(),
    )
    .unwrap();
    (exe, data)
}
#[test]
fn preview_settings_and_paired_tabs_agree_without_changing_new_tabs() {
    let temp = tempfile::tempdir().unwrap();
    let root = temp.path();
    let (exe, data) = fixture(root);
    let prefs = Preferences::read(&json!({"session_picker":true,"local_herdr":true})).unwrap();
    let shared: Value = serde_json::from_str(include_str!("../config/terminal.json")).unwrap();
    let rendered = settings::render(
        &json!({"initialPosition":"-2080,80","centerOnLaunch":true}),
        &shared,
        root,
        &prefs,
    )
    .unwrap();
    assert_eq!(rendered["defaultProfile"], settings::SESSIONS);
    assert_eq!(rendered["initialPosition"], "-2080,80");
    let profile = rendered["profiles"]["list"]
        .as_array()
        .unwrap()
        .iter()
        .find(|v| v["guid"] == settings::PORTS)
        .unwrap();
    let line = profile["commandline"].as_str().unwrap();
    assert!(line.contains("ports audio ; preview.exe"));
    assert!(line.contains("--data-dir"));
    let action = rendered["actions"]
        .as_array()
        .unwrap()
        .iter()
        .find(|v| v["id"] == "User.TerminalWorkspace.Ports")
        .unwrap();
    assert!(
        action["command"]["commandline"]
            .as_str()
            .unwrap()
            .contains(line)
    );
    let machine = launch::Machine {
        id: "fixture".into(),
        name: "Fixture".into(),
        target: "fixture.invalid".into(),
        directory: data.clone(),
        ssh_port: None,
        ssh_config: None,
    };
    let argv = launch::tab_arguments(root, "window", &machine, &data, &prefs).unwrap();
    assert!(argv.contains(&exe.to_string_lossy().replace(';', "\\;")));
    assert_eq!(&argv[argv.len() - 4..], &[";", "focus-tab", "-t", "0"]);
    assert_eq!(preview::directory(root, None).unwrap(), data);
    assert!(preview::directory(root, Some(root.into())).is_err());
    fs::write(data.join(".ports-channel"), b"stable\n").unwrap();
    assert!(preview::load(root).is_err());
}
#[test]
fn actual_preview_selector_uses_schema_two_and_explicit_machine_without_ssh() {
    let Some(exe) = std::env::var_os("WORKSPACE_PREVIEW_PORTS") else {
        return;
    };
    let exe = std::path::PathBuf::from(exe);
    let temp = tempfile::tempdir().unwrap();
    let root = temp.path();
    let data = root.join("isolated");
    fs::create_dir(&data).unwrap();
    fs::write(data.join(".ports-channel"), b"beta\n").unwrap();
    fs::write(
        root.join("ports-preview.json"),
        serde_json::to_vec(&json!({"schema_version":1,"executable":exe,"data_directory":data}))
            .unwrap(),
    )
    .unwrap();
    let result = Command::new(&exe)
        .arg("--data-dir")
        .arg(&data)
        .args(["machines", "add", "fixture.invalid", "--json"])
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let parsed: Value = serde_json::from_slice(&result.stdout).unwrap();
    let id = parsed["machine"]["id"].as_str().unwrap();
    let picked = launch::select(root, &data, Some(id), false, false)
        .unwrap()
        .unwrap();
    assert_eq!(picked.id, id);
    assert_eq!(picked.target, "fixture.invalid");
    let result = Command::new(env!("CARGO_BIN_EXE_terminal-workspace"))
        .arg("--root")
        .arg(root)
        .args(["ports", "--", "--json", "machines", "list"])
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let parsed: Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(parsed["schema_version"], 2);
    assert_eq!(parsed["channel"], "beta");
    assert!(!data.join("audio-state.json").exists());
    assert!(!data.join("endpoint.json").exists());
}

#[test]
fn stable_selection_refuses_beta_marker_and_preview_pair_changes() {
    let temp = tempfile::tempdir().unwrap();
    let root = temp.path();
    let (_exe, data) = fixture(root);
    let other = root.join("other");
    fs::create_dir(&other).unwrap();
    assert!(preview::selected(root, &other).is_err());
    fs::remove_file(root.join("ports-preview.json")).unwrap();
    assert!(preview::directory(root, Some(data.clone())).is_err());
    assert!(preview::selected(root, &data).is_err());
    let child = data.join("machines/child");
    fs::create_dir_all(&child).unwrap();
    assert!(preview::directory(root, Some(child)).is_err());
    assert!(preview::selected(root, &other).is_ok());
}
