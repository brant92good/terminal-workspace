use serde_json::{Value, json};
use std::{fs, path::Path};
use terminal_workspace::{
    launch::{self, Machine},
    settings::{self, Preferences},
};

fn shared() -> Value {
    serde_json::from_str(include_str!("../config/terminal.json")).unwrap()
}
fn preferences() -> Preferences {
    Preferences::read(&json!({"session_picker":true,"local_herdr":true,"herdr":"C:/tools/herdr.exe","remote_client":"herdr","shortcuts":{"newTab":"ctrl+n"}})).unwrap()
}
#[test]
fn new_tab_contract_survives_updates_and_explicit_explorer_independence() {
    let source = json!({"profiles":{"list":[{"guid":"wsl","source":"Microsoft.WSL"},{"guid":"old"}]},"keybindings":[{"keys":"ctrl+shift+t","id":"new-tab"}],"actions":[{"id":"new-tab","command":"newTab"}]});
    let settings = settings::render(
        &source,
        &shared(),
        Path::new("C:/Workspace 測試"),
        &preferences(),
    )
    .unwrap();
    assert_eq!(settings["defaultProfile"], settings::SESSIONS);
    let actions = settings["actions"].as_array().unwrap();
    assert_eq!(
        actions
            .iter()
            .find(|a| a["id"] == settings::TAB_ACTION)
            .unwrap()["command"]["profile"],
        settings::SESSIONS
    );
    assert_eq!(
        actions
            .iter()
            .find(|a| a["id"] == settings::SHELL_ACTION)
            .unwrap()["command"]["profile"],
        settings::PWSH
    );
    assert!(
        settings["keybindings"]
            .as_array()
            .unwrap()
            .contains(&json!({"keys":"ctrl+shift+t","id":"new-tab"}))
    );
    assert_eq!(
        settings::render(
            &settings,
            &shared(),
            Path::new("C:/Workspace 測試"),
            &preferences()
        )
        .unwrap(),
        settings
    );
    for profile in settings["profiles"]["list"].as_array().unwrap() {
        assert!(
            !profile["commandline"]
                .as_str()
                .unwrap_or("")
                .contains("python")
        );
    }
}
#[test]
fn integration_only_preserves_unrelated_settings_but_explicit_picker_owns_default() {
    let source = json!({"theme":"light","defaultProfile":"custom","profiles":{"defaults":{"font":{"size":19}},"list":[{"guid":"custom","name":"My Shell"}]},"newTabMenu":[{"type":"separator"}]});
    let mut options = preferences();
    options.integration_only = true;
    let unchanged = settings::render(&source, &shared(), Path::new("C:/root"), &options).unwrap();
    for key in ["theme", "defaultProfile", "newTabMenu"] {
        assert_eq!(unchanged[key], source[key]);
    }
    assert_eq!(
        unchanged["profiles"]["defaults"],
        source["profiles"]["defaults"]
    );
    options.apply_default = true;
    let picker = settings::render(&source, &shared(), Path::new("C:/root"), &options).unwrap();
    assert_eq!(picker["defaultProfile"], settings::SESSIONS);
}
#[test]
fn collision_including_array_keys_is_rejected_without_mutation() {
    let original = json!({"keybindings":[{"id":"mine","keys":["Alt+Ctrl+P"]}]});
    let snapshot = original.clone();
    assert!(settings::render(&original, &shared(), Path::new("C:/root"), &preferences()).is_err());
    assert_eq!(original, snapshot);
}
#[test]
fn jsonc_handles_literal_comment_markers_and_rejects_extra_documents() {
    let source = br#"/*top*/{"url":"https://example.test/*literal*/","date":"2026-09-09","a":[1,2,],}// last"#;
    let parsed = settings::parse(source).unwrap();
    assert_eq!(parsed["url"], "https://example.test/*literal*/");
    assert_eq!(parsed["a"], json!([1, 2]));
    for source in [b"{} {}".as_slice(), b"[]", b"/* unclosed", b"{\"broken\":}"] {
        assert!(settings::parse(source).is_err());
    }
}
#[test]
fn settings_backup_and_concurrent_change_preservation() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("settings.json");
    let original = b"{ /* personal */ \"theme\":\"light\" }";
    fs::write(&path, original).unwrap();
    settings::write(&path, &json!({"theme":"dark"}), Some(original), true).unwrap();
    let backups: Vec<_> = fs::read_dir(dir.path())
        .unwrap()
        .flatten()
        .filter(|f| f.path().extension().is_some_and(|s| s == "bak"))
        .collect();
    assert_eq!(backups.len(), 1);
    assert_eq!(fs::read(backups[0].path()).unwrap(), original);
    assert!(settings::write(&path, &json!({}), Some(original), true).is_err());
    assert_eq!(settings::load(&path).unwrap()["theme"], "dark");
}
#[test]
fn export_drops_private_paths_and_argv() {
    let exported = settings::export(
        &json!({"startupActions":"private command","profiles":{"defaults":{"font":{"size":15},"startingDirectory":"C:/private"}},"theme":"light"}),
        &shared(),
    );
    assert_eq!(exported["profileDefaults"], json!({"font":{"size":15}}));
    assert!(!exported.to_string().contains("private"));
}
#[test]
fn session_commands_and_tab_composition_preserve_ids_and_override_fallback() {
    let mut machine = Machine {
        id: "stable-id".into(),
        name: "Demo".into(),
        target: "demo".into(),
        ssh_port: None,
        ssh_config: None,
        directory: "C:/data".into(),
    };
    assert_eq!(
        launch::session_arguments(Some(&machine), "herdr", "C:/herdr.exe").unwrap(),
        (
            "C:/herdr.exe".into(),
            vec!["--remote".into(), "demo".into()],
            true
        )
    );
    machine.ssh_port = Some(2222);
    machine.ssh_config = Some("C:/user config".into());
    let (executable, args, herdr) =
        launch::session_arguments(Some(&machine), "herdr", "C:/herdr.exe").unwrap();
    assert_eq!(executable, "ssh.exe");
    assert!(!herdr);
    assert_eq!(args, ["-p", "2222", "-F", "C:/user config", "demo"]);
    let arguments = launch::tab_arguments(
        Path::new("C:/root"),
        "unique-window",
        &machine.id,
        Path::new("C:/data"),
        &preferences(),
    );
    assert_eq!(
        &arguments[..6],
        [
            "-w",
            "unique-window",
            "new-tab",
            "-p",
            settings::PORTS,
            "C:/root\\bin\\ports.exe"
        ]
    );
    assert_eq!(
        &arguments[arguments.len() - 4..],
        [";", "focus-tab", "-t", "0"]
    );
    assert_eq!(
        arguments.iter().filter(|v| v.as_str() == "new-tab").count(),
        2
    );
}
#[test]
fn windows_quoting_handles_embedded_quotes_and_trailing_slashes() {
    assert_eq!(
        settings::quote("C:\\Program Files\\"),
        "\"C:\\Program Files\\\\\""
    );
    assert_eq!(settings::quote("a\"b"), "\"a\\\"b\"");
    assert_eq!(settings::quote(""), "\"\"");
}

#[test]
fn disabling_optional_key_overrides_shared_preference() {
    let mut shared = shared();
    shared["shortcuts"]["newTab"] = json!("ctrl+t");
    let prefs =
        Preferences::read(&json!({"session_picker":true,"shortcuts":{"newTab":null}})).unwrap();
    let rendered = settings::render(&json!({}), &shared, Path::new("C:/root"), &prefs).unwrap();
    assert!(
        !rendered["actions"]
            .as_array()
            .unwrap()
            .iter()
            .any(|a| a["id"] == settings::TAB_ACTION)
    );
    assert_eq!(rendered["defaultProfile"], settings::SESSIONS);
}
