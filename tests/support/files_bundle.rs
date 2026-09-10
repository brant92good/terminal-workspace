//! Package-only checks: never opens a Files UI or an SSH connection.
use super::{check, run};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{fs, path::Path, process::Command};

pub fn verify_installed(destination: &Path, sandbox: &Path) {
    let manifest: Value =
        serde_json::from_slice(&fs::read(destination.join("release.json")).unwrap()).unwrap();
    for (program, version) in [
        ("terminal-workspace", env!("CARGO_PKG_VERSION")),
        ("ports", "0.8.1"),
        ("ssh-sessions", "0.7.0"),
        ("ssh-files", "0.1.0"),
    ] {
        let binary = destination.join(format!("bin/{program}.exe"));
        let output = Command::new(&binary).arg("--version").output().unwrap();
        assert!(output.status.success());
        assert_eq!(
            String::from_utf8(output.stdout).unwrap().trim(),
            format!("{program} {version}")
        );
        assert_eq!(
            manifest["files"][format!("bin/{program}.exe")],
            format!("{:x}", Sha256::digest(fs::read(&binary).unwrap()))
        );
    }
    assert_eq!(manifest["dependencies"]["ssh_files"]["status"], "beta");
    assert_eq!(
        manifest["dependencies"]["ssh_files"]["sha256"],
        manifest["files"]["bin/ssh-files.exe"]
    );
    for name in [
        "ports-LICENSE.txt",
        "ssh-sessions-LICENSE.txt",
        "ssh-files-LICENSE.txt",
        "ssh-files-THIRD_PARTY_NOTICES.txt",
    ] {
        let bytes = fs::read(destination.join("licenses").join(name)).unwrap();
        assert!(bytes.len() > 100);
        assert_eq!(
            manifest["files"][format!("licenses/{name}")],
            format!("{:x}", Sha256::digest(bytes))
        );
    }
    let catalog = sandbox.join("files catalog.json");
    let state = sandbox.join("files device");
    let config = sandbox.join("config \u{958b}\u{767c}.ssh");
    fs::write(
        &config,
        "Host fixture-alias\n HostName selected.invalid\n User fixture-user\n Port 2222\n",
    )
    .unwrap();
    let executable = destination.join("bin/ssh-sessions.exe");
    let mut import = Command::new(&executable);
    import
        .args(["--catalog"])
        .arg(&catalog)
        .arg("--state-dir")
        .arg(&state)
        .args(["import-ssh", "--config"])
        .arg(&config)
        .args(["--all", "--apply", "--json"]);
    check(import.output().unwrap());
    let mut data: Value = serde_json::from_slice(&fs::read(&catalog).unwrap()).unwrap();
    data["machines"][0]["name"] = json!("\u{958b}\u{767c}\u{1f680}");
    data["machines"][0]["routes"][0]["name"] = json!("Explicit route");
    fs::write(&catalog, serde_json::to_vec(&data).unwrap()).unwrap();
    let machine = data["machines"][0]["id"].as_str().unwrap();
    let route = data["machines"][0]["routes"][0]["id"].as_str().unwrap();
    let decoy = sandbox.join("bad PATH");
    fs::create_dir(&decoy).unwrap();
    fs::write(decoy.join("ssh-files.exe"), b"must not be selected").unwrap();
    let before = fs::read(&catalog).unwrap();
    let output = Command::new(&executable)
        .arg("--catalog")
        .arg(&catalog)
        .arg("--state-dir")
        .arg(&state)
        .args(["files", machine, "--route", route, "--json"])
        .env_remove("SSH_FILES_BIN")
        .env("PATH", &decoy)
        .current_dir(sandbox)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let launch: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(launch["machine_id"], machine);
    assert_eq!(launch["route_id"], route);
    // Import resolves existing config paths. Hosted TEMP uses RUNNER~1, while
    // the saved config uses runneradmin; both must name this exact owned file.
    assert_eq!(
        fs::canonicalize(launch["argv"][6].as_str().unwrap()).unwrap(),
        fs::canonicalize(&config).unwrap()
    );
    let mut arguments = launch["argv"].clone();
    arguments[6] = json!(config);
    assert_eq!(
        arguments,
        json!([
            destination.join("bin").join("ssh-files.exe"),
            "--host",
            "fixture-alias",
            "--hostname",
            "selected.invalid",
            "--config",
            config,
            "--user",
            "fixture-user",
            "--port",
            "2222",
            "--label=\u{958b}\u{767c}\u{1f680} | Explicit route",
            "--machine-id",
            machine,
            "--route-id",
            route,
            "--local",
            sandbox
        ])
    );
    assert_eq!(fs::read(&catalog).unwrap(), before);
    verify_workspace_files(destination, sandbox, &config);
}

