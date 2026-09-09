use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::Write,
    path::{Path, PathBuf},
};

pub const HERDR: &str = "{a9a0b421-7dd6-4425-9843-59b5f5d6c2d1}";
pub const PORTS: &str = "{5e483274-6f37-40d5-b42b-1eaef7f9da82}";
pub const PWSH: &str = "{574e775e-4f2a-5b96-ac1e-a2962a402336}";
pub const LOCAL: &str = "{f7c9cd21-fd21-429b-93ac-bd21e5ef8b11}";
pub const SESSIONS: &str = "{2ab64c44-ef5c-48d2-8f4d-678473aae748}";
pub const TAB_ACTION: &str = "User.TerminalWorkspace.NewTab";
pub const SHELL_ACTION: &str = "User.TerminalWorkspace.LocalShell";
const ACTIONS: [(&str, &str); 8] = [
    ("herdr", "User.TerminalWorkspace.Herdr"),
    ("newHerdr", "User.TerminalWorkspace.NewHerdr"),
    ("ports", "User.TerminalWorkspace.Ports"),
    ("newPorts", "User.TerminalWorkspace.NewPorts"),
    ("local", "User.TerminalWorkspace.Local"),
    ("newLocal", "User.TerminalWorkspace.NewLocal"),
    ("shell", SHELL_ACTION),
    ("newTab", TAB_ACTION),
];
const PORTABLE: &[&str] = &[
    "copyFormatting",
    "copyOnSelect",
    "schemes",
    "themes",
    "theme",
    "tabWidthMode",
    "alwaysShowTabs",
    "showTabsInTitlebar",
    "useAcrylicInTabRow",
    "confirmCloseAllTabs",
    "initialRows",
    "initialCols",
    "launchMode",
    "windowingBehavior",
    "language",
    "focusFollowMouse",
    "wordDelimiters",
    "trimBlockSelection",
    "trimPaste",
    "snapToGridOnResize",
    "newTabPosition",
];
const PROFILE_PORTABLE: &[&str] = &[
    "font",
    "colorScheme",
    "useAcrylic",
    "opacity",
    "padding",
    "cursorShape",
    "cursorColor",
    "antialiasingMode",
    "historySize",
    "scrollbarState",
    "bellStyle",
];

#[derive(Clone, Debug)]
pub struct Preferences {
    pub integration_only: bool,
    pub session_picker: bool,
    pub apply_default: bool,
    pub local_herdr: bool,
    pub remote_client: String,
    pub herdr: String,
    pub session_catalog: Option<String>,
    pub shortcuts: BTreeMap<String, String>,
}
impl Preferences {
    pub fn read(data: &Value) -> Result<Self> {
        data.as_object()
            .context(".machine.json must be an object")?;
        let boolean = |key, default| -> Result<bool> {
            match data.get(key) {
                None => Ok(default),
                Some(v) => v
                    .as_bool()
                    .with_context(|| format!("{key} must be true or false")),
            }
        };
        let mut shortcuts = BTreeMap::new();
        if let Some(value) = data.get("shortcuts") {
            for (key, value) in value.as_object().context("shortcuts must be an object")? {
                if value.is_null() {
                    shortcuts.insert(key.clone(), String::new());
                    continue;
                }
                shortcuts.insert(
                    key.clone(),
                    value
                        .as_str()
                        .context("Shortcut must be a string")?
                        .to_string(),
                );
            }
        }
        let remote_client = data["remote_client"]
            .as_str()
            .unwrap_or(
                if data["herdr"].as_str().is_some_and(|s| !s.is_empty())
                    && data["ssh_host"].as_str().is_some_and(|s| !s.is_empty())
                {
                    "herdr"
                } else {
                    "ssh"
                },
            )
            .to_string();
        if !matches!(remote_client.as_str(), "ssh" | "herdr") {
            bail!("remote_client must be ssh or herdr");
        }
        Ok(Self {
            integration_only: boolean("integration_only", false)?,
            session_picker: boolean("session_picker", false)?,
            apply_default: false,
            local_herdr: boolean("local_herdr", false)?,
            remote_client,
            herdr: data["herdr"].as_str().unwrap_or("").into(),
            session_catalog: match data.get("session_catalog") {
                None | Some(Value::Null) => None,
                Some(value) => Some(
                    value
                        .as_str()
                        .context("session_catalog must be a file path")?
                        .into(),
                ),
            },
            shortcuts,
        })
    }
}

