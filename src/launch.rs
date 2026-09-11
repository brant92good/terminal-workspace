use crate::{
    binary, dispatch, output,
    settings::{self, Preferences},
};
use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    ffi::OsString,
    path::{Path, PathBuf},
    process::Command,
    time::Duration,
};

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Machine {
    pub id: String,
    pub name: String,
    pub target: String,
    pub ssh_port: Option<u16>,
    pub ssh_config: Option<String>,
    pub directory: PathBuf,
}

pub fn select(
    root: &Path,
    directory: &Path,
    machine: Option<&str>,
    picker: bool,
    window_context: bool,
) -> Result<Option<Machine>> {
    let mut command = Command::new(binary(root, "ports"));
    command
        .args(["machines", "pick", "--json", "--data-dir"])
        .arg(directory);
    if let Some(machine) = machine {
        command.args(["--machine", machine]);
    }
    if picker {
        command.arg("--force-picker");
    }
    if !window_context {
        command.arg("--no-window-context");
    }
    // The selector renders to inherited stderr; stdout contains one JSON result.
    let result = output(&mut command, None)?;
    let data: Value =
        serde_json::from_slice(&result.stdout).context("Ports selector returned invalid JSON")?;
    if !result.status.success() || data["ok"] != true {
        bail!(
            "{}",
            data["error"]["message"]
                .as_str()
                .unwrap_or("Ports machine selection failed")
        );
    }
    if data["schema_version"] != 1 || data["command"] != "machines pick" {
        bail!("Unsupported Ports selection response");
    }
    if data["machine"].is_null() {
        return Ok(None);
    }
    let machine: Machine = serde_json::from_value(data["machine"].clone())?;
    if machine.id.is_empty()
        || machine.target.starts_with('-')
        || machine.target.contains(['\r', '\n', '\0'])
        || !machine.directory.is_absolute()
    {
        bail!("Invalid machine returned by Ports");
    }
    Ok(Some(machine))
}

pub fn tab_arguments(
    root: &Path,
    window: &str,
    machine: &Machine,
    directory: &Path,
    preferences: &Preferences,
) -> Result<Vec<String>> {
    // Terminal splits even quoted argv on unescaped semicolons. Escape data
    // before adding the deliberate command separators, not Windows argv quotes.
    // See Microsoft Terminal v1.24.11911.0 Commandline::AddArg.
    let wt = |value: &str| value.replace(';', "\\;");
    let mut arguments = vec!["-w".into(), wt(window)];
    if preferences.local_herdr {
        arguments.extend([
            "new-tab".into(),
            "-p".into(),
            settings::LOCAL.into(),
            wt(&binary(root, "terminal-workspace").to_string_lossy()),
            "remote".into(),
            "--local".into(),
            "--herdr".into(),
            wt(&preferences.herdr),
            "--data-dir".into(),
            wt(&directory.to_string_lossy()),
            ";".into(),
        ]);
    }
    arguments.extend([
        "new-tab".into(),
        "-p".into(),
        settings::PORTS.into(),
        wt(&binary(root, "ports").to_string_lossy()),
        "--data-dir".into(),
        wt(&directory.to_string_lossy()),
        "--machine".into(),
        wt(&machine.id),
    ]);
    if preferences.workspace_files {
        let (executable, args) = files_chooser_arguments(root, preferences)?;
        arguments.extend([
            ";".into(),
            "new-tab".into(),
            "-p".into(),
            settings::FILES.into(),
            wt(&executable.to_string_lossy()),
        ]);
        arguments.extend(args.iter().map(|arg| wt(arg)));
    }
    arguments.extend([";".into(), "focus-tab".into(), "-t".into(), "0".into()]);
    Ok(arguments)
}

/// Open the SSH catalog's Files chooser without selecting or mapping a machine.
pub fn files_chooser_arguments(
    root: &Path,
    preferences: &Preferences,
) -> Result<(PathBuf, Vec<String>)> {
    let (executable, mut arguments) = settings::sessions_arguments(root, preferences);
    if !executable.is_file() {
        bail!("SSH Sessions is missing. Run the workspace binary installer again.");
    }
    arguments.push("files".into());
    Ok((executable, arguments))
}

/// Resolve metadata without selecting a current machine or touching a controller.
pub fn read_machine(directory: &Path, id: &str) -> Result<Machine> {
    let machine = port_forward_tui::machines::Catalog::new(directory)?.get(id)?;
    Ok(Machine {
        id: machine.id,
        name: machine.name,
        target: machine.target,
        ssh_port: machine.ssh_port,
        ssh_config: machine.ssh_config,
        directory: machine.directory,
    })
}

/// Freeze this destination into the companion's argv. Files owns no catalog.
pub fn files_arguments(root: &Path, machine: &Machine) -> Result<(PathBuf, Vec<String>)> {
    let executable = binary(root, "ssh-files");
    if !executable.is_file() {
        bail!("SSH Files is missing. Run the workspace binary installer again.");
    }
    port_forward_tui::store::host(&machine.target)?;
    if machine.name.chars().any(char::is_control) || machine.id.chars().any(char::is_control) {
        bail!("Invalid Files machine label or ID");
    }
    let mut args = vec![
        format!("--host={}", machine.target),
        format!("--label={}", machine.name),
        format!("--machine-id={}", machine.id),
    ];
    if let Some(port) = machine.ssh_port {
        if port == 0 {
            bail!("Invalid SSH port");
        }
        args.push(format!("--port={port}"));
    }
    if let Some(config) = &machine.ssh_config {
        let path = std::path::absolute(config)?;
        if !path.is_file() {
            bail!("SSH configuration file does not exist: {}", path.display());
        }
        args.push(format!(
            "--config={}",
            path.to_str()
                .context("SSH config path is not valid Unicode")?
        ));
    }
    Ok((executable, args))
}