fn verify_workspace_files(destination: &Path, sandbox: &Path, config: &Path) {
    let data = sandbox.join("workspace-files-data");
    let added = Command::new(destination.join("bin/ports.exe"))
        .arg("--data-dir")
        .arg(&data)
        .args([
            "machines",
            "add",
            "fixture-alias",
            "--name",
            "Workspace demo",
            "--ssh-port",
            "2222",
            "--config",
        ])
        .arg(config)
        .arg("--json")
        .output()
        .unwrap();
    assert!(
        added.status.success(),
        "{}",
        String::from_utf8_lossy(&added.stdout)
    );
    let added: Value = serde_json::from_slice(&added.stdout).unwrap();
    let machine = added["machine"]["id"].as_str().unwrap();
    let forwards = data.join("machines").join(machine).join("forwards.json");
    let before = fs::read(&forwards).unwrap();
    let preview = Command::new(destination.join("bin/terminal-workspace.exe"))
        .arg("--root")
        .arg(destination)
        .args(["files", "--machine", machine, "--data-dir"])
        .arg(&data)
        .arg("--json")
        .output()
        .unwrap();
    assert!(
        preview.status.success(),
        "{}",
        String::from_utf8_lossy(&preview.stdout)
    );
    let preview: Value = serde_json::from_slice(&preview.stdout).unwrap();
    let arguments = preview["arguments"].as_array().unwrap();
    assert_eq!(
        preview["executable"],
        json!(destination.join("bin/ssh-files.exe"))
    );
    assert!(arguments.contains(&json!("--host=fixture-alias")));
    assert!(arguments.contains(&json!("--port=2222")));
    assert!(arguments.contains(&json!("--label=Workspace demo")));
    let config_arg = arguments
        .iter()
        .filter_map(Value::as_str)
        .find_map(|v| v.strip_prefix("--config="))
        .unwrap();
    assert_eq!(
        fs::canonicalize(config_arg).unwrap(),
        fs::canonicalize(config).unwrap()
    );
    assert_eq!(fs::read(forwards).unwrap(), before);
    assert!(
        !data
            .join("machines")
            .join(machine)
            .join("endpoint.json")
            .exists()
    );
}

pub fn reject_incomplete_update(
    script: &Path,
    arguments: &[String],
    destination: &Path,
    sandbox: &Path,
) {
    let mutation_script = sandbox.join("mutate-fixture.ps1");
    fs::write(&mutation_script, r#"param($Archive,$Mode)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$zip=[IO.Compression.ZipFile]::Open($Archive,[IO.Compression.ZipArchiveMode]::Update)
try {
  $matches=@($zip.Entries | Where-Object { $_.FullName.Replace('\','/') -ceq 'bin/ssh-files.exe' })
  if($matches.Count -ne 1) { throw 'Expected exactly one Files fixture entry' }
  $entry=$matches[0]
  if($Mode -eq 'tamper') {
    $stream=$entry.Open(); try { $stream.SetLength(0); $stream.WriteByte(0) } finally { $stream.Dispose() }
  } else {
    $entry.Delete()
    $entry=$zip.GetEntry('release.json')
    $reader=New-Object IO.StreamReader($entry.Open())
    try { $manifest=$reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
    $entry.Delete()
    $manifest.files.PSObject.Properties.Remove('bin/ssh-files.exe')
    $writer=New-Object IO.StreamWriter($zip.CreateEntry('release.json').Open())
    try { $writer.Write(($manifest | ConvertTo-Json -Depth 10)) } finally { $writer.Dispose() }
  }
} finally { $zip.Dispose() }
"#).unwrap();
    let before = fs::read(destination.join(".machine.json")).unwrap();
    let binary = fs::read(destination.join("bin/ssh-files.exe")).unwrap();
    for mode in ["tamper", "missing"] {
        let archive = sandbox.join(format!("{mode}.zip"));
        fs::copy(&arguments[3], &archive).unwrap();
        check(run(
            &mutation_script,
            &[archive.to_string_lossy().into_owned(), mode.into()],
        ));
        let mut corrupt = arguments.to_vec();
        corrupt[3] = archive.to_string_lossy().into_owned();
        corrupt[5] = format!("{:x}", Sha256::digest(fs::read(&archive).unwrap()));
        let output = run(script, &corrupt);
        assert!(
            !output.status.success(),
            "Incomplete Files bundle was accepted"
        );
        assert_eq!(fs::read(destination.join(".machine.json")).unwrap(), before);
        assert_eq!(
            fs::read(destination.join("bin/ssh-files.exe")).unwrap(),
            binary
        );
    }
    let checkout = sandbox.join("owned source checkout");
    fs::create_dir_all(checkout.join(".git")).unwrap();
    let source = b"[package]\nname = \"terminal-workspace\"\n";
    fs::write(checkout.join("Cargo.toml"), source).unwrap();
    fs::write(checkout.join("README.md"), b"local source documentation").unwrap();
    fs::write(checkout.join(".machine.json"), &before).unwrap();
    let mut source_args = arguments.to_vec();
    source_args[1] = checkout.to_string_lossy().into_owned();
    source_args.push("-SourceCheckout".into());
    check(run(script, &source_args));
    assert_eq!(fs::read(checkout.join("Cargo.toml")).unwrap(), source);
    assert_eq!(
        fs::read(checkout.join("README.md")).unwrap(),
        b"local source documentation"
    );
    assert_eq!(fs::read(checkout.join(".machine.json")).unwrap(), before);
    assert_eq!(
        fs::read(checkout.join("bin/ssh-files.exe")).unwrap(),
        binary
    );
    assert_eq!(
        fs::read(checkout.join("licenses/ssh-files-THIRD_PARTY_NOTICES.txt")).unwrap(),
        fs::read(destination.join("licenses/ssh-files-THIRD_PARTY_NOTICES.txt")).unwrap()
    );
}
