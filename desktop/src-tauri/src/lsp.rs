//! Language Server Protocol client — manages language-server subprocesses.
//!
//! Each language server (rust-analyzer, pyright, typescript-language-server,
//! etc.) runs as a child process communicating via stdio JSON-RPC (the LSP
//! standard). This module owns the subprocess lifecycle + the JSON-RPC framing
//! (Content-Length headers), and exposes a simple request/response + notification
//! API to the frontend via Tauri commands + events.
//!
//! The server binary must be on PATH — we don't bundle language servers.

#![cfg(target_os = "macos")]

use std::collections::HashMap;
use std::io::{self, BufRead, BufReader, Read, Write};
use std::process::{Child, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;

/// A running language server session.
struct LspServer {
    #[allow(dead_code)]
    language: String,
    child: Child,
    stdin: Arc<Mutex<std::process::ChildStdin>>,
    /// Pending requests waiting for responses: id → sender.
    pending: Arc<Mutex<HashMap<u64, PendingResponse>>>,
    next_id: AtomicU64,
}

struct PendingResponse {
    tx: std::sync::mpsc::Sender<serde_json::Value>,
}

impl Drop for LspServer {
    fn drop(&mut self) {
        // Best-effort kill on drop.
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// Registry of active language servers, keyed by language name.
pub struct LspRegistry {
    servers: Mutex<HashMap<String, Arc<LspServer>>>,
}

impl Default for LspRegistry {
    fn default() -> Self {
        Self {
            servers: Mutex::new(HashMap::new()),
        }
    }
}

/// Known language → server command mapping. The server binary must be on PATH.
/// Users can install them via their package manager (cargo, npm, pip).
fn server_command(language: &str) -> Option<Vec<&'static str>> {
    match language {
        "rust" => Some(vec!["rust-analyzer"]),
        "python" => Some(vec!["pyright-langserver", "--stdio"]),
        "typescript" | "javascript" => Some(vec!["typescript-language-server", "--stdio"]),
        "json" => Some(vec!["vscode-json-language-server", "--stdio"]),
        "css" => Some(vec!["vscode-css-language-server", "--stdio"]),
        "html" => Some(vec!["vscode-html-language-server", "--stdio"]),
        _ => None,
    }
}

/// Emit callback for notifications (diagnostics etc.) → Tauri events.
pub type NotificationEmitter = Arc<dyn Fn(&str, &serde_json::Value) + Send + Sync>;

impl LspRegistry {
    /// Start a language server for the given language + workspace root.
    /// Returns Ok(()) if already running or successfully started.
    /// Returns Err if the server binary is not found or fails to start.
    pub fn start(
        &self,
        language: &str,
        workspace_root: &str,
        emit: NotificationEmitter,
    ) -> io::Result<()> {
        let mut guard = self.servers.lock().expect("lsp lock poisoned");
        if guard.contains_key(language) {
            return Ok(()); // already running
        }
        let cmd_parts = server_command(language).ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                format!("no language server configured for '{language}'"),
            )
        })?;
        let program = cmd_parts[0];
        let args = &cmd_parts[1..];
        let mut child = Command::new(program)
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .current_dir(workspace_root)
            .spawn()
            .map_err(|e| {
                io::Error::new(
                    io::ErrorKind::NotFound,
                    format!(
                        "language server '{program}' not found on PATH: {e}. Install it (e.g. `cargo install rust-analyzer` or `npm install -g typescript-language-server`)."
                    ),
                )
            })?;
        let stdin = child.stdin.take().expect("stdin");
        let stdout = child.stdout.take().expect("stdout");
        let server = Arc::new(LspServer {
            language: language.to_owned(),
            child,
            stdin: Arc::new(Mutex::new(stdin)),
            pending: Arc::new(Mutex::new(HashMap::new())),
            next_id: AtomicU64::new(1),
        });
        // Spawn reader thread for stdout (JSON-RPC responses + notifications).
        let server_for_reader = Arc::clone(&server);
        let lang = language.to_owned();
        thread::Builder::new()
            .name(format!("lsp-reader-{lang}"))
            .spawn(move || {
                read_lsp_messages(stdout, &server_for_reader, &lang, &emit);
            })?;
        guard.insert(language.to_owned(), server);
        Ok(())
    }

    /// Send a JSON-RPC request and wait for the response (blocking, with timeout).
    pub fn request(
        &self,
        language: &str,
        method: &str,
        params: serde_json::Value,
        timeout_secs: u64,
    ) -> io::Result<serde_json::Value> {
        let guard = self.servers.lock().expect("lsp lock poisoned");
        let server = guard.get(language).cloned().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                format!("language server '{language}' is not running"),
            )
        })?;
        drop(guard);
        let id = server.next_id.fetch_add(1, Ordering::SeqCst);
        let (tx, rx) = std::sync::mpsc::channel();
        server
            .pending
            .lock()
            .expect("pending lock")
            .insert(id, PendingResponse { tx });
        let msg = serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params,
        });
        send_message(&server.stdin, &msg)?;
        match rx.recv_timeout(std::time::Duration::from_secs(timeout_secs)) {
            Ok(response) => Ok(response),
            Err(_) => {
                server.pending.lock().expect("pending lock").remove(&id);
                Err(io::Error::other("LSP request timed out"))
            }
        }
    }

    /// Send a notification (no response expected).
    pub fn notify(
        &self,
        language: &str,
        method: &str,
        params: serde_json::Value,
    ) -> io::Result<()> {
        let guard = self.servers.lock().expect("lsp lock poisoned");
        let server = guard.get(language).cloned().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                format!("language server '{language}' is not running"),
            )
        })?;
        drop(guard);
        let msg = serde_json::json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        });
        send_message(&server.stdin, &msg)
    }

    /// Stop a language server.
    pub fn stop(&self, language: &str) -> io::Result<bool> {
        let mut guard = self.servers.lock().expect("lsp lock poisoned");
        Ok(guard.remove(language).is_some())
    }

    /// Check if a server is running for the given language.
    pub fn is_running(&self, language: &str) -> bool {
        self.servers
            .lock()
            .expect("lsp lock poisoned")
            .contains_key(language)
    }
}