pub fn files(root: &Path, machine: &Machine) -> Result<i32> {
    let (executable, args) = files_arguments(root, machine)?;
    Ok(Command::new(executable)
        .args(args)
        .status()
        .context("Could not start SSH Files")?
        .code()
        .unwrap_or(1))
}

pub fn session_arguments(
    machine: Option<&Machine>,
    client: &str,
    herdr: &str,
) -> Result<(String, Vec<String>, bool)> {
    if let Some(machine) = machine {
        let use_herdr =
            client == "herdr" && machine.ssh_port.is_none() && machine.ssh_config.is_none();
        if use_herdr {
            return Ok((
                herdr.into(),
                vec!["--remote".into(), machine.target.clone()],
                true,
            ));
        }
        let mut args = vec![];
        if let Some(port) = machine.ssh_port {
            args.extend(["-p".into(), port.to_string()]);
        }
        if let Some(config) = &machine.ssh_config {
            args.extend(["-F".into(), config.clone()]);
        }
        args.push(machine.target.clone());
        Ok(("ssh.exe".into(), args, false))
    } else {
        Ok((herdr.into(), vec![], true))
    }
}

pub fn remote(
    root: &Path,
    directory: &Path,
    machine: Option<Machine>,
    preferences: &Preferences,
    focus: bool,
) -> Result<i32> {
    let (executable, args, uses_herdr) = session_arguments(
        machine.as_ref(),
        &preferences.remote_client,
        &preferences.herdr,
    )?;
    if uses_herdr && !Path::new(&executable).is_file() {
        bail!("Herdr executable not found; configure --herdr PATH");
    }
    let records = if let Some(machine) = &machine {
        if uses_herdr {
            directory
                .join("herdr-views")
                .join(&format!("{:x}", Sha256::digest(machine.target.as_bytes()))[..16])
        } else {
            directory.join("ssh-views").join(&machine.id)
        }
    } else {
        directory.join("local-herdr-views")
    };
    let scope = port_forward_tui::views::read_scope(
        machine
            .as_ref()
            .map_or(directory, |m| m.directory.as_path()),
    )?;
    let origin = port_forward_tui::views::mark_origin().unwrap_or_default();
    if focus && !origin.is_empty() {
        match port_forward_tui::views::try_focus(&records, &scope, &origin, false) {
            Ok(true) => return Ok(0),
            Ok(false) => {}
            Err(error) => eprintln!("Return shortcut: {error}"),
        }
    }
    let view = if origin.is_empty() {
        None
    } else {
        match port_forward_tui::views::register_remote(
            &records,
            machine.as_ref().map(|_| directory),
            machine.as_ref().map(|m| m.id.as_str()),
            &origin,
            &binary(root, "TerminalViews"),
        ) {
            Ok(view) => Some(view),
            Err(error) => {
                eprintln!("Opening session without a return target: {error}");
                None
            }
        }
    };
    let mut command = Command::new(executable);
    command.args(args);
    if uses_herdr && view.is_some() {
        // Only after this new tab has a verified identity, discard inherited pane
        // identities. Keep shell/profile/Conda settings and ordinary user values.
        const CONTEXT: &[&str] = &[
            "HERDR_ENV",
            "HERDR_PANE_ID",
            "HERDR_TAB_ID",
            "HERDR_WORKSPACE_ID",
            "HERDR_SOCKET_PATH",
            "HERDR_STARTUP_CWD",
            "HERDR_BIN_PATH",
        ];
        for (key, _) in std::env::vars_os() {
            if CONTEXT.contains(&key.to_string_lossy().to_ascii_uppercase().as_str()) {
                command.env_remove(key);
            }
        }
    }
    let status = command.status().context("Could not start the session")?;
    drop(view);
    Ok(status.code().unwrap_or(1))
}

pub fn workspace(
    root: &Path,
    window: &str,
    directory: &Path,
    machine: Option<&str>,
    picker: bool,
    taskbar: bool,
) -> Result<i32> {
    if window.is_empty() || window.contains(['\r', '\n', '\0', ';']) {
        bail!("Invalid workspace window identity");
    }
    let preferences = Preferences::read(&settings::load(&root.join(".machine.json"))?)?;
    if taskbar && let Ok(origin) = port_forward_tui::views::mark_origin() {
        let _ = dispatch(
            &root.join("build/TerminalWorkspace.exe"),
            &[OsString::from("--identify-origin"), origin.into()],
            Duration::from_secs(7),
        );
    }
    let Some(machine) = select(root, directory, machine, picker, false)? else {
        return Ok(0);
    };
    let terminal = which::which("wt.exe").context("Windows Terminal was not found")?;
    let arguments: Vec<OsString> = tab_arguments(root, window, &machine, directory, &preferences)?
        .into_iter()
        .map(OsString::from)
        .collect();
    let result = dispatch(&terminal, &arguments, Duration::from_secs(10))?;
    if !result.success() {
        bail!("Windows Terminal could not create the companion tabs");
    }
    remote(root, directory, Some(machine), &preferences, false)
}