/// Windows argv quoting, without a shell. Preserve quotes and terminal backslashes.
pub fn quote(value: &str) -> String {
    if !value.is_empty() && !value.chars().any(|c| c.is_whitespace() || c == '"') {
        return value.into();
    }
    let mut output = String::from("\"");
    let mut slashes = 0;
    for character in value.chars() {
        if character == '\\' {
            slashes += 1;
            continue;
        }
        if character == '"' {
            output.push_str(&"\\".repeat(slashes * 2 + 1));
        } else {
            output.push_str(&"\\".repeat(slashes));
        }
        slashes = 0;
        output.push(character);
    }
    output.push_str(&"\\".repeat(slashes * 2));
    output.push('"');
    output
}
fn command(arguments: &[String]) -> String {
    arguments
        .iter()
        .map(|arg| quote(arg))
        .collect::<Vec<_>>()
        .join(" ")
}

fn chord_identity(chord: &str) -> String {
    let mut parts: Vec<_> = chord
        .split('+')
        .map(|part| part.trim().to_ascii_lowercase())
        .collect();
    parts.sort();
    parts.join("+")
}
fn uses_chord(value: &Value, chord: &str) -> bool {
    match value {
        Value::String(value) => chord_identity(value) == chord_identity(chord),
        Value::Array(values) => values.iter().any(|value| uses_chord(value, chord)),
        _ => false,
    }
}

