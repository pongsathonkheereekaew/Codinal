//! Persistent interactive PTY sessions for the trusted user terminal.
//!
//! Unlike the agent's `run_shell` tool (which runs one-shot commands inside a
//! macOS seatbelt sandbox with no network and a temp HOME), these sessions are
//! **trusted user actions**: the user is typing interactively, like their own
//! Terminal.app. The child runs unsandboxed, with the real HOME, so the
//! terminal can do what the sandbox forbids — `git push`, `npm install`,
//! interactive TUI apps (vim, htop, less).
//!
//! The PTY is a kernel object owned entirely by the Rust shell; the Python
//! control plane never touches it. Output streams through a shell-owned
//! callback, keeping lifecycle and byte transport independent of the UI.

#![cfg(target_os = "macos")]

use std::collections::{HashMap, VecDeque};
use std::io;
use std::os::fd::{AsRawFd, RawFd};
use std::os::unix::process::CommandExt;
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use nix::pty::{openpty, Winsize};
use nix::sys::signal::Signal;
use nix::sys::wait::{waitpid, WaitStatus};
use nix::unistd::{ForkResult, Pid};

/// Callback the reader thread invokes per output chunk (`Some`) and once on
/// EOF / child exit (`None`). Wired to the active desktop shell by the caller.
pub type Emit = Arc<dyn Fn(&str, Option<&[u8]>) + Send + Sync>;

/// Default winsize when the frontend has not measured yet. (Referenced from
/// the frontend's open call; kept as the documented fallback.)
#[allow(dead_code)]
const DEFAULT_COLS: u16 = 80;
#[allow(dead_code)]
const DEFAULT_ROWS: u16 = 24;

pub const DEFAULT_OUTPUT_CAPACITY: usize = 1024 * 1024;

#[derive(Default)]
struct PtyOutputState {
    bytes: VecDeque<u8>,
    next_cursor: u64,
    exited: bool,
}

#[derive(Debug, PartialEq, Eq)]
pub struct PtyOutputDelta {
    pub bytes: Vec<u8>,
    pub next_cursor: u64,
    pub truncated: bool,
    pub exited: bool,
}

/// Bounded shell-neutral PTY output model suitable for native UI polling.
pub struct PtyOutputBuffer {
    capacity: usize,
    state: Mutex<PtyOutputState>,
}

impl Default for PtyOutputBuffer {
    fn default() -> Self {
        Self::new(DEFAULT_OUTPUT_CAPACITY)
    }
}

impl PtyOutputBuffer {
    pub fn new(capacity: usize) -> Self {
        Self {
            capacity: capacity.max(1),
            state: Mutex::new(PtyOutputState::default()),
        }
    }

    pub fn push(&self, bytes: &[u8]) {
        let mut state = self.state.lock().expect("pty output lock poisoned");
        state.next_cursor = state.next_cursor.saturating_add(bytes.len() as u64);
        let overflow = state
            .bytes
            .len()
            .saturating_add(bytes.len())
            .saturating_sub(self.capacity);
        let retained_len = state.bytes.len();
        state.bytes.drain(..overflow.min(retained_len));
        let start = bytes.len().saturating_sub(self.capacity);
        state.bytes.extend(&bytes[start..]);
    }

    pub fn mark_exited(&self) {
        self.state.lock().expect("pty output lock poisoned").exited = true;
    }

    pub fn read_since(&self, cursor: u64) -> PtyOutputDelta {
        let state = self.state.lock().expect("pty output lock poisoned");
        let retained_start = state.next_cursor.saturating_sub(state.bytes.len() as u64);
        let truncated = cursor < retained_start || cursor > state.next_cursor;
        let effective_cursor = if truncated { retained_start } else { cursor };
        let skip = effective_cursor.saturating_sub(retained_start) as usize;
        PtyOutputDelta {
            bytes: state.bytes.iter().skip(skip).copied().collect(),
            next_cursor: state.next_cursor,
            truncated,
            exited: state.exited,
        }
    }
}

/// A live interactive PTY session and its background reader.
pub struct PtySession {
    #[allow(dead_code)]
    session_id: String,
    master: Arc<MasterFd>,
    child: Pid,
    /// Set when the reader thread has finished (EOF on master / child exit).
    #[allow(dead_code)]
    finished: Arc<AtomicBool>,
    reader: Option<thread::JoinHandle<()>>,
}

impl PtySession {
    /// Returns the child PID (for diagnostics / kill).
    pub fn child_pid(&self) -> Pid {
        self.child
    }

