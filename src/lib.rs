pub mod launch;
pub mod settings;

use anyhow::{Context, Result, bail};
use std::{
    ffi::OsString,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    time::{Duration, Instant},
};

pub fn root(explicit: Option<PathBuf>) -> Result<PathBuf> {
    if let Some(path) = explicit {
        return Ok(std::path::absolute(path)?);
    }
    let executable = std::env::current_exe()?;
    let parent = executable.parent().context("Executable has no directory")?;
    Ok(parent
        .parent()
        .context("Expected the workspace bin directory")?
        .to_path_buf())
}

pub fn binary(root: &Path, name: &str) -> PathBuf {
    root.join("bin").join(format!("{name}.exe"))
}

/// Dispatch a status-only helper without inheriting unrelated caller handles.
/// These callers intentionally inherit the environment/cwd and capture no output.
pub fn dispatch(
    executable: &Path,
    arguments: &[OsString],
    timeout: Duration,
) -> Result<std::process::ExitStatus> {
    #[cfg(windows)]
    let mut child = port_forward_tui::process::spawn_hidden(executable, arguments)?;
    #[cfg(not(windows))]
    let mut child = Command::new(executable)
        .args(arguments)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()?;
    let started = Instant::now();
    loop {
        if let Some(status) = child.try_wait()? {
            return Ok(status);
        }
        if started.elapsed() > timeout {
            let _ = child.kill();
            let cleanup = Instant::now();
            while cleanup.elapsed() < Duration::from_secs(3) {
                if child.try_wait()?.is_some() {
                    break;
                }
                std::thread::sleep(Duration::from_millis(10));
            }
            bail!("Command timed out");
        }
        std::thread::sleep(Duration::from_millis(10));
    }
}

pub fn output(command: &mut Command, timeout: Option<Duration>) -> Result<std::process::Output> {
    use std::io::Read;
    // The interactive selector's TUI remains on the inherited console while
    // stdout carries its single machine-selection JSON response.
    command
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .stdin(Stdio::inherit());
    let mut child = command.spawn()?;
    let mut pipe = child.stdout.take().context("Missing child output")?;
    let reader = std::thread::spawn(move || {
        let mut bytes = Vec::new();
        pipe.by_ref()
            .take(2_097_153)
            .read_to_end(&mut bytes)
            .map(|_| bytes)
    });
    let status = wait_status(&mut child, timeout)?;
    let stdout = reader
        .join()
        .map_err(|_| anyhow::anyhow!("Child output reader failed"))??;
    if stdout.len() > 2_097_152 {
        bail!("Command returned too much output");
    }
    Ok(std::process::Output {
        status,
        stdout,
        stderr: vec![],
    })
}

fn wait_status(
    child: &mut std::process::Child,
    timeout: Option<Duration>,
) -> Result<std::process::ExitStatus> {
    let started = Instant::now();
    loop {
        if let Some(status) = child.try_wait()? {
            return Ok(status);
        }
        if timeout.is_some_and(|timeout| started.elapsed() > timeout) {
            let _ = child.kill();
            let _ = child.wait();
            bail!("Command timed out");
        }
        std::thread::sleep(Duration::from_millis(10));
    }
}