pub fn render(
    original: &Value,
    shared: &Value,
    root: &Path,
    preferences: &Preferences,
) -> Result<Value> {
    let mut data = original
        .as_object()
        .context("Windows Terminal settings must be an object")?
        .clone();
    if !preferences.integration_only {
        for key in PORTABLE {
            data.remove(*key);
        }
        if let Some(presentation) = shared["terminal"].as_object() {
            for (key, value) in presentation {
                if PORTABLE.contains(&key.as_str()) {
                    data.insert(key.clone(), value.clone());
                }
            }
        }
    }
    if !preferences.integration_only || preferences.apply_default {
        data.insert(
            "defaultProfile".into(),
            json!(if preferences.session_picker {
                SESSIONS
            } else {
                PWSH
            }),
        );
    }
    let mut profiles = data.get("profiles").cloned().unwrap_or(json!({}));
    profiles.as_object().context("profiles must be an object")?;
    if !preferences.integration_only {
        profiles["defaults"] = shared.get("profileDefaults").cloned().unwrap_or(json!({}));
    }
    let mut entries = profiles
        .get("list")
        .cloned()
        .unwrap_or(json!([]))
        .as_array()
        .context("profiles.list must be an array")?
        .clone();
    if entries.iter().any(|entry| !entry.is_object()) {
        bail!("Each profile must be an object");
    }
    if !preferences.integration_only && shared["compactMenu"].as_bool().unwrap_or(true) {
        for entry in &mut entries {
            let guid = entry["guid"].as_str().unwrap_or("");
            let visible = [PWSH, HERDR, PORTS].contains(&guid)
                || guid == LOCAL && preferences.local_herdr
                || guid == SESSIONS && preferences.session_picker
                || entry["source"] == "Microsoft.WSL";
            entry["hidden"] = json!(!visible);
        }
    }
    let native = crate::binary(root, "terminal-workspace")
        .to_string_lossy()
        .into_owned();
    let remote = command(&[
        native.clone(),
        "remote".into(),
        "--client".into(),
        preferences.remote_client.clone(),
        "--herdr".into(),
        preferences.herdr.clone(),
    ]);
    let local = command(&[
        native,
        "remote".into(),
        "--local".into(),
        "--herdr".into(),
        preferences.herdr.clone(),
    ]);
    let ports = command(&[crate::binary(root, "ports").to_string_lossy().into_owned()]);
    let mut session_args = vec![
        crate::binary(root, "ssh-sessions")
            .to_string_lossy()
            .into_owned(),
    ];
    if let Some(catalog) = &preferences.session_catalog {
        session_args.extend(["--catalog".into(), catalog.clone()]);
    }
    let sessions = command(&session_args);
    let mut desired = vec![
        json!({"guid": PWSH, "name":"PowerShell", "source":"Windows.Terminal.PowershellCore", "hidden":false}),
        profile(
            HERDR,
            if preferences.remote_client == "herdr" {
                "Remote Herdr"
            } else {
                "Remote SSH"
            },
            &remote,
            if preferences.remote_client == "herdr" {
                root.join("build/herdr.ico").to_string_lossy().into_owned()
            } else {
                "🖥".into()
            },
            "Remote",
        ),
        profile(PORTS, "Ports", &ports, "🔌".into(), "Ports"),
    ];
    if preferences.session_picker {
        desired.push(profile(
            SESSIONS,
            "SSH Sessions",
            &sessions,
            "🖥".into(),
            "SSH Sessions",
        ));
    }
    if preferences.local_herdr {
        desired.push(profile(
            LOCAL,
            "Local Herdr",
            &local,
            root.join("build/herdr.ico").to_string_lossy().into_owned(),
            "Local Herdr",
        ));
    }
    for entry in &mut entries {
        if entry["guid"] == SESSIONS && !preferences.session_picker
            || entry["guid"] == LOCAL && !preferences.local_herdr
        {
            entry["hidden"] = json!(true);
        }
    }
    for desired in desired {
        let existing = entries
            .iter()
            .position(|entry| entry["guid"] == desired["guid"]);
        if preferences.integration_only && desired["guid"] == PWSH {
            if existing.is_none() && (preferences.session_picker || preferences.apply_default) {
                entries.push(json!({"guid":PWSH,"name":"PowerShell","commandline":"pwsh.exe -NoLogo","hidden":false}));
            }
            continue;
        }
        if let Some(index) = existing {
            entries[index]
                .as_object_mut()
                .unwrap()
                .extend(desired.as_object().unwrap().clone());
        } else {
            entries.push(desired);
        }
    }
    profiles["list"] = json!(entries);
    data.insert("profiles".into(), profiles);
    if !preferences.integration_only {
        data.insert("newTabMenu".into(), json!([{"type":"remainingProfiles"}]));
    }
    let mut actions = data
        .get("actions")
        .cloned()
        .unwrap_or(json!([]))
        .as_array()
        .context("actions must be an array")?
        .clone();
    let mut bindings = data
        .get("keybindings")
        .cloned()
        .unwrap_or(json!([]))
        .as_array()
        .context("keybindings must be an array")?
        .clone();
    let mut managed: BTreeSet<String> = ACTIONS.iter().map(|(_, id)| id.to_string()).collect();
    for action in &actions {
        if action["command"]["profile"]
            .as_str()
            .is_some_and(|guid| [HERDR, PORTS, LOCAL, SESSIONS].contains(&guid))
            && let Some(id) = action["id"].as_str()
        {
            managed.insert(id.into());
        }
    }
    actions.retain(|a| !a["id"].as_str().is_some_and(|id| managed.contains(id)));
    bindings.retain(|a| !a["id"].as_str().is_some_and(|id| managed.contains(id)));
    let mut shortcuts = BTreeMap::<String, String>::new();
    for (key, value) in shared["shortcuts"]
        .as_object()
        .context("Shared shortcuts must be an object")?
    {
        shortcuts.insert(
            key.clone(),
            value
                .as_str()
                .context("Shared shortcut must be text")?
                .into(),
        );
    }
    for (key, value) in [
        ("local", "ctrl+alt+l"),
        ("newLocal", "ctrl+alt+shift+l"),
        ("shell", "ctrl+alt+n"),
    ] {
        shortcuts.entry(key.into()).or_insert(value.into());
    }
    shortcuts.extend(preferences.shortcuts.clone());
    let mut chosen = BTreeSet::new();
    for (key, id) in ACTIONS {
        if (["local", "newLocal"].contains(&key) && !preferences.local_herdr)
            || (key == "shell" && !preferences.session_picker)
            || (key == "newTab" && !shortcuts.get(key).is_some_and(|value| !value.is_empty()))
        {
            continue;
        }
        let chord = shortcuts
            .get(key)
            .filter(|value| !value.is_empty())
            .with_context(|| format!("Missing {key} shortcut"))?;
        if !chosen.insert(chord_identity(chord)) {
            bail!("Each workspace action needs a different shortcut");
        }
        if bindings.iter().any(|b| uses_chord(&b["keys"], chord))
            || actions.iter().any(|a| uses_chord(&a["keys"], chord))
        {
            bail!("Shortcut {chord} is already assigned to another action");
        }
        let profile = match key {
            "herdr" | "newHerdr" => HERDR,
            "local" | "newLocal" => LOCAL,
            "shell" => PWSH,
            "newTab" => {
                if preferences.session_picker {
                    SESSIONS
                } else {
                    PWSH
                }
            }
            _ => PORTS,
        };
        let mut action = json!({"action":"newTab", "profile":profile});
        if ["herdr", "ports", "local"].contains(&key) {
            action["commandline"] = json!(format!(
                "{} --focus-existing",
                match key {
                    "herdr" => &remote,
                    "ports" => &ports,
                    _ => &local,
                }
            ));
        }
        actions.push(json!({"id":id,"command":action}));
        bindings.push(json!({"id":id,"keys":chord}));
    }
    data.insert("actions".into(), json!(actions));
    data.insert("keybindings".into(), json!(bindings));
    Ok(Value::Object(data))
}

fn profile(guid: &str, name: &str, command: &str, icon: String, title: &str) -> Value {
    json!({"guid":guid,"name":name,"commandline":command,"icon":icon,"tabTitle":title,"suppressApplicationTitle":false,"closeOnExit":"automatic","hidden":false,"startingDirectory":"%USERPROFILE%"})
}