    /// Write user input (keystrokes) to the PTY master end.
    pub fn write_input(&self, data: &[u8]) -> io::Result<()> {
        let guard = self.master.0.lock().expect("master lock poisoned");
        let fd = guard.as_raw_fd();
        let mut remaining = data;
        while !remaining.is_empty() {
            // SAFETY: fd is a valid open master; remaining points to writable bytes.
            let rc = unsafe { libc::write(fd, remaining.as_ptr() as *const _, remaining.len()) };
            if rc < 0 {
                let err = io::Error::last_os_error();
                if err.kind() == io::ErrorKind::Interrupted {
                    continue;
                }
                return Err(err);
            }
            remaining = &remaining[rc as usize..];
        }
        Ok(())
    }

    /// Resize the PTY window (SIGWINCH-equivalent via TIOCSWINSZ on master).
    pub fn resize(&self, cols: u16, rows: u16) -> io::Result<()> {
        let fd = self.master.as_raw_fd();
        let winsize = Winsize {
            ws_col: cols.max(1),
            ws_row: rows.max(1),
            ws_xpixel: 0,
            ws_ypixel: 0,
        };
        // SAFETY: TIOCSWINSZ is a well-formed ioctl that takes a winsize ptr.
        let rc = unsafe { libc::ioctl(fd, libc::TIOCSWINSZ, &winsize as *const Winsize) };
        if rc < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
}

impl Drop for PtySession {
    fn drop(&mut self) {
        // Best-effort cleanup: kill the child group and reap it so we don't
        // leak zombies. Errors are ignored — the session is being torn down.
        let _ = nix::sys::signal::kill(self.child, Some(Signal::SIGKILL));
        // Reap if still around. Non-blocking: don't hang Drop on a wedged child.
        for _ in 0..50 {
            match waitpid(self.child, Some(nix::sys::wait::WaitPidFlag::WNOHANG)) {
                Ok(WaitStatus::StillAlive) => thread::sleep(Duration::from_millis(10)),
                _ => break,
            }
        }
        if let Some(handle) = self.reader.take() {
            let _ = handle.join();
        }
    }
}

/// Newtype around the master `OwnedFd` so it can be shared across threads via
/// Arc<Mutex>. Reading happens via raw `libc::read` against `as_raw_fd()` to
/// avoid the borrow-checker friction of `OwnedFd` (which has no `read`).
struct MasterFd(Mutex<std::os::fd::OwnedFd>);

impl AsRawFd for MasterFd {
    fn as_raw_fd(&self) -> RawFd {
        self.0.lock().expect("master lock poisoned").as_raw_fd()
    }
}

/// Spawns a child in a new PTY and returns the session.
///
/// `emit` is called from the reader thread for each chunk of bytes read and
/// again with `None` when the child exits.
pub fn spawn(
    session_id: String,
    workspace: &str,
    shell: Option<&str>,
    cols: u16,
    rows: u16,
    emit: impl Fn(&str, Option<&[u8]>) + Send + Sync + 'static,
) -> io::Result<PtySession> {
    let winsize = Winsize {
        ws_col: cols.max(1),
        ws_row: rows.max(1),
        ws_xpixel: 0,
        ws_ypixel: 0,
    };
    let pty = openpty(&winsize, None)?;

    // SAFETY: fork() is the textbook-unsafe call. After forkpty-style split
    // (we do a manual openpty + fork + dup2 + exec), in the child we may only
    // call async-signal-safe functions before exec.
    let fork_result = unsafe { nix::unistd::fork() }
        .map_err(|e| io::Error::other(format!("fork failed: {e}")))?;

    match fork_result {
        ForkResult::Parent { child } => {
            // Parent: drop the slave end (child owns its copy now). Keep master.
            drop(pty.slave);
            let master = Arc::new(MasterFd(Mutex::new(pty.master)));

            let finished = Arc::new(AtomicBool::new(false));
            let reader_finished = Arc::clone(&finished);
            let reader_master = Arc::clone(&master);
            let reader_id = session_id.clone();
            let reader_emit: Emit = Arc::new(emit);

            let reader = thread::Builder::new()
                .name(format!("pty-reader-{reader_id}"))
                .spawn(move || {
                    let mut buf = [0u8; 4096];
                    loop {
                        // Read under the lock so we don't race Drop's close.
                        let n = {
                            let guard = match reader_master.0.lock() {
                                Ok(g) => g,
                                Err(_) => break,
                            };
                            let fd = guard.as_raw_fd();
                            // SAFETY: fd is a valid open master until we drop guard.
                            let rc =
                                unsafe { libc::read(fd, buf.as_mut_ptr() as *mut _, buf.len()) };
                            if rc < 0 {
                                let err = io::Error::last_os_error();
                                if err.kind() == io::ErrorKind::Interrupted {
                                    continue;
                                }
                                break;
                            }
                            rc as usize
                        };
                        if n == 0 {
                            break; // EOF
                        }
                        (reader_emit)(&reader_id, Some(&buf[..n]));
                    }
                    reader_finished.store(true, Ordering::SeqCst);
                    (reader_emit)(&reader_id, None);
                })?;

            Ok(PtySession {
                session_id,
                master,
                child,
                finished,
                reader: Some(reader),
            })
        }
        ForkResult::Child => {
            // Child: become session leader, wire slave as stdio, then exec.
            // Only async-signal-safe calls until exec. Use raw libc (not nix)
            // to avoid allocations inside fork's child branch.
            let slave_fd = pty.slave.as_raw_fd();
            let master_fd = pty.master.as_raw_fd();
            // Prevent OwnedFd Drop from closing these (we manage them by hand
            // in the child via dup2 + close before exec).
            std::mem::forget(pty.slave);
            std::mem::forget(pty.master);
            // SAFETY: we are in the child of fork(); these syscalls set up the
            // controlling tty and stdio before exec. Async-signal-safe.
            unsafe {
                libc::setsid();
                for dst in [0, 1, 2] {
                    if libc::dup2(slave_fd, dst) < 0 {
                        libc::_exit(127);
                    }
                }
                if slave_fd > 2 {
                    libc::close(slave_fd);
                }
                libc::close(master_fd);
            }

            let shell_str: String = match shell {
                Some(s) => s.to_owned(),
                None => std::env::var("SHELL").unwrap_or_else(|_| "/bin/zsh".to_owned()),
            };
            // Build the child via std::process::Command so env + cwd set up
            // happens through the safe API, then exec manually.
            let mut cmd = Command::new(&shell_str);
            cmd.current_dir(workspace);
            cmd.env_clear();
            // Trusted user terminal: real HOME + a minimal working env.
            if let Ok(home) = std::env::var("HOME") {
                cmd.env("HOME", home);
            }
            cmd.env("TERM", "xterm-256color");
            for key in ["PATH", "LANG", "LC_ALL", "LC_CTYPE", "USER", "LOGNAME"] {
                if let Ok(val) = std::env::var(key) {
                    cmd.env(key, val);
                }
            }
            // CommandExt::exec replaces this process image; on error, exit.
            // exec only returns on failure.
            let _ = cmd.exec();
            // SAFETY: exec failed; exit immediately so we don't return through
            // fork() with the parent's state half-applied.
            unsafe { libc::_exit(127) };
        }
    }
}

/// Registry of live PTY sessions, keyed by shell-owned session id.
pub struct PtyRegistry {
    sessions: Mutex<HashMap<String, PtySession>>,
}

impl Default for PtyRegistry {
    fn default() -> Self {
        Self {
            sessions: Mutex::new(HashMap::new()),
        }
    }
}

impl PtyRegistry {
    pub fn open(
        &self,
        session_id: &str,
        workspace: &str,
        shell: Option<&str>,
        cols: u16,
        rows: u16,
        emit: impl Fn(&str, Option<&[u8]>) + Send + Sync + 'static,
    ) -> io::Result<()> {
        let session = spawn(session_id.to_owned(), workspace, shell, cols, rows, emit)?;
        let mut guard = self.sessions.lock().expect("pty lock poisoned");
        if guard.contains_key(session_id) {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "pty session id already in use",
            ));
        }
        guard.insert(session_id.to_owned(), session);
        Ok(())
    }

    pub fn write(&self, session_id: &str, data: &[u8]) -> io::Result<()> {
        let guard = self.sessions.lock().expect("pty lock poisoned");
        match guard.get(session_id) {
            Some(s) => s.write_input(data),
            None => Err(io::Error::new(
                io::ErrorKind::NotFound,
                "pty session not found",
            )),
        }
    }

    pub fn resize(&self, session_id: &str, cols: u16, rows: u16) -> io::Result<()> {
        let guard = self.sessions.lock().expect("pty lock poisoned");
        match guard.get(session_id) {
            Some(s) => s.resize(cols, rows),
            None => Err(io::Error::new(
                io::ErrorKind::NotFound,
                "pty session not found",
            )),
        }
    }

    pub fn kill(&self, session_id: &str) -> io::Result<bool> {
        let mut guard = self.sessions.lock().expect("pty lock poisoned");
        match guard.remove(session_id) {
            Some(_) => Ok(true),
            None => Ok(false),
        }
    }
}
