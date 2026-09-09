use anyhow::{Context, Result, bail};
use clap::{Args, Parser, Subcommand};
use serde_json::{Value, json};
use std::{path::PathBuf, time::Duration};
use terminal_workspace::{
    binary, launch, root,
    settings::{self, Preferences},
};

#[derive(Parser)]
#[command(
    version,
    about = "Remote shells and saved forwards in Windows Terminal"
)]
struct Cli {
    #[arg(long, global = true)]
    root: Option<PathBuf>,
    #[arg(long, global = true)]
    json: bool,
    #[command(subcommand)]
    command: Action,
}
#[derive(Subcommand)]
enum Action {
    /// Render this installation's profiles and shortcuts, with an original backup.
    Configure(Configure),
    /// Read-only installation checks; does not start SSH or change Terminal.
    Doctor,
    /// Open or return to a remote tab, or an independent local Herdr session.
    Remote(Remote),
    /// Choose a machine, add its companion tabs, then run its remote session.
    Workspace(Workspace),
}
#[derive(Args)]
struct Configure {
    #[arg(long)]
    settings: Option<PathBuf>,
    #[arg(long)]
    export: bool,
    #[arg(long)]
    ssh_host: Option<String>,
    #[arg(long)]
    herdr: Option<PathBuf>,
    #[arg(long, value_parser=["ssh","herdr"])]
    remote_client: Option<String>,
    #[arg(long, conflicts_with = "no_local_herdr")]
    local_herdr: bool,
    #[arg(long)]
    no_local_herdr: bool,
    #[arg(long, conflicts_with = "no_session_picker")]
    session_picker: bool,
    #[arg(long)]
    no_session_picker: bool,
    #[arg(long)]
    session_catalog: Option<PathBuf>,
    #[arg(long,value_parser=["ctrl+n","ctrl+t","none"])]
    new_tab_shortcut: Option<String>,
    #[arg(long, conflicts_with = "apply_shared_settings")]
    integration_only: bool,
    #[arg(long)]
    apply_shared_settings: bool,
    /// Render JSON without writing files or starting processes.
    #[arg(long)]
    dry_run: bool,
}
#[derive(Args)]
struct Remote {
    #[arg(long)]
    machine: Option<String>,
    #[arg(long)]
    machines: bool,
    #[arg(long)]
    data_dir: Option<PathBuf>,
    #[arg(long)]
    local: bool,
    #[arg(long,value_parser=["ssh","herdr"])]
    client: Option<String>,
    #[arg(long)]
    herdr: Option<String>,
    #[arg(long)]
    focus_existing: bool,
}
#[derive(Args)]
struct Workspace {
    #[arg(long)]
    window: String,
    #[arg(long)]
    machine: Option<String>,
    #[arg(long)]
    machines: bool,
    #[arg(long)]
    data_dir: Option<PathBuf>,
    #[arg(long)]
    taskbar_identity: bool,
}

fn directory(value: Option<PathBuf>) -> Result<PathBuf> {
    Ok(value.unwrap_or(
        dirs::data_local_dir()
            .context("Cannot find application data")?
            .join("PortForwardTUI"),
    ))
}

