//! Opt-in, owned ConPTY proof of the real helper -> released chooser -> Files chain.
//! No desktop, profiles, installation, personal catalogs or implicit SSH inputs.
#![cfg(windows)]

#[path = "support/files_channel_gate.rs"]
mod gate;

use portable_pty::{CommandBuilder, MasterPty, PtySize, native_pty_system};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    ffi::c_void,
    fs,
    io::{Read, Write},
    os::windows::{io::AsRawHandle, process::CommandExt},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread,
    time::{Duration, Instant},
};

const SELECTOR_SHA: &str = "c4797d09ebb9bcd0fd239dac2e6a899c10c89b82a019c60a085990100c54d14c";
const BETA_SHA: &str = "9814653d8501ae26775434052d0f3769bf90176a80a5760e0812f295facca3e1";
const F2: &str = "\x1bOQ";
const F8: &str = "\x1b[19~";
const F10: &str = "\x1b[21~";
const SOURCE: [&str; 3] = [
    "files-channel.ps1",
    "scripts/files-channel-common.ps1",
    "config/files-channels.json",
];

fn digest(path: &Path) -> String {
    let mut file = fs::File::open(path).unwrap();
    let mut hash = Sha256::new();
    let mut bytes = [0u8; 65536];
    loop {
        let n = file.read(&mut bytes).unwrap();
        if n == 0 {
            break;
        }
        hash.update(&bytes[..n]);
    }
    format!("{:x}", hash.finalize())
}
fn input(name: &str) -> PathBuf {
    let path =
        PathBuf::from(std::env::var_os(name).unwrap_or_else(|| panic!("Explicit {name} required")));
    assert!(path.is_absolute(), "{name} must be absolute");
    path.canonicalize().unwrap()
}
fn plain(path: &Path) -> String {
    path.to_str()
        .unwrap()
        .strip_prefix(r"\\?\")
        .unwrap_or(path.to_str().unwrap())
        .to_owned()
}
fn write_json(path: &Path, value: &Value) {
    fs::write(path, serde_json::to_vec_pretty(value).unwrap()).unwrap();
}

// The trusted child waits for GO before creating any clients. The parent assigns
// it to this kill-on-close Job first, then releases the barrier. No broad PID kill.
mod owned {
    use super::*;
    type Handle = *mut c_void;
    #[repr(C)]
    struct Basic {
        user: i64,
        job: i64,
        flags: u32,
        min: usize,
        max: usize,
        active: u32,
        affinity: usize,
        priority: u32,
        scheduling: u32,
    }
    #[repr(C)]
    struct Extended {
        basic: Basic,
        io: [u64; 6],
        process_memory: usize,
        job_memory: usize,
        peak_process: usize,
        peak_job: usize,
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn CreateJobObjectW(a: Handle, name: *const u16) -> Handle;
        fn OpenJobObjectW(access: u32, inherit: i32, name: *const u16) -> Handle;
        fn SetInformationJobObject(
            job: Handle,
            class: i32,
            value: *const c_void,
            length: u32,
        ) -> i32;
        fn QueryInformationJobObject(
            job: Handle,
            class: i32,
            value: *mut c_void,
            length: u32,
            written: *mut u32,
        ) -> i32;
        fn AssignProcessToJobObject(job: Handle, process: Handle) -> i32;
        fn IsProcessInJob(process: Handle, job: Handle, result: *mut i32) -> i32;
        fn TerminateJobObject(job: Handle, code: u32) -> i32;
        fn OpenProcess(access: u32, inherit: i32, pid: u32) -> Handle;
        fn QueryFullProcessImageNameW(
            process: Handle,
            flags: u32,
            image: *mut u16,
            size: *mut u32,
        ) -> i32;
        fn WaitForSingleObject(object: Handle, milliseconds: u32) -> u32;
        fn CloseHandle(object: Handle) -> i32;
    }
    pub struct Job {
        handle: Handle,
        terminate: bool,
    }
    impl Job {
        pub fn create(name: &str) -> Self {
            let name: Vec<_> = name.encode_utf16().chain(Some(0)).collect();
            let handle = unsafe { CreateJobObjectW(std::ptr::null_mut(), name.as_ptr()) };
            assert!(!handle.is_null());
            let mut limits: Extended = unsafe { std::mem::zeroed() };
            limits.basic.flags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            assert_ne!(
                unsafe {
                    SetInformationJobObject(
                        handle,
                        9,
                        (&limits as *const Extended).cast(),
                        std::mem::size_of::<Extended>() as u32,
                    )
                },
                0
            );
            Self {
                handle,
                terminate: true,
            }
        }
        pub fn open(name: &str) -> Self {
            let name: Vec<_> = name.encode_utf16().chain(Some(0)).collect();
            let handle = unsafe { OpenJobObjectW(5, 0, name.as_ptr()) }; // query + assign exact returned child
            assert!(!handle.is_null());
            Self {
                handle,
                terminate: false,
            }
        }
        pub fn assign(&self, child: &std::process::Child) {
            assert_ne!(
                unsafe { AssignProcessToJobObject(self.handle, child.as_raw_handle()) },
                0
            );
        }
        pub fn contain_returned_child(&self, child: Handle) -> bool {
            let mut included = 0;
            assert_ne!(
                unsafe { IsProcessInJob(child, self.handle, &mut included) },
                0
            );
            let inherited = included != 0;
            if !inherited {
                assert_ne!(
                    unsafe { AssignProcessToJobObject(self.handle, child) },
                    0,
                    "Cannot assign exact returned helper handle: {}",
                    std::io::Error::last_os_error()
                );
            }
            assert_ne!(
                unsafe { IsProcessInJob(child, self.handle, &mut included) },
                0
            );
            assert_ne!(included, 0, "Exact helper is outside the owned Job");
            inherited
        }
        pub fn pids(&self) -> Vec<u32> {
            // Fixed room for 128 PIDs; exceeding this is a fixture failure.
            let mut buffer = [0usize; 130];
            assert_ne!(
                unsafe {
                    QueryInformationJobObject(
                        self.handle,
                        3,
                        buffer.as_mut_ptr().cast(),
                        std::mem::size_of_val(&buffer) as u32,
                        std::ptr::null_mut(),
                    )
                },
                0
            );
            let counts = unsafe { std::slice::from_raw_parts(buffer.as_ptr().cast::<u32>(), 2) };
            assert!(counts[0] <= 128 && counts[1] == counts[0]);
            let start = 8 / std::mem::size_of::<usize>();
            buffer[start..start + counts[1] as usize]
                .iter()
                .map(|pid| *pid as u32)
                .collect()
        }
        pub fn processes(&self) -> Vec<Process> {
            self.pids().into_iter().map(Process::open).collect()
        }
    }
    impl Drop for Job {
        fn drop(&mut self) {
            unsafe {
                if self.terminate {
                    TerminateJobObject(self.handle, 91);
                }
                CloseHandle(self.handle);
            }
        }
    }
    pub struct Process {
        handle: Handle,
        pub pid: u32,
        pub image: PathBuf,
    }
    impl Process {
        fn open(pid: u32) -> Self {
            let handle = unsafe { OpenProcess(0x100000 | 0x1000, 0, pid) };
            assert!(!handle.is_null(), "Cannot retain owned PID {pid}");
            let mut image = vec![0u16; 32768];
            let mut size = image.len() as u32;
            assert_ne!(
                unsafe { QueryFullProcessImageNameW(handle, 0, image.as_mut_ptr(), &mut size) },
                0
            );
            Self {
                handle,
                pid,
                image: PathBuf::from(String::from_utf16_lossy(&image[..size as usize]))
                    .canonicalize()
                    .unwrap(),
            }
        }
        pub fn exited(&self) -> bool {
            match unsafe { WaitForSingleObject(self.handle, 0) } {
                0 => true,
                258 => false,
                other => panic!("Wait failed {other}"),
            }
        }
    }
    impl Drop for Process {
        fn drop(&mut self) {
            unsafe {
                CloseHandle(self.handle);
            }
        }
    }
}

fn suite(shell: &str, test_name: &str) {
    if let Ok(mode) = std::env::var("FILES_CHOOSER_CHILD") {
        let mut go = [0u8; 2];
        std::io::stdin().read_exact(&mut go).unwrap();
        assert_eq!(&go, b"GO");
        run_case(shell, &mode);
        return;
    }
    // Validate explicit test intent before spawning; normal ignored tests never run this.
    let evidence = input("FILES_CHOOSER_EVIDENCE");
    for mode in ["transfer", "cancel", "quit", "hpcon"] {
        let case = evidence.join(format!("{shell}-{mode}-{}", uuid::Uuid::new_v4().simple()));
        fs::create_dir(&case).unwrap();
        let name = format!("Local\\files-chooser-{}", uuid::Uuid::new_v4().simple());
        let job = owned::Job::create(&name);
        let mut child = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                test_name,
                "--ignored",
                "--nocapture",
                "--test-threads=1",
            ])
            .env("FILES_CHOOSER_CHILD", mode)
            .env("FILES_CHOOSER_CASE", &case)
            .env("FILES_CHOOSER_JOB", name)
            .stdin(Stdio::piped())
            .stdout(fs::File::create(case.join("stdout.txt")).unwrap())
            .stderr(fs::File::create(case.join("stderr.txt")).unwrap())
            .creation_flags(0x08000000)
            .spawn()
            .unwrap();
        job.assign(&child);
        child.stdin.take().unwrap().write_all(b"GO").unwrap();
        let started = Instant::now();
        let status = loop {
            if let Some(status) = child.try_wait().unwrap() {
                break Some(status);
            }
            if started.elapsed() > Duration::from_secs(45) {
                break None;
            }
            thread::sleep(Duration::from_millis(20));
        };
        let mut remaining = job.pids();
        if status.is_some_and(|s| s.success()) {
            let end =
                (Instant::now() + Duration::from_secs(5)).min(started + Duration::from_secs(45));
            while !remaining.is_empty() && Instant::now() < end {
                thread::sleep(Duration::from_millis(10));
                remaining = job.pids();
            }
        }
        write_json(
            &case.join("watchdog.json"),
            &json!({"completed":status.is_some(),"exit":status.and_then(|s|s.code()),"seconds":started.elapsed().as_secs_f64(),"remaining_pids_before_cleanup":remaining,"scope":"assigned owned child tree; trusted startup barrier before clients"}),
        );
        drop(job); // Unconditional owned-tree cleanup, after writing actual result.
        if status.is_none() {
            let _ = child.wait();
        }
        // This parent receipt also runs after a failed or timed-out child.
        let selector = digest(&input("FILES_CHOOSER_SELECTOR"));
        let beta = digest(&input("FILES_CHOOSER_BETA"));
        let source = input("FILES_CHOOSER_SOURCE");
        let sources: Vec<_> = SOURCE.iter().map(|p| digest(&source.join(p))).collect();
        let expected: Vec<String> =
            serde_json::from_str(&std::env::var("FILES_CHOOSER_SOURCE_HASHES").unwrap()).unwrap();
        write_json(
            &case.join("after-cleanup-hashes.json"),
            &json!({"selector":selector,"beta":beta,"source_hashes":sources}),
        );
        assert_eq!(selector, SELECTOR_SHA);
        assert_eq!(beta, BETA_SHA);
        assert_eq!(sources, expected);
        assert!(
            remaining.is_empty(),
            "Owned descendants survived before cleanup: {remaining:?}"
        );
        assert!(
            status.is_some_and(|s| s.success()),
            "{shell}/{mode} FAILED: {}",
            case.display()
        );
        println!("PASS {shell}/{mode}: {}", case.display());
    }
}

