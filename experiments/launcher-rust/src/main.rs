//! Measurement-only return launcher. This is not an installed application.
//! Machine selection/new-view fallback stay outside this experiment's contract.
use base64::{Engine, engine::general_purpose::STANDARD};
use serde_json::{Value, json};
use std::os::windows::process::CommandExt;
use std::{
    env, fs, io,
    path::Path,
    process::{Command, ExitCode, Stdio},
    time::{SystemTime, UNIX_EPOCH},
};
use windows_sys::Win32::{
    Foundation::{CloseHandle, HANDLE, WAIT_OBJECT_0, WAIT_TIMEOUT},
    System::{
        Console::SetConsoleTitleW,
        Threading::{
            CREATE_BREAKAWAY_FROM_JOB, CREATE_NO_WINDOW, CreateEventW, OpenProcess,
            PROCESS_SYNCHRONIZE, WaitForMultipleObjects, WaitForSingleObject,
        },
    },
    UI::WindowsAndMessaging::AllowSetForegroundWindow,
};

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

// All owned Win32 handles are closed once, including on early returns.
struct Handle(HANDLE);
impl Handle {
    fn new(raw: HANDLE) -> io::Result<Self> {
        if raw.is_null() {
            Err(io::Error::last_os_error())
        } else {
            Ok(Self(raw))
        }
    }
}
impl Drop for Handle {
    fn drop(&mut self) {
        // SAFETY: constructed only from successful owned handle-returning calls.
        unsafe {
            CloseHandle(self.0);
        }
    }
}

fn wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(Some(0)).collect()
}

fn alive(pid: u32) -> bool {
    // SAFETY: scalar PID/access arguments; returned handle is owned here.
    let Ok(handle) = Handle::new(unsafe { OpenProcess(PROCESS_SYNCHRONIZE, 0, pid) }) else {
        return false;
    };
    // SAFETY: handle remains live throughout this nonblocking wait.
    unsafe { WaitForSingleObject(handle.0, 0) == WAIT_TIMEOUT }
}

fn read_json(path: &Path) -> Result<Value> {
    Ok(serde_json::from_slice(&fs::read(path)?)?)
}
fn string<'a>(data: &'a Value, key: &str) -> Result<&'a str> {
    data[key]
        .as_str()
        .ok_or_else(|| format!("Expected string field: {key}").into())
}

/// The same observable operation as the Python control: read scope and live
/// views, then produce the existing native helper's payload. No UI imports.
fn prepare(plan: &Value) -> Result<Value> {
    let mode = string(plan, "mode")?;
    if mode != "ports" && mode != "records" {
        return Err("Invalid mode".into());
    }
    let settings = Path::new(string(plan, "settings")?).join("ui-settings.json");
    let scope = if settings.exists() {
        let data = read_json(&settings)?;
        data.get("focus_scope").cloned().unwrap_or(json!("all"))
    } else {
        json!("all")
    };
    if scope != "all" && scope != "window" {
        return Err("Invalid focus_scope".into());
    }
    let views = Path::new(string(plan, "views")?);
    let mut records = Vec::new();
    let mut titles = Vec::new();
    if views.exists() {
        for entry in fs::read_dir(views)? {
            let path = entry?.path();
            if path.extension().and_then(|x| x.to_str()) != Some("json") {
                continue;
            }
            let Ok(record) = read_json(&path) else {
                continue;
            };
            let Some(pid) = record["pid"]
                .as_u64()
                .and_then(|x| u32::try_from(x).ok())
                .filter(|p| *p > 0)
            else {
                continue;
            };
            if mode == "ports"
                && !record["title"]
                    .as_str()
                    .is_some_and(|s| s.starts_with("Ports | "))
            {
                continue;
            }
            if !alive(pid) {
                let _ = fs::remove_file(path);
                continue;
            }
            if mode == "ports" {
                let timestamp = match record.get("last_focus") {
                    None => 0.0,
                    Some(value) => match value
                        .as_f64()
                        .or_else(|| value.as_str().and_then(|s| s.parse().ok()))
                    {
                        Some(value) if value.is_finite() => value,
                        _ => continue,
                    },
                };
                titles.push((timestamp, record["title"].as_str().unwrap().to_owned()));
            } else {
                records.push(record);
            }
        }
    }
    let (flag, payload) = if mode == "ports" {
        titles.sort_by(|a, b| b.0.total_cmp(&a.0).then_with(|| b.1.cmp(&a.1)));
        (
            "-TitlesBase64",
            json!(
                titles
                    .into_iter()
                    .map(|(_, title)| title)
                    .collect::<Vec<_>>()
            ),
        )
    } else {
        ("-RecordsBase64", json!(records))
    };
    Ok(json!({"scope": scope, "flag": flag, "payload": payload}))
}

