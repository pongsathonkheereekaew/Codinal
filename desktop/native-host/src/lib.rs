//! Shared native lifecycle and secret bootstrap for desktop shells.
//!
//! This crate owns the token, launch, and Keychain contracts so every native
//! shell depends on the same implementation without importing Tauri sources.
pub mod control_client;
pub mod host;
#[cfg(target_os = "macos")]
pub mod lsp;
pub mod oauth;
pub mod project_open;
#[cfg(target_os = "macos")]
pub mod pty;
pub mod secrets;
pub mod workspace;

pub use host::*;