#[test]
#[ignore = "Requires explicit released binaries, source pins and owned strict SFTP fixture"]
fn actual_files_helper_powershell() {
    suite("powershell", "actual_files_helper_powershell");
}
#[test]
#[ignore = "Requires explicit released binaries, source pins and owned strict SFTP fixture"]
fn actual_files_helper_pwsh() {
    suite("pwsh", "actual_files_helper_pwsh");
}

struct Session {
    child: Box<dyn portable_pty::Child + Send + Sync>,
    master: Option<Box<dyn MasterPty + Send>>,
    input: Box<dyn Write + Send>,
    output: mpsc::Receiver<Vec<u8>>,
    reader: Option<thread::JoinHandle<()>>,
    overflow: Arc<AtomicBool>,
    reader_error: Arc<std::sync::Mutex<Option<String>>>,
    parser: vt100::Parser,
    raw: Vec<u8>,
    query_tail: Vec<u8>,
    evidence: PathBuf,
    closing: bool,
}
impl Session {
    fn start(command: CommandBuilder, evidence: &Path) -> Self {
        let pair = native_pty_system()
            .openpty(PtySize {
                rows: 32,
                cols: 140,
                pixel_width: 0,
                pixel_height: 0,
            })
            .unwrap();
        let child = pair.slave.spawn_command(command).unwrap();
        drop(pair.slave); // The master below is the final owner of HPCON.
        let input = pair.master.take_writer().unwrap();
        let mut reader = pair.master.try_clone_reader().unwrap();
        let (send, output) = mpsc::sync_channel(64);
        let overflow = Arc::new(AtomicBool::new(false));
        let full = overflow.clone();
        let reader_error = Arc::new(std::sync::Mutex::new(None));
        let errors = reader_error.clone();
        let reader = thread::spawn(move || {
            let mut buffer = [0; 8192];
            loop {
                match reader.read(&mut buffer) {
                    Ok(0) => break,
                    Ok(n) => match send.try_send(buffer[..n].to_vec()) {
                        Ok(()) => {}
                        Err(mpsc::TrySendError::Full(_)) => {
                            full.store(true, Ordering::Release);
                            break;
                        }
                        Err(mpsc::TrySendError::Disconnected(_)) => break,
                    },
                    Err(error) if error.kind() == std::io::ErrorKind::BrokenPipe => break,
                    Err(error) => {
                        *errors.lock().unwrap() = Some(error.to_string());
                        break;
                    }
                }
            }
        });
        let session = Self {
            child,
            master: Some(pair.master),
            input,
            output,
            reader: Some(reader),
            overflow,
            reader_error,
            parser: vt100::Parser::new(32, 140, 0),
            raw: Vec::new(),
            query_tail: Vec::new(),
            evidence: evidence.into(),
            closing: false,
        };
        // Packaged PowerShell can omit inherited Job membership. The real
        // returned handle is assigned before input, without PID rediscovery.
        // Session RAII is already established if assignment fails.
        let job = owned::Job::open(&std::env::var("FILES_CHOOSER_JOB").unwrap());
        let inherited = job.contain_returned_child(session.child.as_raw_handle().unwrap());
        write_json(
            &evidence.join("helper-containment.json"),
            &json!({"helper_pid":session.child.process_id(),"inherited_membership":inherited,"explicit_assignment":!inherited,"membership_verified":true,"before_input":true}),
        );
        session
    }
    fn send(&mut self, text: &str) {
        self.input.write_all(text.as_bytes()).unwrap();
        self.input.flush().unwrap();
    }
    fn check_before_selection(&self, selector: &Path, gate: &gate::Gate) {
        let job = owned::Job::open(&std::env::var("FILES_CHOOSER_JOB").unwrap());
        let processes = job.processes();
        let selector = selector.canonicalize().unwrap();
        assert!(
            processes
                .iter()
                .any(|p| Some(p.pid) == self.child.process_id()),
            "Helper escaped before input"
        );
        assert!(
            processes.iter().any(|p| p.image == selector),
            "Selector escaped before input; no connection permitted"
        );
        assert_eq!(gate.accepted.load(Ordering::Acquire), 0);
        write_json(
            &self.evidence.join("before-selection.json"),
            &json!({"accepted_connections":0,"helper_pid":self.child.process_id(),"processes":processes.iter().map(|p|json!({"pid":p.pid,"image":p.image})).collect::<Vec<_>>() }),
        );
    }
    fn pump(&mut self) {
        assert!(
            !self.overflow.load(Ordering::Acquire),
            "ConPTY bounded output queue overflow"
        );
        let reader_error = self.reader_error.lock().unwrap().clone();
        assert!(
            reader_error.is_none(),
            "ConPTY read failure: {reader_error:?}"
        );
        if let Ok(bytes) = self.output.recv_timeout(Duration::from_millis(10)) {
            self.query_tail.extend(&bytes);
            let queries = self
                .query_tail
                .windows(4)
                .filter(|s| *s == b"\x1b[6n")
                .count();
            let keep = self.query_tail.len().saturating_sub(3);
            self.query_tail.drain(..keep);
            if !self.closing {
                for _ in 0..queries {
                    self.send("\x1b[1;1R");
                }
            }
            self.parser.process(&bytes);
            self.raw.extend(&bytes);
            let excess = self.raw.len().saturating_sub(262144);
            self.raw.drain(..excess);
        }
    }
    fn until(&mut self, reason: &str, seconds: u64, mut condition: impl FnMut(&mut Self) -> bool) {
        let end = Instant::now() + Duration::from_secs(seconds);
        loop {
            self.pump();
            if condition(self) {
                return;
            }
            assert!(
                Instant::now() < end,
                "{reason}: {}",
                self.parser.screen().contents()
            );
        }
    }
    fn expect(&mut self, text: &str) {
        self.until(&format!("Missing {text}"), 15, |s| {
            s.parser.screen().contents().contains(text)
        });
    }
    fn expect_exit(&mut self, text: &str) {
        self.until(&format!("Missing after trigger {text}"), 5, |s| {
            s.parser.screen().contents().contains(text)
        });
    }
    fn absent(&mut self, text: &str) {
        self.until(&format!("Still visible {text}"), 15, |s| {
            !s.parser.screen().contents().contains(text)
        });
    }
    fn settle(&mut self) {
        let end = Instant::now() + Duration::from_millis(220);
        while Instant::now() < end {
            self.pump();
        }
    }
    fn position(&mut self, text: &str) -> (u16, u16) {
        self.expect(text);
        for row in 0..32 {
            for col in 0..140 {
                let line: String = (col..140)
                    .map(|x| {
                        let text = self.parser.screen().cell(row, x).unwrap().contents();
                        if text.is_empty() { " " } else { text }
                    })
                    .collect();
                if line.starts_with(text) {
                    return (col, row);
                }
            }
        }
        panic!("No cell position for {text}")
    }
    fn mouse(&mut self, button: u16, at: (u16, u16), release: bool) {
        self.send(&format!(
            "\x1b[<{};{};{}{}",
            button,
            at.0 + 1,
            at.1 + 1,
            if release { 'm' } else { 'M' }
        ));
    }
    fn click(&mut self, button: u16, at: (u16, u16)) {
        self.mouse(button, at, false);
        self.mouse(button, at, true);
    }
    fn exit_chooser(&mut self) {
        self.send("\x1b");
        let mut code = None;
        self.until("Helper did not exit", 5, |s| {
            code = s.child.try_wait().unwrap();
            code.is_some()
        });
        assert!(code.unwrap().success());
    }
    fn close_master(&mut self) {
        self.closing = true;
        let master = self.master.take().unwrap();
        let (send, done) = mpsc::sync_channel(1);
        let closer = thread::spawn(move || {
            drop(master);
            let _ = send.send(());
        });
        self.until("ClosePseudoConsole did not return", 5, |_| {
            done.try_recv().is_ok()
        });
        closer.join().unwrap();
    }
    fn save(&self) {
        fs::write(
            self.evidence.join("screen.txt"),
            self.parser.screen().contents(),
        )
        .unwrap();
        fs::write(self.evidence.join("tail.raw"), &self.raw).unwrap();
    }
}
impl Drop for Session {
    fn drop(&mut self) {
        // Evidence errors must not skip cleanup. External Job watchdog bounds all joins.
        let _ = fs::write(
            self.evidence.join("screen.txt"),
            self.parser.screen().contents(),
        );
        let _ = fs::write(self.evidence.join("tail.raw"), &self.raw);
        if !matches!(self.child.try_wait(), Ok(Some(_))) {
            let _ = self.child.kill();
        }
        if self.master.is_some() {
            self.closing = true;
            let master = self.master.take().unwrap();
            let closer = thread::spawn(move || drop(master));
            while !closer.is_finished() {
                if let Ok(bytes) = self.output.recv_timeout(Duration::from_millis(10)) {
                    self.parser.process(&bytes);
                }
            }
            let _ = closer.join();
        }
        if let Some(reader) = self.reader.take() {
            while !reader.is_finished() {
                let _ = self.output.recv_timeout(Duration::from_millis(10));
            }
            let _ = reader.join();
        }
        let _ = self.child.wait();
    }
}