pub fn export(data: &Value, shared: &Value) -> Value {
    let mut result = shared.clone();
    result["terminal"] = json!({});
    result["profileDefaults"] = json!({});
    for key in PORTABLE {
        if let Some(value) = data.get(*key) {
            result["terminal"][*key] = value.clone();
        }
    }
    for key in PROFILE_PORTABLE {
        if let Some(value) = data["profiles"]["defaults"].get(*key) {
            result["profileDefaults"][*key] = value.clone();
        }
    }
    for (key, id) in &ACTIONS[..4] {
        if let Some(binding) = data["keybindings"]
            .as_array()
            .and_then(|bindings| bindings.iter().find(|b| b["id"] == *id))
        {
            result["shortcuts"][*key] = binding["keys"].clone();
        }
    }
    result
}

pub fn settings_path() -> Result<PathBuf> {
    let local = dirs::data_local_dir().context("Cannot find LocalAppData")?;
    let packaged =
        local.join("Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json");
    let unpackaged = local.join("Microsoft/Windows Terminal/settings.json");
    Ok(if packaged.exists() || !unpackaged.exists() {
        packaged
    } else {
        unpackaged
    })
}

/// Accept JSON comments/trailing commas without interpreting strings or dates.
pub fn parse(contents: &[u8]) -> Result<Value> {
    let bytes = contents.strip_prefix(b"\xef\xbb\xbf").unwrap_or(contents);
    std::str::from_utf8(bytes).context("Settings must use UTF-8")?;
    let mut cleaned = bytes.to_vec();
    let mut i = 0;
    let mut in_string = false;
    while i < bytes.len() {
        if in_string {
            if bytes[i] == b'\\' {
                i += 2;
                continue;
            }
            if bytes[i] == b'"' {
                in_string = false;
            }
        } else if bytes[i] == b'"' {
            in_string = true;
        } else if bytes[i] == b'/' && bytes.get(i + 1) == Some(&b'/') {
            while i < bytes.len() && bytes[i] != b'\n' {
                cleaned[i] = b' ';
                i += 1;
            }
            continue;
        } else if bytes[i] == b'/' && bytes.get(i + 1) == Some(&b'*') {
            cleaned[i] = b' ';
            cleaned[i + 1] = b' ';
            i += 2;
            while i + 1 < bytes.len() && !(bytes[i] == b'*' && bytes[i + 1] == b'/') {
                cleaned[i] = b' ';
                i += 1;
            }
            if i + 1 == bytes.len() || i >= bytes.len() {
                bail!("Unclosed settings comment");
            }
            cleaned[i] = b' ';
            cleaned[i + 1] = b' ';
            i += 2;
            continue;
        }
        i += 1;
    }
    i = 0;
    in_string = false;
    while i < cleaned.len() {
        if in_string {
            if cleaned[i] == b'\\' {
                i += 2;
                continue;
            }
            if cleaned[i] == b'"' {
                in_string = false;
            }
        } else if cleaned[i] == b'"' {
            in_string = true;
        } else if cleaned[i] == b',' {
            let next = cleaned[i + 1..].iter().find(|b| !b.is_ascii_whitespace());
            if matches!(next, Some(b'}' | b']')) {
                cleaned[i] = b' ';
            }
        }
        i += 1;
    }
    let result: Value = serde_json::from_slice(&cleaned)
        .context("Invalid Windows Terminal settings; original left unchanged")?;
    result.as_object().context("Settings must be an object")?;
    Ok(result)
}

pub fn load(path: &Path) -> Result<Value> {
    match read_bytes(path)? {
        Some(bytes) => parse(&bytes),
        None => Ok(json!({})),
    }
}
pub fn read_bytes(path: &Path) -> Result<Option<Vec<u8>>> {
    match fs::read(path) {
        Ok(bytes) => Ok(Some(bytes)),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(error.into()),
    }
}
pub fn write(path: &Path, value: &Value, expected: Option<&[u8]>, backup: bool) -> Result<()> {
    let parent = path.parent().context("Settings path needs a directory")?;
    fs::create_dir_all(parent)?;
    let current = read_bytes(path)?;
    if current.as_deref() != expected {
        bail!("Settings changed while preparing the update; retry");
    }
    if backup && let Some(bytes) = &current {
        let backup = path.with_file_name(format!(
            "{}.before-workspace-{}.bak",
            path.file_name().unwrap().to_string_lossy(),
            uuid::Uuid::new_v4().simple()
        ));
        fs::write(backup, bytes)?;
    }
    let mut temporary = tempfile::NamedTempFile::new_in(parent)?;
    serde_json::to_writer_pretty(&mut temporary, value)?;
    temporary.write_all(b"\n")?;
    temporary.as_file().sync_all()?;
    if read_bytes(path)?.as_deref() != expected {
        bail!("Settings changed while preparing the update; retry");
    }
    temporary.persist(path)?;
    Ok(())
}
