//! A status-only launcher must not wait for a long-lived child's output handles.
use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
    thread,
    time::{Duration, Instant},
};
fn fixture(root: &Path) -> PathBuf {
    let source = root.join("fixture.rs");
    fs::write(&source, r#"
use std::{env,fs,path::PathBuf,process::Command,thread,time::{Duration,Instant}};
fn main() {
 let args=env::args().collect::<Vec<_>>();
 if args[1]=="stall" { thread::sleep(Duration::from_secs(8)); return; }
 let directory=PathBuf::from(&args[2]);
 if args[1]=="child" {
  let deadline=Instant::now()+Duration::from_secs(8);
  while !directory.join("release").exists() && Instant::now()<deadline {thread::sleep(Duration::from_millis(20));}
  fs::write(directory.join("done"),"done").unwrap(); return;
 }
 Command::new(env::current_exe().unwrap()).arg("child").arg(directory).spawn().unwrap();
 println!("launcher exited");
}
"#).unwrap();
    let executable = root.join(if cfg!(windows) {
        "fixture.exe"
    } else {
        "fixture"
    });
    let result = Command::new("rustc")
        .arg("--edition=2024")
        .arg(source)
        .arg("-o")
        .arg(&executable)
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    executable
}
#[test]
fn status_only_dispatch_does_not_wait_for_descendant_pipe_and_timeout_still_works() {
    let temp = tempfile::tempdir().unwrap();
    let executable = fixture(temp.path());
    let started = Instant::now();
    let result = terminal_workspace::output(
        Command::new(&executable).arg("parent").arg(temp.path()),
        Some(Duration::from_secs(1)),
        false,
    );
    let elapsed = started.elapsed();
    // Release the fixture descendant even when the assertion below fails.
    fs::write(temp.path().join("release"), b"finish owned child").unwrap();
    let deadline = Instant::now() + Duration::from_secs(3);
    while !temp.path().join("done").exists() && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(20));
    }
    assert!(temp.path().join("done").exists());
    assert!(result.unwrap().status.success());
    assert!(
        elapsed < Duration::from_secs(3),
        "Waited on a descendant for {elapsed:?}"
    );
    let started = Instant::now();
    let error = terminal_workspace::output(
        Command::new(&executable).arg("stall"),
        Some(Duration::from_millis(100)),
        false,
    )
    .unwrap_err();
    assert!(error.to_string().contains("timed out"));
    assert!(started.elapsed() < Duration::from_secs(3));
}
