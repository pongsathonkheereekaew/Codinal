//! Shared native sidecar lifecycle and secret bootstrap for desktop shells.
//!
//! The implementation remains sourced from the production Tauri host while
//! the GPUI migration is staged.  This keeps the sidecar protocol and macOS
//! Keychain schema identical for both shells.
#[path = "../../src-tauri/src/host.rs"]
pub mod host;

#[path = "../../src-tauri/src/secrets.rs"]
pub mod secrets;

pub use host::*;
