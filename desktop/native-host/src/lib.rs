//! Shared native lifecycle and secret bootstrap for native desktop hosts.
//!
//! This crate owns the token, launch, and Keychain contracts so every native
//! host can depend on the same implementation without duplicating platform code.
pub mod control_client;
pub mod host;
#[cfg(target_os = "macos")]
pub mod lsp;
pub mod oauth;
pub mod project_open;
#[cfg(target_os = "macos")]
pub mod pty;
pub mod secrets;
pub mod updater;
pub mod workspace;

pub use host::*;
