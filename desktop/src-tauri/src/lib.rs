pub mod control_client;
pub mod host;
pub mod oauth;
pub mod secrets;
pub mod workspace;

use std::process::Child;
use std::sync::Mutex;

use serde::Serialize;
use tauri::{Emitter, Manager, RunEvent, State, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_deep_link::DeepLinkExt;
use zeroize::{Zeroize, Zeroizing};

use control_client::{relay_oauth_callback, sync_provider_secret};
use host::{
    development_runtime_root, free_loopback_port, initialization_script, mint_session_token,
    python_executable, SidecarLaunch,
};
use oauth::parse_oauth_deep_link;
use secrets::{
    encode_secret_bootstrap, provider_secret_status, update_provider_secret, PlatformSecretVault,
};
use workspace::choose_workspace;

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

#[derive(Clone, Serialize)]
struct OAuthRelayStatus {
    flow: String,
    ok: bool,
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

#[tauri::command]
fn pick_workspace() -> Result<String, String> {
    choose_workspace()
        .map(|path| path.to_string_lossy().into_owned())
        .map_err(|error| error.to_string())
}

fn relay_deep_links(app_handle: tauri::AppHandle, urls: Vec<url::Url>) {
    for url in urls {
        let Ok(callback) = parse_oauth_deep_link(&url) else {
            continue;
        };
        let state = app_handle.state::<DesktopState>();
        let port = state.port;
        let token = Zeroizing::new(state.token.clone());
        let secret_sync_token = Zeroizing::new(state.secret_sync_token.clone());
        let flow = callback.flow().to_owned();
        let relay_app = app_handle.clone();
        tauri::async_runtime::spawn_blocking(move || {
            let ok = relay_oauth_callback(port, &token, &secret_sync_token, &callback).is_ok();
            let _ = relay_app.emit("codinal://oauth-status", OAuthRelayStatus { flow, ok });
        });
    }
}

pub fn run() {
    let application = tauri::Builder::default()
        .plugin(tauri_plugin_deep_link::init())
        .invoke_handler(tauri::generate_handler![
            list_provider_secret_status,
            set_provider_secret,
            delete_provider_secret,
            pick_workspace
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

            let deep_link_handle = app.handle().clone();
            app.deep_link().on_open_url(move |event| {
                relay_deep_links(deep_link_handle.clone(), event.urls());
            });
            if let Some(urls) = app.deep_link().get_current()? {
                relay_deep_links(app.handle().clone(), urls);
            }

            let window =
                WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                    .title("Codinal")
                    .inner_size(1180.0, 760.0)
                    .min_inner_size(760.0, 520.0)
                    .initialization_script(initialization_script(port, &token));
            #[cfg(target_os = "macos")]
            let window = window
                .title_bar_style(tauri::TitleBarStyle::Overlay)
                .hidden_title(true);
            window.build()?;
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
