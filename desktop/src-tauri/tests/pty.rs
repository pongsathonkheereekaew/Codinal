//! PTY session tests — verify spawn/write/resize/kill against a real forkpty.
//!
//! These run only on macOS (the only platform where the PTY module compiles).

#![cfg(target_os = "macos")]

use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use codinal_desktop::pty::{Emit, PtyRegistry};

/// Wait until `predicate` is true, polling every 10ms, up to `timeout`.
/// Used to assert on async reader-thread output.
fn wait_for<T>(timeout: Duration, mut predicate: impl FnMut() -> Option<T>) -> T {
    let deadline = Instant::now() + timeout;
    loop {
        if let Some(value) = predicate() {
            return value;
        }
        if Instant::now() >= deadline {
            panic!("wait_for timed out after {:?}", timeout);
        }
        std::thread::sleep(Duration::from_millis(10));
    }
}

/// Drain a session's emitted bytes into a shared buffer.
fn capture_buffer() -> (Arc<Mutex<Vec<u8>>>, Emit) {
    let buf: Arc<Mutex<Vec<u8>>> = Arc::new(Mutex::new(Vec::new()));
    let buf_clone = Arc::clone(&buf);
    let emit: Emit = Arc::new(move |_sid, chunk| {
        if let Some(bytes) = chunk {
            buf_clone.lock().expect("buf lock").extend_from_slice(bytes);
        }
    });
    (buf, emit)
}

#[test]
fn pty_open_writes_input_and_reads_output() {
    let tmp = tempfile::tempdir().expect("tempdir");
    let (buf, emit) = capture_buffer();
    let registry = PtyRegistry::default();

    // Use /bin/sh for deterministic echo behavior across test machines.
    registry
        .open(
            "s1",
            tmp.path().to_str().unwrap(),
            Some("/bin/sh"),
            80,
            24,
            move |sid, chunk| emit(sid, chunk),
        )
        .expect("open");

    // Write a command whose output we can detect.
    registry
        .write("s1", b"echo pty_alive_marker_42\n")
        .expect("write");

    let captured = wait_for(Duration::from_secs(5), || {
        let guard = buf.lock().expect("buf lock");
        let text = String::from_utf8_lossy(&guard);
        if text.contains("pty_alive_marker_42") {
            Some(text.into_owned())
        } else {
            None
        }
    });

    assert!(captured.contains("pty_alive_marker_42"));
    registry.kill("s1").expect("kill");
}

#[test]
fn pty_exit_emits_none_when_child_exits() {
    let tmp = tempfile::tempdir().expect("tempdir");
    let exited: Arc<Mutex<bool>> = Arc::new(Mutex::new(false));
    let exited_clone = Arc::clone(&exited);
    let registry = PtyRegistry::default();

    registry
        .open(
            "s2",
            tmp.path().to_str().unwrap(),
            Some("/bin/sh"),
            80,
            24,
            move |_sid, chunk| {
                if chunk.is_none() {
                    *exited_clone.lock().expect("lock") = true;
                }
            },
        )
        .expect("open");

    // Tell the shell to exit; the reader should hit EOF and emit None.
    registry.write("s2", b"exit 0\n").expect("write");

    wait_for(Duration::from_secs(5), || {
        if *exited.lock().expect("lock") {
            Some(())
        } else {
            None
        }
    });
}

#[test]
fn pty_resize_does_not_error() {
    let tmp = tempfile::tempdir().expect("tempdir");
    let (_, emit) = capture_buffer();
    let registry = PtyRegistry::default();

    registry
        .open(
            "s3",
            tmp.path().to_str().unwrap(),
            Some("/bin/sh"),
            80,
            24,
            move |sid, chunk| emit(sid, chunk),
        )
        .expect("open");

    // Resize to 120x40; should succeed without error. (Visual confirmation
    // that the child sees the new size via `stty size` is a manual smoke
    // test — here we only assert the TIOCSWINSZ ioctl didn't fail.)
    registry.resize("s3", 120, 40).expect("resize");

    registry.kill("s3").expect("kill");
}

#[test]
fn pty_kill_removes_session_from_registry() {
    let tmp = tempfile::tempdir().expect("tempdir");
    let (_, emit) = capture_buffer();
    let registry = PtyRegistry::default();

    registry
        .open(
            "s4",
            tmp.path().to_str().unwrap(),
            Some("/bin/sh"),
            80,
            24,
            move |sid, chunk| emit(sid, chunk),
        )
        .expect("open");

    assert!(registry.kill("s4").expect("kill"));
    // Second kill returns false (already removed).
    assert!(!registry.kill("s4").expect("kill second"));
    // Writes after kill fail with NotFound.
    let err = registry.write("s4", b"x").unwrap_err();
    assert_eq!(err.kind(), std::io::ErrorKind::NotFound);
}

#[test]
fn pty_write_to_unknown_session_errors() {
    let registry = PtyRegistry::default();
    let err = registry.write("nonexistent", b"x").unwrap_err();
    assert_eq!(err.kind(), std::io::ErrorKind::NotFound);
}
