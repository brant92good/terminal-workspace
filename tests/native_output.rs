//! A status-only launcher must not wait for a long-lived child's output handles.
use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
    thread,
    time::{Duration, Instant},
};
// One case intentionally exposes an inheritable handle. Keep sibling fixture
// compilers/processes from inheriting it and changing the EOF observation.
static FIXTURE_PROCESS: std::sync::Mutex<()> = std::sync::Mutex::new(());
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
    let _serial = FIXTURE_PROCESS
        .lock()
        .unwrap_or_else(|error| error.into_inner());
    let temp = tempfile::tempdir().unwrap();
    let executable = fixture(temp.path());
    let started = Instant::now();
    let result = terminal_workspace::dispatch(
        &executable,
        &["parent".into(), temp.path().as_os_str().to_owned()],
        Duration::from_secs(1),
    );
    let elapsed = started.elapsed();
    // Release the fixture descendant even when the assertion below fails.
    fs::write(temp.path().join("release"), b"finish owned child").unwrap();
    let deadline = Instant::now() + Duration::from_secs(3);
    while !temp.path().join("done").exists() && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(20));
    }
    assert!(temp.path().join("done").exists());
    assert!(result.unwrap().success());
    assert!(
        elapsed < Duration::from_secs(3),
        "Waited on a descendant for {elapsed:?}"
    );
    let started = Instant::now();
    let error =
        terminal_workspace::dispatch(&executable, &["stall".into()], Duration::from_millis(100))
            .unwrap_err();
    assert!(error.to_string().contains("timed out"));
    assert!(started.elapsed() < Duration::from_secs(3));
}

#[cfg(windows)]
#[test]
fn status_only_dispatch_excludes_unrelated_inheritable_handles() {
    let _serial = FIXTURE_PROCESS
        .lock()
        .unwrap_or_else(|error| error.into_inner());
    use std::{ffi::c_void, io::Read, os::windows::io::FromRawHandle, sync::mpsc};
    type Handle = *mut c_void;
    #[repr(C)]
    struct SecurityAttributes {
        size: u32,
        descriptor: Handle,
        inherit: i32,
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn CreatePipe(
            read: *mut Handle,
            write: *mut Handle,
            security: *const SecurityAttributes,
            size: u32,
        ) -> i32;
        fn SetHandleInformation(handle: Handle, mask: u32, flags: u32) -> i32;
        fn CloseHandle(handle: Handle) -> i32;
    }
    let temp = tempfile::tempdir().unwrap();
    let executable = fixture(temp.path());
    let mut read = std::ptr::null_mut();
    let mut write = std::ptr::null_mut();
    let security = SecurityAttributes {
        size: std::mem::size_of::<SecurityAttributes>() as u32,
        descriptor: std::ptr::null_mut(),
        inherit: 1,
    };
    unsafe {
        assert_ne!(CreatePipe(&mut read, &mut write, &security, 0), 0);
        assert_ne!(SetHandleInformation(read, 1, 0), 0);
    }
    let mut pipe = unsafe { fs::File::from_raw_handle(read) };
    let (send, receive) = mpsc::channel();
    thread::spawn(move || {
        let mut bytes = Vec::new();
        let _ = send.send(pipe.read_to_end(&mut bytes));
    });
    let result = terminal_workspace::dispatch(
        &executable,
        &["parent".into(), temp.path().as_os_str().to_owned()],
        Duration::from_secs(1),
    );
    unsafe { CloseHandle(write) };
    let released_before_descendant =
        matches!(receive.recv_timeout(Duration::from_millis(300)), Ok(Ok(0)));
    // The owned descendant has an eight-second self-expiry as a second bound.
    // Release it before asserting so the deliberately failing baseline is safe.
    fs::write(temp.path().join("release"), b"finish owned child").unwrap();
    let deadline = Instant::now() + Duration::from_secs(3);
    while !temp.path().join("done").exists() && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(20));
    }
    assert!(temp.path().join("done").exists());
    if !released_before_descendant {
        assert!(matches!(
            receive.recv_timeout(Duration::from_secs(3)),
            Ok(Ok(0))
        ));
    }
    assert!(result.unwrap().success());
    assert!(
        released_before_descendant,
        "status-only child inherited an unrelated caller pipe"
    );
}
