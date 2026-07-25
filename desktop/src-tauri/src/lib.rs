pub mod control_client;
pub mod host;
pub mod secrets;

use std::process::Child;
use std::sync::Mutex;

use serde::Serialize;
use tauri::{Manager, RunEvent, State, WebviewUrl, WebviewWindowBuilder};
use zeroize::{Zeroize, Zeroizing};

use control_client::sync_provider_secret;
use host::{
    development_runtime_root, free_loopback_port, initialization_script, mint_session_token,
    python_executable, SidecarLaunch,
};
use secrets::{
    encode_secret_bootstrap, provider_secret_status, update_provider_secret, PlatformSecretVault,
};

struct DesktopState {
    process: Mutex<Option<Child>>,
    vault: PlatformSecretVault,
    port: u16,
    token: String,
    secret_sync_token: String,
}

impl DesktopState {
    fn stop(&self) {
        if let Ok(mut guard) = self.process.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

impl Drop for DesktopState {
    fn drop(&mut self) {
        if let Ok(child) = self.process.get_mut() {
            if let Some(mut child) = child.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
        self.token.zeroize();
        self.secret_sync_token.zeroize();
    }
}

#[derive(Serialize)]
struct SecretMutationResult {
    provider: String,
    configured: bool,
}

#[tauri::command]
fn list_provider_secret_status(
    state: State<'_, DesktopState>,
) -> Result<Vec<secrets::ProviderSecretStatus>, String> {
    provider_secret_status(&state.vault).map_err(|error| error.to_string())
}

#[tauri::command]
fn set_provider_secret(
    provider: String,
    api_key: String,
    state: State<'_, DesktopState>,
) -> Result<SecretMutationResult, String> {
    let api_key = Zeroizing::new(api_key);
    update_provider_secret(&state.vault, &provider, Some(&api_key), || {
        sync_provider_secret(
            state.port,
            &state.token,
            &state.secret_sync_token,
            &provider,
            Some(&api_key),
        )
    })
    .map(|configured| SecretMutationResult {
        provider,
        configured,
    })
    .map_err(|error| error.to_string())
}

#[tauri::command]
fn delete_provider_secret(
    provider: String,
    state: State<'_, DesktopState>,
) -> Result<SecretMutationResult, String> {
    update_provider_secret(&state.vault, &provider, None, || {
        sync_provider_secret(
            state.port,
            &state.token,
            &state.secret_sync_token,
            &provider,
            None,
        )
    })
    .map(|configured| SecretMutationResult {
        provider,
        configured,
    })
    .map_err(|error| error.to_string())
}

pub fn run() {
    let application = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            list_provider_secret_status,
            set_provider_secret,
            delete_provider_secret
        ])
        .setup(|app| {
            let token = mint_session_token()?;
            let secret_sync_token = mint_session_token()?;
            let port = free_loopback_port()?;
            let runtime_root = development_runtime_root();
            let vault = PlatformSecretVault;
            let secret_bootstrap = encode_secret_bootstrap(&vault, &secret_sync_token)?;
            let launch = SidecarLaunch::new(
                python_executable(&runtime_root),
                runtime_root,
                app.path().app_data_dir()?,
                port,
                token.clone(),
            )?;
            let child = launch.spawn_with_bootstrap(secret_bootstrap)?;
            app.manage(DesktopState {
                process: Mutex::new(Some(child)),
                vault,
                port,
                token: token.clone(),
                secret_sync_token,
            });

            WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("Codinal")
                .inner_size(1180.0, 760.0)
                .min_inner_size(760.0, 520.0)
                .initialization_script(initialization_script(port, &token))
                .build()?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build Codinal desktop application");

    application.run(|app_handle, event| {
        if matches!(event, RunEvent::Exit) {
            app_handle.state::<DesktopState>().stop();
        }
    });
}