fn configure(root: &std::path::Path, options: Configure) -> Result<Value> {
    let path = options.settings.unwrap_or(settings::settings_path()?);
    let original = settings::read_bytes(&path)?;
    let current = match &original {
        Some(bytes) => settings::parse(bytes)?,
        None => json!({}),
    };
    let shared_path = root.join("config/terminal.json");
    let shared = settings::load(&shared_path)?;
    if options.export {
        if original.is_none() {
            bail!("Open Windows Terminal before exporting settings");
        }
        let result = settings::export(&current, &shared);
        if !options.dry_run {
            settings::write(
                &shared_path,
                &result,
                settings::read_bytes(&shared_path)?.as_deref(),
                true,
            )?;
        }
        return Ok(result);
    }
    let machine_path = root.join(".machine.json");
    let machine_original = settings::read_bytes(&machine_path)?;
    let mut machine = settings::load(&machine_path)?;
    // Validate the existing structure before indexing nested shortcut choices.
    // An invalid personal file must produce a diagnostic, not a panic or reset.
    Preferences::read(&machine)?;
    if options.integration_only {
        machine["integration_only"] = json!(true);
    }
    if options.apply_shared_settings {
        machine["integration_only"] = json!(false);
    }
    if options.local_herdr || options.no_local_herdr {
        machine["local_herdr"] = json!(options.local_herdr);
    }
    if options.session_picker || options.no_session_picker {
        machine["session_picker"] = json!(options.session_picker);
    }
    if let Some(client) = options.remote_client {
        machine["remote_client"] = json!(client);
    }
    if let Some(herdr) = options.herdr {
        machine["herdr"] = json!(std::path::absolute(herdr)?);
    }
    if let Some(catalog) = options.session_catalog {
        machine["session_catalog"] = json!(std::path::absolute(catalog)?);
    }
    if let Some(host) = &options.ssh_host {
        port_forward_tui::store::host(host)?;
        machine["ssh_host"] = json!(host);
    }
    if let Some(chord) = options.new_tab_shortcut {
        machine["shortcuts"]["newTab"] = if chord == "none" {
            Value::Null
        } else {
            json!(chord)
        };
    }
    let mut preferences = Preferences::read(&machine)?;
    preferences.apply_default = options.session_picker || options.no_session_picker;
    if (preferences.local_herdr || preferences.remote_client == "herdr")
        && !std::path::Path::new(&preferences.herdr).is_file()
        && !options.dry_run
    {
        bail!("Install Herdr first or pass --herdr PATH");
    }
    for name in [
        "terminal-workspace",
        "ports",
        "ssh-sessions",
        "TerminalViews",
        "PortsFocus",
    ] {
        if !binary(root, name).is_file() && !options.dry_run {
            bail!("Missing {name}.exe. Run the binary installer before configuring");
        }
    }
    let updated = settings::render(&current, &shared, root, &preferences)?;
    if options.dry_run {
        return Ok(updated);
    }
    if settings::read_bytes(&machine_path)? != machine_original {
        bail!("Machine preferences changed while preparing the update; retry");
    }
    settings::write(&path, &updated, original.as_deref(), true)?;
    settings::write(&machine_path, &machine, machine_original.as_deref(), true)?;
    if let Some(host) = options.ssh_host {
        let result = terminal_workspace::dispatch(
            &binary(root, "ports"),
            &[
                "machines".into(),
                "add".into(),
                host.into(),
                "--json".into(),
            ],
            Duration::from_secs(10),
        )?;
        if !result.success() {
            eprintln!(
                "Profiles are ready; import the requested host inside Ports (automatic add did not finish)."
            );
        }
    }
    Ok(
        json!({"schema_version":1,"ok":true,"command":"configure","settings":path,"session_picker":preferences.session_picker,"integration_only":preferences.integration_only}),
    )
}

fn doctor(root: &std::path::Path) -> Value {
    let mut checks = vec![];
    for (name, fix) in [
        ("wt.exe", "Install Windows Terminal."),
        ("pwsh.exe", "Install PowerShell 7."),
        ("ssh.exe", "Enable Windows OpenSSH Client."),
    ] {
        checks.push(json!({"name":name,"ok":which::which(name).is_ok(),"fix":fix}));
    }
    for name in [
        "terminal-workspace",
        "ports",
        "ssh-sessions",
        "PortsFocus",
        "TerminalViews",
    ] {
        checks.push(json!({"name":name,"ok":binary(root,name).is_file(),"fix":"Run the binary installer again."}));
    }
    let preferences =
        settings::load(&root.join(".machine.json")).and_then(|data| Preferences::read(&data));
    match preferences {
        Ok(preferences) => {
            let needed = preferences.local_herdr || preferences.remote_client == "herdr";
            checks.push(json!({"name":"herdr","ok":!needed || std::path::Path::new(&preferences.herdr).is_file(),"fix":"Install Herdr or choose ordinary SSH."}));
        }
        Err(error) => {
            checks.push(json!({"name":"machine_settings","ok":false,"fix":error.to_string()}))
        }
    }
    let ok = checks.iter().all(|c| c["ok"] == true);
    json!({"schema_version":1,"ok":ok,"command":"doctor","checks":checks})
}