/// Keep the production handoff: named event, detached helper, wait for match,
/// exit launcher, then the same helper waits for tab closure and focuses it.
fn focus(plan: &Value, prepared: &Value) -> Result<bool> {
    if prepared["payload"].as_array().is_none_or(|a| a.is_empty()) {
        return Ok(false);
    }
    let nonce = format!(
        "{}-{}",
        std::process::id(),
        SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos()
    );
    let title = format!("Shortcut | {nonce}");
    let title_wide = wide(&title);
    // SAFETY: a live, nul-terminated UTF-16 buffer is borrowed for this call.
    if unsafe { SetConsoleTitleW(title_wide.as_ptr()) } == 0 {
        return Err(io::Error::last_os_error().into());
    }
    let name = format!("Local\\PortsFocus-{nonce}");
    let name_wide = wide(&name);
    // SAFETY: default security, manual reset, unsignalled; name lives through call.
    let ready = Handle::new(unsafe { CreateEventW(std::ptr::null(), 1, 0, name_wide.as_ptr()) })?;
    let payload = STANDARD.encode(serde_json::to_vec(&prepared["payload"])?);
    let mut command = Command::new(string(plan, "helper")?);
    command.args([
        string(prepared, "flag")?,
        &payload,
        "-Scope",
        string(prepared, "scope")?,
        "-OriginTitle",
        &title,
        "-ReadyEvent",
        &name,
        "-AfterPid",
        &std::process::id().to_string(),
    ]);
    if let Some(trace) = plan["trace"].as_str() {
        command.args(["-TracePath", trace]);
    }
    let mut child = command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .creation_flags(CREATE_NO_WINDOW | CREATE_BREAKAWAY_FROM_JOB)
        .spawn()?;
    // SAFETY: scalar PID of the child we just started.
    unsafe {
        AllowSetForegroundWindow(child.id());
    }
    // SAFETY: requesting a synchronization handle to our child, owned on success.
    let child_handle = Handle::new(unsafe { OpenProcess(PROCESS_SYNCHRONIZE, 0, child.id()) });
    let matched = match child_handle {
        Ok(handle) => {
            let handles = [ready.0, handle.0];
            // SAFETY: both handles are live for the entire bounded wait.
            unsafe { WaitForMultipleObjects(2, handles.as_ptr(), 0, 5000) == WAIT_OBJECT_0 }
        }
        Err(_) => false,
    };
    if !matched {
        let _ = child.kill();
        let _ = child.wait();
    }
    Ok(matched)
}

fn run() -> Result<bool> {
    let args: Vec<_> = env::args_os().skip(1).collect();
    if args.len() == 1 && args[0] == "--noop" {
        return Ok(true);
    }
    if args.is_empty() || args.len() > 2 || (args.len() == 2 && args[1] != "--prepare") {
        return Err("Usage: launcher-experiment PLAN.json [--prepare] | --noop".into());
    }
    let plan = read_json(Path::new(&args[0]))?;
    let prepared = prepare(&plan)?;
    if args.len() == 2 {
        println!("{prepared}");
        return Ok(true);
    }
    focus(&plan, &prepared)
}

fn main() -> ExitCode {
    match run() {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::from(1),
        Err(error) => {
            eprintln!("Launcher experiment: {error}");
            ExitCode::from(2)
        }
    }
}
