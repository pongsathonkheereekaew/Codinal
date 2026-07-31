//! Shared native lifecycle and secret bootstrap for desktop shells.
//!
//! This crate owns the token, launch, and Keychain contracts so every native
//! shell depends on the same implementation without importing Tauri sources.
pub mod host;
pub mod secrets;

pub use host::*;