fn run(cli: Cli) -> Result<i32> {
    if !cfg!(windows) {
        bail!(
            "Terminal Workspace integrates Windows Terminal. Install the independent Ports and SSH Sessions apps on Linux/macOS."
        );
    }
    let root = root(cli.root)?;
    match cli.command {
        Action::Configure(options) => {
            let dry = options.dry_run;
            let result = configure(&root, options)?;
            if cli.json || dry {
                println!("{}", serde_json::to_string_pretty(&result)?);
            } else {
                println!(
                    "Workspace settings are ready. New-tab and local-shell choices are saved in .machine.json."
                );
            }
            Ok(0)
        }
        Action::Doctor => {
            let result = doctor(&root);
            let ok = result["ok"] == true;
            if cli.json {
                println!("{}", serde_json::to_string_pretty(&result)?);
            } else {
                for check in result["checks"].as_array().unwrap() {
                    println!(
                        "{} {}{}",
                        if check["ok"] == true { "OK" } else { "FIX" },
                        check["name"].as_str().unwrap(),
                        if check["ok"] == true {
                            String::new()
                        } else {
                            format!(": {}", check["fix"].as_str().unwrap())
                        }
                    );
                }
            }
            Ok(if ok { 0 } else { 1 })
        }
        Action::Remote(options) => {
            let mut preferences = Preferences::read(&settings::load(&root.join(".machine.json"))?)?;
            if let Some(client) = options.client {
                preferences.remote_client = client;
            }
            if let Some(herdr) = options.herdr {
                preferences.herdr = herdr;
            }
            let directory = directory(options.data_dir)?;
            let machine = if options.local {
                None
            } else {
                let selected = launch::select(
                    &root,
                    &directory,
                    options.machine.as_deref(),
                    options.machines,
                    true,
                )?;
                if selected.is_none() {
                    return Ok(0);
                }
                selected
            };
            launch::remote(
                &root,
                &directory,
                machine,
                &preferences,
                options.focus_existing,
            )
        }
        Action::Workspace(options) => launch::workspace(
            &root,
            &options.window,
            &directory(options.data_dir)?,
            options.machine.as_deref(),
            options.machines,
            options.taskbar_identity,
        ),
    }
}

fn main() {
    let arguments: Vec<_> = std::env::args_os().collect();
    let wants_json = arguments.iter().any(|arg| arg == "--json");
    let cli = match Cli::try_parse_from(&arguments) {
        Ok(cli) => cli,
        Err(error) if wants_json && error.use_stderr() => {
            println!(
                "{}",
                json!({"schema_version":1,"ok":false,"error":{"code":"invalid_arguments","message":error.to_string()}})
            );
            std::process::exit(2);
        }
        Err(error) => error.exit(),
    };
    let json = cli.json;
    let result = port_forward_tui::process::protect_incoming_stdio().and_then(|()| {
        // Protect inherited capture handles before starting threads or helpers.
        // Explicit child console streams are duplicated normally by Command.
        // The child session handles Ctrl+C; retain ownership until it returns.
        let _ = ctrlc::set_handler(|| {});
        run(cli)
    });
    let code = match result {
        Ok(code) => code,
        Err(error) => {
            if json {
                println!(
                    "{}",
                    json!({"schema_version":1,"ok":false,"error":{"code":"operation_failed","message":format!("{error:#}")}})
                );
            } else {
                eprintln!("Workspace: {error:#}");
            }
            1
        }
    };
    std::process::exit(code);
}