fn snapshot(root: &Path) -> BTreeMap<String, String> {
    let mut out = BTreeMap::new();
    if root.exists() {
        for item in fs::read_dir(root).unwrap() {
            let p = item.unwrap().path();
            if p.is_dir() {
                for (key, value) in snapshot(&p) {
                    out.insert(
                        format!("{}/{}", p.file_name().unwrap().to_str().unwrap(), key),
                        value,
                    );
                }
            } else {
                out.insert(p.file_name().unwrap().to_str().unwrap().into(), digest(&p));
            }
        }
    }
    out
}
fn command_json(mut command: Command) -> Value {
    let output = command.creation_flags(0x08000000).output().unwrap();
    assert!(
        output.status.success(),
        "Metadata failed: {} {}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).unwrap()
}

fn run_case(shell: &str, mode: &str) {
    let case = input("FILES_CHOOSER_CASE");
    let selector = input("FILES_CHOOSER_SELECTOR");
    let beta = input("FILES_CHOOSER_BETA");
    assert_eq!(digest(&selector), SELECTOR_SHA);
    assert_eq!(digest(&beta), BETA_SHA);
    let source = input("FILES_CHOOSER_SOURCE");
    let revision = std::env::var("FILES_CHOOSER_REVISION").unwrap();
    assert!(
        revision.len() == 40
            && revision
                .bytes()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
    );
    let hashes: Vec<_> = SOURCE.iter().map(|p| digest(&source.join(p))).collect();
    let expected: Vec<String> =
        serde_json::from_str(&std::env::var("FILES_CHOOSER_SOURCE_HASHES").unwrap()).unwrap();
    assert_eq!(hashes, expected, "Caller must bind reviewed helper source");
    let contract: Value =
        serde_json::from_slice(&fs::read(source.join(SOURCE[2])).unwrap()).unwrap();
    assert_eq!(contract["beta"]["binary_sha256"], BETA_SHA);
    assert_eq!(contract["stable"]["selector_sha256"], SELECTOR_SHA);
    assert_eq!(contract["beta"]["qualification"], "qualified");
    let fixture = input("FILES_CHOOSER_FIXTURE");
    let ready: Value =
        serde_json::from_slice(&fs::read(fixture.join("ready.json")).unwrap()).unwrap();
    assert_eq!(ready["ok"], true);
    assert_eq!(ready["host"], "fixture");
    assert_eq!(
        PathBuf::from(ready["root"].as_str().unwrap())
            .canonicalize()
            .unwrap(),
        fixture
    );
    let config = PathBuf::from(ready["config"].as_str().unwrap())
        .canonicalize()
        .unwrap();
    let remote_root = PathBuf::from(ready["remote"].as_str().unwrap())
        .canonicalize()
        .unwrap();
    assert_eq!(config.parent().unwrap(), fixture);
    assert_eq!(remote_root.parent().unwrap(), fixture);
    assert!(!fixture.join("STOP").exists());
    let original = fs::read_to_string(&config).unwrap();
    let mut fields = BTreeMap::new();
    for line in original.lines().filter(|line| !line.trim().is_empty()) {
        let (key, value) = line.trim().split_once(char::is_whitespace).unwrap();
        assert!(
            fields
                .insert(
                    key.to_ascii_lowercase(),
                    value.trim().trim_matches('"').to_string()
                )
                .is_none(),
            "Duplicate SSH directive"
        );
    }
    assert_eq!(
        fields.keys().cloned().collect::<Vec<_>>(),
        [
            "batchmode",
            "connecttimeout",
            "globalknownhostsfile",
            "host",
            "hostname",
            "identitiesonly",
            "identityagent",
            "identityfile",
            "port",
            "stricthostkeychecking",
            "user",
            "userknownhostsfile"
        ]
    );
    for (key, value) in [
        ("host", "fixture"),
        ("hostname", "127.0.0.1"),
        ("identityagent", "none"),
        ("stricthostkeychecking", "yes"),
        ("globalknownhostsfile", "none"),
        ("batchmode", "yes"),
        ("identitiesonly", "yes"),
    ] {
        assert_eq!(fields[key], value);
    }
    for key in ["identityfile", "userknownhostsfile"] {
        assert_eq!(
            Path::new(&fields[key])
                .canonicalize()
                .unwrap()
                .parent()
                .unwrap(),
            fixture
        );
    }
    let port: u16 = fields["port"].parse().unwrap();
    assert_eq!(ready["port"], port);
    let gate = gate::Gate::start(port);
    let remote = tempfile::Builder::new()
        .prefix("helper-case-")
        .tempdir_in(&remote_root)
        .unwrap()
        .keep();
    let remote = remote.canonicalize().unwrap();
    assert_eq!(fs::read_dir(&remote).unwrap().count(), 0);
    let local = case.join("local 開發 'literal'");
    fs::create_dir(&local).unwrap();
    let local = local.canonicalize().unwrap();
    let meta = case.join("metadata");
    fs::create_dir(&meta).unwrap();
    let state = meta.join("state");
    fs::create_dir(&state).unwrap();
    let catalog = meta.join("catalog.json");
    let known = meta.join("known_hosts");
    let public = fs::read_to_string(fixture.join("host.pub")).unwrap();
    fs::write(&known, format!("fixture-key {public}")).unwrap();
    let config = meta.join("selected_config");
    let selected = original
        .lines()
        .map(|line| match line.split_whitespace().next() {
            Some("Port") => format!(" Port {}", gate.port),
            Some("UserKnownHostsFile") => format!(
                " UserKnownHostsFile \"{}\"",
                plain(&known).replace('\\', "/")
            ),
            _ => line.into(),
        })
        .collect::<Vec<_>>()
        .join("\n")
        + "\n HostKeyAlias fixture-key\n";
    fs::write(&config, selected).unwrap();
    let workspace = case.join("workspace");
    let install = case.join("beta");
    fs::create_dir_all(workspace.join("bin")).unwrap();
    fs::create_dir_all(install.join("bin")).unwrap();
    let selected_exe = workspace.join("bin/ssh-sessions.exe");
    let beta_exe = install.join("bin/ssh-files-beta.exe");
    fs::copy(&selector, &selected_exe).unwrap();
    fs::copy(&beta, &beta_exe).unwrap();
    fs::write(
        install.join(".ssh-files-beta-installer"),
        b"ssh-files-beta\n",
    )
    .unwrap();
    fs::write(install.join("version"), b"0.4.0-beta.1\n").unwrap();
    let metadata_command = || {
        let mut c = Command::new(&selected_exe);
        c.arg("--catalog")
            .arg(&catalog)
            .arg("--state-dir")
            .arg(&state)
            .current_dir(&local)
            .env("SSH_FILES_BIN", plain(&beta_exe));
        c
    };
    let mut c = metadata_command();
    c.args(["import-ssh", "--config"]).arg(&config).args([
        "--host",
        "fixture",
        "--apply",
        "--group",
        "Owned fixtures",
        "--json",
    ]);
    assert_eq!(command_json(c)["applied"], true);
    let mut catalog_value: Value = serde_json::from_slice(&fs::read(&catalog).unwrap()).unwrap();
    let machine = &mut catalog_value["machines"][0];
    machine["name"] = json!("Owned test server");
    let machine_id = machine["id"].as_str().unwrap().to_owned();
    let route = machine["routes"][0].clone();
    let route_id = route["id"].as_str().unwrap().to_owned();
    write_json(&catalog, &catalog_value);
    let remote_wire = plain(&remote).replace('\\', "/");
    let mut machines = serde_json::Map::new();
    machines.insert(
        machine_id.clone(),
        json!([{"id":"saved","name":"Saved project","path":remote_wire}]),
    );
    write_json(
        &meta.join("catalog.json.files.json"),
        &json!({"version":1,"machines":machines}),
    );
    fs::write(local.join("upload-a.txt"), b"first marked payload").unwrap();
    fs::write(local.join("upload-b.txt"), b"second marked payload").unwrap();
    fs::write(local.join("z-unselected.txt"), b"never selected").unwrap();
    fs::write(remote.join("remote-ready.txt"), b"owned preset").unwrap();
    fs::write(remote.join("sentinel.txt"), b"must remain unchanged").unwrap();
    fs::create_dir(remote.join("a-destination")).unwrap();
    if mode != "transfer" {
        fs::File::create(local.join("large.bin"))
            .unwrap()
            .set_len(128 * 1024 * 1024)
            .unwrap();
    }
    let before = snapshot(&meta);
    let mut help = metadata_command();
    help.args(["files", "--help"]);
    let help = help.creation_flags(0x08000000).output().unwrap();
    assert!(help.status.success());
    for flag in ["--route", "--remote", "--json"] {
        assert!(String::from_utf8_lossy(&help.stdout).contains(flag));
    }
    let mut c = metadata_command();
    c.args([
        "files",
        &machine_id,
        "--route",
        &route_id,
        "--remote",
        &remote_wire,
        "--json",
    ]);
    let args = command_json(c);
    let expected_argv = vec![
        plain(&beta_exe),
        "--host".into(),
        "fixture".into(),
        "--hostname".into(),
        "127.0.0.1".into(),
        "--config".into(),
        plain(&config),
        "--user".into(),
        fields["user"].clone(),
        "--port".into(),
        gate.port.to_string(),
        format!(
            "--label=Owned test server | {}",
            route["name"].as_str().unwrap()
        ),
        "--machine-id".into(),
        machine_id,
        "--route-id".into(),
        route_id,
        "--local".into(),
        plain(&local),
        format!("--remote={remote_wire}"),
    ];
    let actual: Vec<String> = serde_json::from_value(args["argv"].clone()).unwrap();
    assert_eq!(actual, expected_argv, "Frozen route/alias/preset changed");
    assert_eq!(snapshot(&meta), before);
    assert_eq!(gate.accepted.load(Ordering::Acquire), 0);
    write_json(
        &case.join("preflight.json"),
        &json!({"selector_sha256":digest(&selector),"beta_sha256":digest(&beta),"source_hashes":hashes,"revision":revision,"argv":actual,"remote":remote,"metadata":before}),
    );
    let shell_path = which::which(shell).unwrap().canonicalize().unwrap();
    let command = || {
        let mut c = CommandBuilder::new(plain(&shell_path));
        c.args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]);
        c.arg(plain(&source.join(SOURCE[0])));
        for (key, value) in [
            ("-Channel", "beta".into()),
            ("-Action", "Launch".into()),
            ("-Version", "0.4.0-beta.1".into()),
            ("-WorkspaceRoot", plain(&workspace)),
            ("-InstallDir", plain(&install)),
            ("-Catalog", plain(&catalog)),
            ("-StateDir", plain(&state)),
            ("-LocalDirectory", plain(&local)),
            ("-IntegrationRevision", revision.clone()),
            ("-SourceSha256", hashes[0].clone()),
            ("-CommonSha256", hashes[1].clone()),
            ("-ContractSha256", hashes[2].clone()),
        ] {
            c.arg(key);
            c.arg(value);
        }
        c.env("TERM", "xterm-256color");
        c.env("SSH_FILES_BIN", case.join("invalid-inherited-sentinel.exe"));
        c.cwd(plain(&local));
        c
    };
    if mode == "transfer" {
        let cancel_dir = case.join("chooser-cancel");
        fs::create_dir(&cancel_dir).unwrap();
        let mut cancelled = Session::start(command(), &cancel_dir);
        cancelled.expect("Choose a server");
        cancelled.expect("Owned fixtures");
        cancelled.expect("Owned test server");
        cancelled.check_before_selection(&selected_exe, &gate);
        assert_eq!(gate.accepted.load(Ordering::Acquire), 0);
        cancelled.exit_chooser();
        drop(cancelled);
        assert_eq!(snapshot(&meta), before);
    }
    let mut session = Session::start(command(), &case);
    session.expect("Choose a server");
    session.expect("Owned test server");
    session.check_before_selection(&selected_exe, &gate);
    assert_eq!(gate.accepted.load(Ordering::Acquire), 0);
    session.send("\x1b[B\x1b[C");
    session.expect("Saved project");
    assert_eq!(gate.accepted.load(Ordering::Acquire), 0);
    session.send("\x1b[B\r");
    session.expect("BETA");
    session.expect("0.4.0-beta.1");
    session.expect("upload-a.txt");
    session.expect("remote-ready.txt");
    if mode == "transfer" {
        session.send("\x1b[C\x1b[C");
        session.send(F2);
        session.expect("Remote directory");
        session.send("\x1b");
        session.absent("Remote directory");
        session.expect("F6 paste paths");
        session.send("\x1b[D\x1b[D");
        session.send(F2);
        session.expect("Local directory");
        session.send("\x1b");
        session.absent("Local directory");
        session.expect("F6 paste paths");
        let a = session.position("upload-a.txt");
        let b = session.position("upload-b.txt");
        session.click(0, a);
        session.click(4, b);
        session.expect("2 marked");
        let target = session.position("a-destination");
        session.mouse(0, a, false);
        session.mouse(32, target, false);
        session.expect("Release to upload");
        session.mouse(0, target, true);
        session.expect("2 complete");
        assert!(
            !session
                .parser
                .screen()
                .contents()
                .contains("Review transfers")
        );
        for name in ["upload-a.txt", "upload-b.txt"] {
            assert_eq!(
                fs::read(remote.join("a-destination").join(name)).unwrap(),
                fs::read(local.join(name)).unwrap()
            );
        }
        assert_eq!(
            fs::read_dir(remote.join("a-destination")).unwrap().count(),
            2
        );
        assert!(!remote.join("a-destination/z-unselected.txt").exists());
        gate.cancelling.store(true, Ordering::Release);
        session.send(F10);
        session.expect("Files closed. Choose another server or path.");
        session.until("Normal Files exit left streams", 5, |_| {
            gate.active.load(Ordering::Acquire) == 0
        });
        session.exit_chooser();
    } else {
        let large = session.position("large.bin");
        session.mouse(0, large, false);
        session.mouse(32, (110, large.1 + 6), false);
        session.expect("Release to upload");
        session.mouse(0, (110, large.1 + 6), true);
        session.until("No fresh transfer partial", 10, |_| {
            fs::read_dir(&remote).unwrap().any(|e| {
                e.unwrap()
                    .file_name()
                    .to_string_lossy()
                    .starts_with(".ssh-files-")
            })
        });
        gate.pause_transfer.store(true, Ordering::Release);
        session.until("Transfer relay did not acknowledge pause", 5, |_| {
            gate.transfer_paused.load(Ordering::Acquire)
        });
        assert_eq!(gate.active.load(Ordering::Acquire), 2);
        assert!(!remote.join("large.bin").exists());
        gate.assert_clean();
        let job = owned::Job::open(&std::env::var("FILES_CHOOSER_JOB").unwrap());
        let all_handles: Vec<_> = job
            .processes()
            .into_iter()
            .filter(|p| p.pid != std::process::id())
            .collect();
        write_json(
            &case.join("job-process-snapshot.json"),
            &json!({"helper_child_pid":session.child.process_id(),"helper_child_status":format!("{:?}",session.child.try_wait().unwrap()),"processes":all_handles.iter().map(|p|json!({"pid":p.pid,"image":p.image})).collect::<Vec<_>>()}),
        );
        let ssh = which::which("ssh").unwrap().canonicalize().unwrap();
        let conhost = PathBuf::from(std::env::var_os("SystemRoot").unwrap())
            .join("System32/conhost.exe")
            .canonicalize()
            .unwrap();
        let expected_targets = [
            shell_path.clone(),
            selected_exe.canonicalize().unwrap(),
            beta_exe.canonicalize().unwrap(),
            ssh.clone(),
        ];
        assert!(
            all_handles
                .iter()
                .all(|p| expected_targets.contains(&p.image) || p.image == conhost),
            "Unexpected executable in owned Job"
        );
        let support:Vec<_>=all_handles.iter().filter(|p|p.image==conhost).map(|p|json!({"pid":p.pid,"image":p.image,"reason":"console host may belong to the still-running test; whole Job must empty after test exit"})).collect();
        let handles: Vec<_> = all_handles
            .into_iter()
            .filter(|p| expected_targets.contains(&p.image))
            .collect();
        for expected in [
            &shell_path,
            &selected_exe.canonicalize().unwrap(),
            &beta_exe.canonicalize().unwrap(),
        ] {
            assert!(
                handles.iter().any(|p| p.image == *expected),
                "Missing live owned {}",
                expected.display()
            );
        }
        assert_eq!(handles.iter().filter(|p| p.image == ssh).count(), 2);
        assert!(handles.iter().all(|p| !p.exited()));
        write_json(
            &case.join("before-trigger.json"),
            &json!({"mode":mode,"active_streams":2,"processes":handles.iter().map(|p|json!({"pid":p.pid,"image":p.image})).collect::<Vec<_>>(),"support_processes_checked_after_test_exit":support,"partial_names":fs::read_dir(&remote).unwrap().map(|e|e.unwrap().file_name().to_string_lossy().to_string()).collect::<Vec<_>>() }),
        );
        gate.cancelling.store(true, Ordering::Release);
        let triggered = Instant::now();
        match mode {
            "cancel" => {
                session.send("\x03");
                session.expect_exit("Stopped:");
                gate.pause_transfer.store(false, Ordering::Release);
                session.until("Cancelled transfer stream remained", 5, |_| {
                    gate.active.load(Ordering::Acquire) == 1
                });
                let marker = format!("after-cancel-{}.txt", uuid::Uuid::new_v4().simple());
                fs::write(remote.join(&marker), b"created after cancel").unwrap();
                session.send("\x1b[C");
                session.send(F8);
                session.expect(&marker);
                assert_eq!(gate.active.load(Ordering::Acquire), 1);
                assert!(!remote.join("large.bin").exists());
                session.send(F10);
                session.expect_exit("Files closed. Choose another server or path.");
                session.until("Browser survived Files exit", 5, |_| {
                    gate.active.load(Ordering::Acquire) == 0
                });
                session.exit_chooser();
            }
            "quit" => {
                session.send(F10);
                session.expect_exit("Close Files?");
                session.settle();
                session.send(F10);
                gate.pause_transfer.store(false, Ordering::Release);
                session.expect_exit("Files closed. Choose another server or path.");
                session.until("Quit left streams", 5, |_| {
                    gate.active.load(Ordering::Acquire) == 0
                });
                session.exit_chooser();
            }
            "hpcon" => {
                session.close_master();
                gate.pause_transfer.store(false, Ordering::Release);
                session.until("HPCON close left owned process or stream", 5, |_| {
                    handles.iter().all(|p| p.exited()) && gate.active.load(Ordering::Acquire) == 0
                });
                let exit = session
                    .child
                    .try_wait()
                    .unwrap()
                    .expect("HPCON helper exit");
                write_json(
                    &case.join("hpcon-exit.json"),
                    &json!({"exit":exit.exit_code(),"success":exit.success(),"seconds":triggered.elapsed().as_secs_f64()}),
                );
            }
            _ => unreachable!(),
        }
        session.until("Owned pre-trigger process survived", 5, |_| {
            handles.iter().all(|p| p.exited())
        });
        assert!(!remote.join("large.bin").exists());
        write_json(
            &case.join("trigger-result.json"),
            &json!({"mode":mode,"seconds":triggered.elapsed().as_secs_f64(),"owned_processes_exited":true,"active_streams":gate.active.load(Ordering::Acquire),"final_absent":true}),
        );
    }
    gate.assert_clean();
    assert_eq!(
        fs::read(remote.join("sentinel.txt")).unwrap(),
        b"must remain unchanged"
    );
    assert_eq!(snapshot(&meta), before);
    assert_eq!(digest(&selector), SELECTOR_SHA);
    assert_eq!(digest(&beta), BETA_SHA);
    assert_eq!(
        SOURCE
            .iter()
            .map(|p| digest(&source.join(p)))
            .collect::<Vec<_>>(),
        hashes
    );
    session.save();
    drop(session);
    drop(gate);
    write_json(
        &case.join("result.json"),
        &json!({"ok":true,"shell":shell,"mode":mode,"selector_sha256":digest(&selector),"beta_sha256":digest(&beta),"source_hashes":hashes,"metadata_preserved":true,"remote":remote,"scope":"owned ConPTY and strict loopback SFTP; no physical desktop or Explorer drop"}),
    );
}