/// Write a JSON-RPC message with Content-Length header (LSP framing).
fn send_message(
    stdin: &Arc<Mutex<std::process::ChildStdin>>,
    msg: &serde_json::Value,
) -> io::Result<()> {
    let body = serde_json::to_vec(msg)
        .map_err(|e| io::Error::other(format!("JSON encode failed: {e}")))?;
    let header = format!("Content-Length: {}\r\n\r\n", body.len());
    let mut writer = stdin.lock().expect("stdin lock");
    writer.write_all(header.as_bytes())?;
    writer.write_all(&body)?;
    writer.flush()?;
    Ok(())
}

/// Read LSP messages from stdout, dispatch responses to pending requesters,
/// and emit notifications (diagnostics etc.) via the callback.
fn read_lsp_messages(
    stdout: ChildStdout,
    server: &Arc<LspServer>,
    language: &str,
    emit: &NotificationEmitter,
) {
    let mut reader = BufReader::new(stdout);
    loop {
        // Read headers until blank line.
        let mut content_length: Option<usize> = None;
        loop {
            let mut line = String::new();
            match reader.read_line(&mut line) {
                Ok(0) => return, // EOF
                Ok(_) => {}
                Err(_) => return,
            }
            let trimmed = line.trim();
            if trimmed.is_empty() {
                break; // end of headers
            }
            if let Some(len_str) = trimmed.strip_prefix("Content-Length:") {
                content_length = len_str.trim().parse().ok();
            }
        }
        let length = match content_length {
            Some(l) => l,
            None => continue,
        };
        // Read the JSON body.
        let mut buf = vec![0u8; length];
        if reader.read_exact(&mut buf).is_err() {
            return;
        }
        let msg: serde_json::Value = match serde_json::from_slice(&buf) {
            Ok(v) => v,
            Err(_) => continue,
        };
        // Dispatch: response (has "id" + "result"/"error") or notification (no "id").
        if let Some(id) = msg.get("id").and_then(|v| v.as_u64()) {
            // It's a response — find the pending requester.
            let pending = server.pending.lock().expect("pending lock").remove(&id);
            if let Some(p) = pending {
                let result = msg
                    .get("result")
                    .cloned()
                    .unwrap_or(serde_json::Value::Null);
                let _ = p.tx.send(result);
            }
        } else if let Some(method) = msg.get("method").and_then(|v| v.as_str()) {
            // It's a notification — emit to frontend.
            let params = msg
                .get("params")
                .cloned()
                .unwrap_or(serde_json::Value::Null);
            emit(
                language,
                &serde_json::json!({ "method": method, "params": params }),
            );
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn server_command_known_languages() {
        assert_eq!(server_command("rust"), Some(vec!["rust-analyzer"]));
        assert_eq!(
            server_command("typescript"),
            Some(vec!["typescript-language-server", "--stdio"])
        );
        assert_eq!(
            server_command("python"),
            Some(vec!["pyright-langserver", "--stdio"])
        );
        assert_eq!(server_command("unknown"), None);
    }

    #[test]
    fn registry_starts_and_stops() {
        // We can't test real server startup in CI (no rust-analyzer installed),
        // but we can verify the registry's start/stop state machine with a
        // fake command that fails gracefully.
        let registry = LspRegistry::default();
        assert!(!registry.is_running("rust"));
        // start() with a missing server should fail gracefully.
        let emit: NotificationEmitter = Arc::new(|_, _| {});
        let result = registry.start("rust", "/tmp", emit);
        // This may succeed or fail depending on whether rust-analyzer is on PATH.
        // The important thing is it doesn't panic.
        let _ = result;
        if registry.is_running("rust") {
            assert!(registry.stop("rust").unwrap_or(false));
            assert!(!registry.is_running("rust"));
        }
    }
}
