//! Temporary Tauri compatibility re-export of the shared native LSP client.

#![cfg(target_os = "macos")]

pub use codinal_native_host::lsp::*;
