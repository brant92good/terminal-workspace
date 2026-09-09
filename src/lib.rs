pub mod launch;
pub mod settings;

use anyhow::{Context, Result, bail};
use std::{
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

pub fn hidden(command: &mut Command) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    #[cfg(not(windows))]
    let _ = command;
}

pub fn output(
    command: &mut Command,
    timeout: Option<Duration>,
    interactive: bool,
) -> Result<std::process::Output> {
    use std::io::Read;
    command
        .stdout(if interactive {
            Stdio::piped()
        } else {
            Stdio::null()
        })
        .stderr(if interactive {
            Stdio::inherit()
        } else {
            Stdio::null()
        });
    command.stdin(if interactive {
        Stdio::inherit()
    } else {
        Stdio::null()
    });
    if !interactive {
        hidden(command);
    }
    let mut child = command.spawn()?;
    if !interactive {
        // These callers dispatch work or check status; they do not consume
        // output. In particular, wt.exe may leave long-lived tabs inheriting
        // its handles. Do not wait for those tabs to close an unused pipe.
        return Ok(std::process::Output {
            status: wait_status(&mut child, timeout)?,
            stdout: vec![],
            stderr: vec![],
        });
    }
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
