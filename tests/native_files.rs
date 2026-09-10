#![cfg(windows)]
use serde_json::{Value, json};
use std::{fs, path::Path, process::Command};
use terminal_workspace::{
    launch::{self, Machine},
    settings::{self, Preferences},
};

fn setup(root: &Path) -> Machine {
    fs::create_dir_all(root.join("bin")).unwrap();
    fs::write(
        root.join("bin/ssh-files.exe"),
        b"preview must not execute this",
    )
    .unwrap();
    let config = root.join("config 測試; tail");
    fs::write(&config, b"Host demo\n HostName 192.0.2.4\n").unwrap();
    Machine {
        id: "stable-ports-id".into(),
        name: "--開發; new-tab ; quote \" end\\".into(),
        target: "user@demo".into(),
        ssh_port: Some(2222),
        ssh_config: Some(config.to_string_lossy().into_owned()),
        directory: root.join("data"),
    }
}

#[test]
fn four_tabs_freeze_route_and_escape_terminal_delimiters() {
    let temp = tempfile::tempdir().unwrap();
    let root = temp.path().join("workspace;測試");
    let machine = setup(&root);
    let prefs = Preferences::read(
        &json!({"local_herdr":true,"workspace_files":true,"herdr":"C:/my;herdr.exe"}),
    )
    .unwrap();
    let args = launch::tab_arguments(&root, "unique-window", &machine, &machine.directory, &prefs)
        .unwrap();
    let chunks: Vec<_> = args.split(|s| s == ";").collect();
    assert_eq!(chunks.len(), 4); // Three companions and focus; Remote already exists.
    assert_eq!(chunks[0][4], settings::PORTS);
    assert_eq!(chunks[1][2], settings::LOCAL);
    assert_eq!(chunks[2][2], settings::FILES);
    assert_eq!(chunks[3], ["focus-tab", "-t", "0"]);
    let frozen: Vec<_> = chunks[2][4..]
        .iter()
        .map(|arg| arg.replace("\\;", ";"))
        .collect();
    let (_, expected) = launch::files_arguments(&root, &machine).unwrap();
    assert_eq!(frozen, expected);
    assert!(frozen.contains(&format!("--label={}", machine.name)));
    assert!(frozen.contains(&"--host=user@demo".into()));
    assert!(frozen.contains(&"--port=2222".into()));
    assert!(frozen.contains(&format!("--config={}", machine.ssh_config.unwrap())));
    assert!(!frozen.iter().any(|arg| arg.contains("route-id")));
    for chunk in &chunks {
        for arg in *chunk {
            for (i, _) in arg.match_indices(';') {
                assert!(i > 0 && arg.as_bytes()[i - 1] == b'\\');
            }
        }
    }
    fs::remove_file(root.join("bin/ssh-files.exe")).unwrap();
    assert!(
        launch::tab_arguments(&root, "unique-window", &setup_machine(&root), &root, &prefs)
            .is_err()
    );
}

fn setup_machine(root: &Path) -> Machine {
    Machine {
        id: "id".into(),
        name: "Demo".into(),
        target: "demo".into(),
        ssh_port: None,
        ssh_config: None,
        directory: root.into(),
    }
}

#[test]
fn literal_and_backslash_semicolons_round_trip_through_terminal_boundary() {
    let temp = tempfile::tempdir().unwrap();
    let root = temp.path();
    let mut machine = setup(root);
    let config = root.join(";ssh_config");
    fs::write(&config, b"Host demo\n").unwrap();
    machine.ssh_config = Some(config.to_str().unwrap().into());
    let options = Preferences::read(&json!({"workspace_files":true})).unwrap();
    for label in [";", r"before\;after", r"trailing\;"] {
        machine.name = label.into();
        let args = launch::tab_arguments(root, "window", &machine, root, &options).unwrap();
        let commands: Vec<_> = args.split(|arg| arg == ";").collect();
        assert_eq!(commands.len(), 3);
        let restored: Vec<_> = commands[1][4..]
            .iter()
            .map(|arg| arg.replace("\\;", ";"))
            .collect();
        assert_eq!(restored, launch::files_arguments(root, &machine).unwrap().1);
    }
}

#[test]
fn files_preview_is_read_only_and_resolves_relative_config_before_tab_changes_directory() {
    let temp = tempfile::tempdir().unwrap();
    let root = temp.path();
    setup(root);
    fs::write(root.join("ssh_config"), b"Host demo\n HostName 192.0.2.4\n").unwrap();
    let data = root.join("data");
    fs::create_dir(&data).unwrap();
    let bytes=serde_json::to_vec(&json!({"version":1,"host":"demo","ssh_port":2222,"ssh_config":"ssh_config","keep_alive":true,"forwards":[]})).unwrap();
    fs::write(data.join("forwards.json"), &bytes).unwrap();
    let run = |extra: &[&str]| {
        Command::new(env!("CARGO_BIN_EXE_terminal-workspace"))
            .current_dir(root)
            .arg("--root")
            .arg(root)
            .arg("files")
            .arg("--data-dir")
            .arg(&data)
            .arg("--json")
            .args(extra)
            .output()
            .unwrap()
    };
    let output = run(&["--machine", "demo"]);
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stdout)
    );
    let preview: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(preview["command"], "files");
    assert_eq!(preview["machine"]["target"], "demo");
    assert!(
        preview["arguments"]
            .as_array()
            .unwrap()
            .contains(&json!(format!(
                "--config={}",
                root.join("ssh_config").display()
            )))
    );
    for args in [&[][..], &["--machines"][..], &["--machine", "missing"][..]] {
        assert!(!run(args).status.success());
    }
    assert_eq!(fs::read(data.join("forwards.json")).unwrap(), bytes);
    assert_eq!(fs::read_dir(&data).unwrap().count(), 1);
    assert!(!root.join(".machine.json").exists());
}

