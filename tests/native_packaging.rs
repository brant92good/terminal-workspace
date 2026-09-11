#![cfg(windows)]
use std::{os::windows::process::CommandExt, path::Path, process::Command};

#[test]
fn ports_archive_requires_exact_payloads_and_hash_index_before_extraction() {
    for shell in ["powershell.exe", "pwsh.exe"] {
        let fixture = tempfile::tempdir().unwrap();
        let output = Command::new(shell)
            .args([
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
            ])
            .arg(Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/ports_release_archive.ps1"))
            .arg("-FixtureRoot")
            .arg(fixture.path())
            .creation_flags(0x08000000)
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{shell}: {}\n{}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
        assert_eq!(
            String::from_utf8_lossy(&output.stdout)
                .lines()
                .filter(|line| line.starts_with("PASS "))
                .count(),
            13
        );
    }
}
