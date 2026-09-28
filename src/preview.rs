//! Explicit device-local Ports preview selection. Public installations stay on the bundle.
use anyhow::{Context, Result, ensure};
use serde::Deserialize;
use std::{
    fs,
    path::{Path, PathBuf},
};

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Ports {
    pub schema_version: u32,
    pub executable: PathBuf,
    pub data_directory: PathBuf,
}

pub fn load(root: &Path) -> Result<Option<Ports>> {
    let path = root.join("ports-preview.json");
    let bytes = match fs::read(&path) {
        Ok(bytes) => bytes,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error.into()),
    };
    let value: Ports = serde_json::from_slice(&bytes).context("Invalid ports-preview.json")?;
    ensure!(
        value.schema_version == 1,
        "Unsupported Ports preview configuration"
    );
    ensure!(
        value.executable.is_absolute() && value.executable.is_file(),
        "Ports preview executable is missing or not absolute"
    );
    ensure!(
        value.data_directory.is_absolute() && value.data_directory.is_dir(),
        "Ports preview needs its existing isolated data directory"
    );
    ensure!(
        fs::read(value.data_directory.join(".ports-channel"))? == b"beta\n",
        "Ports preview needs beta-owned data"
    );
    let stable = dirs::data_local_dir()
        .context("Cannot find local data")?
        .join("PortForwardTUI");
    let resolved = value.data_directory.canonicalize()?;
    let stable = if stable.exists() {
        stable.canonicalize()?
    } else {
        stable
    };
    let normalized = |path: &Path| {
        PathBuf::from(
            path.to_string_lossy()
                .trim_start_matches("\\\\?\\")
                .to_lowercase(),
        )
    };
    let (resolved, stable) = (normalized(&resolved), normalized(&stable));
    ensure!(
        !resolved.starts_with(&stable) && !stable.starts_with(&resolved),
        "Ports preview cannot use stable data"
    );
    Ok(Some(value))
}

pub fn executable(root: &Path) -> Result<PathBuf> {
    Ok(load(root)?.map_or_else(|| crate::binary(root, "ports"), |p| p.executable))
}

/// Resolve and validate one executable/data pair before a child is launched.
pub fn selected(root: &Path, directory: &Path) -> Result<(PathBuf, bool)> {
    if let Some(preview) = load(root)? {
        ensure!(
            directory.canonicalize()? == preview.data_directory.canonicalize()?,
            "Ports preview selection changed; retry with its configured data directory"
        );
        Ok((preview.executable, true))
    } else {
        reject_beta(directory)?;
        Ok((crate::binary(root, "ports"), false))
    }
}
fn reject_beta(directory: &Path) -> Result<()> {
    let directory = if directory.exists() {
        directory.canonicalize()?
    } else {
        std::path::absolute(directory)?
    };
    ensure!(
        !directory
            .ancestors()
            .any(|p| p.join(".ports-channel").exists()),
        "Bundled Ports cannot use beta-owned data; select the preview explicitly"
    );
    Ok(())
}

pub fn directory(root: &Path, explicit: Option<PathBuf>) -> Result<PathBuf> {
    if let Some(preview) = load(root)? {
        if let Some(explicit) = explicit {
            ensure!(
                explicit.canonicalize()? == preview.data_directory.canonicalize()?,
                "This workspace uses isolated Ports preview data; the requested data directory differs"
            );
        }
        return Ok(preview.data_directory);
    }
    let directory = explicit.unwrap_or(
        dirs::data_local_dir()
            .context("Cannot find application data")?
            .join("PortForwardTUI"),
    );
    reject_beta(&directory)?;
    Ok(directory)
}
