//! Shared native sidecar lifecycle for desktop shells.
#[path = "../../src-tauri/src/host.rs"]
mod implementation;

pub use implementation::*;