#[test]
fn actual_workspace_dispatch_cancels_cleanly_and_freezes_files_before_remote_runs() {
    let temp = tempfile::tempdir().unwrap();
    let root = temp.path();
    let mut machine = setup(root);
    machine.ssh_port = None;
    machine.ssh_config = None;
    let source = root.join("fixture.rs");
    fs::write(&source, r#"
use std::{env,fs,path::PathBuf};
fn main() {
 let root=PathBuf::from(env::var_os("WORKSPACE_FIXTURE").unwrap());
 let exe=env::current_exe().unwrap(); let name=exe.file_stem().unwrap().to_str().unwrap();
 fs::write(root.join(format!("{name}.argv")),env::args().skip(1).collect::<Vec<_>>().join("\0")).unwrap();
 if name=="ports" {print!("{}",fs::read_to_string(root.join("selection.json")).unwrap());}
}
"#).unwrap();
    let result = Command::new("rustc")
        .arg("--edition=2024")
        .arg(source)
        .arg("-o")
        .arg(root.join("bin/fixture.exe"))
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    for name in ["wt", "ports", "herdr", "ssh-files"] {
        fs::copy(
            root.join("bin/fixture.exe"),
            root.join(format!("bin/{name}.exe")),
        )
        .unwrap();
    }
    fs::write(
        root.join(".machine.json"),
        serde_json::to_vec(&json!({
        "workspace_files":true,"local_herdr":true,"remote_client":"herdr",
        "herdr":root.join("bin/herdr.exe")}))
        .unwrap(),
    )
    .unwrap();
    let path = std::env::join_paths(
        std::iter::once(root.join("bin"))
            .chain(std::env::split_paths(&std::env::var_os("PATH").unwrap())),
    )
    .unwrap();
    let run = |action: &[&str]| {
        Command::new(env!("CARGO_BIN_EXE_terminal-workspace"))
            .arg("--root")
            .arg(root)
            .args(action)
            .arg("--data-dir")
            .arg(&machine.directory)
            .env("PATH", &path)
            .env("WORKSPACE_FIXTURE", root)
            .env_remove("WT_SESSION")
            .current_dir(root)
            .output()
            .unwrap()
    };
    let selected = root.join("selection.json");
    fs::write(
        &selected,
        serde_json::to_vec(
            &json!({"schema_version":1,"ok":true,"command":"machines pick","machine":null}),
        )
        .unwrap(),
    )
    .unwrap();
    assert!(
        run(&["workspace", "--window", "owned-fixture"])
            .status
            .success()
    );
    assert!(run(&["files"]).status.success());
    for name in ["wt", "herdr", "ssh-files"] {
        assert!(!root.join(format!("{name}.argv")).exists());
    }
    fs::write(
        &selected,
        serde_json::to_vec(
            &json!({"schema_version":1,"ok":true,"command":"machines pick","machine":machine}),
        )
        .unwrap(),
    )
    .unwrap();
    fs::remove_file(root.join("bin/ssh-files.exe")).unwrap();
    assert!(
        !run(&["workspace", "--window", "owned-fixture"])
            .status
            .success()
    );
    assert!(!root.join("wt.argv").exists());
    assert!(!root.join("herdr.argv").exists());
    fs::copy(root.join("bin/fixture.exe"), root.join("bin/ssh-files.exe")).unwrap();
    let result = run(&["workspace", "--window", "owned-fixture"]);
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let expected = launch::tab_arguments(
        root,
        "owned-fixture",
        &machine,
        &machine.directory,
        &Preferences::read(&settings::load(&root.join(".machine.json")).unwrap()).unwrap(),
    )
    .unwrap();
    assert_eq!(
        fs::read_to_string(root.join("wt.argv"))
            .unwrap()
            .split('\0')
            .collect::<Vec<_>>(),
        expected
    );
    assert_eq!(
        fs::read_to_string(root.join("herdr.argv")).unwrap(),
        format!("--remote\0{}", machine.target)
    );
    assert!(run(&["files"]).status.success());
    assert_eq!(
        fs::read_to_string(root.join("ssh-files.argv"))
            .unwrap()
            .split('\0')
            .collect::<Vec<_>>(),
        launch::files_arguments(root, &machine).unwrap().1
    );
}
