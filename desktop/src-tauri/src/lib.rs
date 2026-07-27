pub mod control_client;
pub mod host;
pub mod oauth;
pub mod project_open;
pub mod secrets;
pub mod workspace;

use std::process::Child;
use std::sync::Mutex;

use serde::Serialize;
use tauri::{Emitter, Manager, RunEvent, State, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_deep_link::DeepLinkExt;
use tauri_plugin_updater::UpdaterExt;
use zeroize::{Zeroize, Zeroizing};

use control_client::{relay_oauth_callback, sync_provider_secret};
use host::{
    free_loopback_port, initialization_script, mint_session_token, runtime_layout,
    validate_runtime_layout, SidecarLaunch,
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

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct UpdateStatus {
    available: bool,
    current_version: String,
    version: Option<String>,
    notes: Option<String>,
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
    base_url: Option<String>,
    state: State<'_, DesktopState>,
) -> Result<SecretMutationResult, String> {
    let api_key = Zeroizing::new(api_key);
    update_provider_secret(
        &state.vault,
        &provider,
        Some(&api_key),
        base_url.as_deref(),
        || {
            sync_provider_secret(
                state.port,
                &state.token,
                &state.secret_sync_token,
                &provider,
                Some(&api_key),
                base_url.as_deref(),
            )
        },
    )
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
    update_provider_secret(&state.vault, &provider, None, None, || {
        sync_provider_secret(
            state.port,
            &state.token,
            &state.secret_sync_token,
            &provider,
            None,
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
fn list_custom_providers(
    state: State<'_, DesktopState>,
) -> Result<Vec<secrets::CustomProviderRecord>, String> {
    secrets::list_custom_providers(&state.vault).map_err(|error| error.to_string())
}

#[tauri::command]
fn set_custom_provider(
    slug: String,
    base_url: String,
    api_key: String,
    failover_eligible: bool,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    let slug_for_sync = slug.clone();
    let base_url_for_sync = base_url.clone();
    let api_key = Zeroizing::new(api_key);
    secrets::set_custom_provider(
        &state.vault,
        &slug,
        &base_url,
        &api_key,
        failover_eligible,
        || {
            control_client::sync_custom_provider(
                state.port,
                &state.token,
                &state.secret_sync_token,
                &slug_for_sync,
                &base_url_for_sync,
                Some(&api_key),
                failover_eligible,
            )
        },
    )
    .map_err(|error| error.to_string())
}

#[tauri::command]
fn delete_custom_provider(slug: String, state: State<'_, DesktopState>) -> Result<bool, String> {
    let slug_for_sync = slug.clone();
    secrets::delete_custom_provider(&state.vault, &slug, || {
        control_client::sync_custom_provider(
            state.port,
            &state.token,
            &state.secret_sync_token,
            &slug_for_sync,
            "",
            None,
            false,
        )
    })
    .map_err(|error| error.to_string())
}

#[tauri::command]
fn pick_workspace() -> Result<String, String> {
    choose_workspace()
        .map(|path| path.to_string_lossy().into_owned())
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn check_for_update(app: tauri::AppHandle) -> Result<UpdateStatus, String> {
    let current_version = app.package_info().version.to_string();
    let update = available_update(&app).await?;
    Ok(match update {
        Some(update) => UpdateStatus {
            available: true,
            current_version,
            version: Some(update.version),
            notes: update.body,
        },
        None => UpdateStatus {
            available: false,
            current_version,
            version: None,
            notes: None,
        },
    })
}

async fn available_update(
    app: &tauri::AppHandle,
) -> Result<Option<tauri_plugin_updater::Update>, String> {
    app.updater()
        .map_err(|error| error.to_string())?
        .check()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn install_update(expected_version: String, app: tauri::AppHandle) -> Result<(), String> {
    // Backup the current .app bundle so rollback is possible if the update
    // is broken. The backup lives next to the app as `<name>.backup`.
    let current_exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let app_bundle = current_exe
        .ancestors()
        .nth(3)
        .ok_or("could not locate .app bundle")?;
    let backup = app_bundle.with_extension("app.backup");
    if app_bundle.exists() {
        let _ = std::fs::remove_dir_all(&backup);
        let _ = std::fs::create_dir_all(&backup);
        copy_dir_recursive(app_bundle, &backup).map_err(|e| e.to_string())?;
    }

    let update = available_update(&app)
        .await?
        .ok_or_else(|| "No update is available".to_owned())?;
    if update.version != expected_version {
        return Err("The available update changed; check again before installing".to_owned());
    }
    update
        .download_and_install(|_, _| {}, || {})
        .await
        .map_err(|error| error.to_string())?;
    app.restart();
}

#[tauri::command]
async fn rollback_update(app: tauri::AppHandle) -> Result<(), String> {
    // Restore the backed-up .app bundle from before the last update.
    let current_exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let app_bundle = current_exe
        .ancestors()
        .nth(3)
        .ok_or("could not locate .app bundle")?;
    let backup = app_bundle.with_extension("app.backup");
    if !backup.exists() {
        return Err("no update backup found — nothing to roll back".to_owned());
    }
    // Swap: move current aside, move backup into place, remove the old current.
    let temp = app_bundle.with_extension("app.failed");
    let _ = std::fs::remove_dir_all(&temp);
    std::fs::rename(app_bundle, &temp)
        .map_err(|e| format!("could not move current app aside: {e}"))?;
    if let Err(e) = std::fs::rename(&backup, app_bundle) {
        // Restore: move the current back if the backup rename failed.
        let _ = std::fs::rename(&temp, app_bundle);
        return Err(format!("could not restore backup: {e}"));
    }
    let _ = std::fs::remove_dir_all(&temp);
    app.restart();
}

fn copy_dir_recursive(src: &std::path::Path, dst: &std::path::Path) -> std::io::Result<()> {
    if !dst.exists() {
        std::fs::create_dir_all(dst)?;
    }
    for entry in std::fs::read_dir(src)? {
        let entry = entry?;
        let from = entry.path();
        let to = dst.join(entry.file_name());
        if from.is_dir() {
            copy_dir_recursive(&from, &to)?;
        } else {
            std::fs::copy(&from, &to)?;
        }
    }
    Ok(())
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
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            list_provider_secret_status,
            set_provider_secret,
            delete_provider_secret,
            list_custom_providers,
            set_custom_provider,
            delete_custom_provider,
            pick_workspace,
            check_for_update,
            install_update,
            rollback_update
        ])
        .setup(|app| {
            let token = mint_session_token()?;
            let secret_sync_token = mint_session_token()?;
            let port = free_loopback_port()?;
            let layout = runtime_layout(&app.path().resource_dir()?, cfg!(debug_assertions));
            validate_runtime_layout(&layout)?;
            let vault = PlatformSecretVault;
            let secret_bootstrap = encode_secret_bootstrap(&vault, &secret_sync_token)?;
            let launch = SidecarLaunch::new(
                layout.python,
                layout.runtime_root,
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

#[cfg(test)]
mod tests {
    use super::copy_dir_recursive;
    use std::fs;

    #[test]
    fn copy_dir_recursive_copies_files_and_subdirs() {
        let tmp = std::env::temp_dir().join("codinal-copy-test");
        let _ = fs::remove_dir_all(&tmp);
        let src = tmp.join("src");
        fs::create_dir_all(src.join("sub")).unwrap();
        fs::write(src.join("a.txt"), "hello").unwrap();
        fs::write(src.join("sub/b.txt"), "world").unwrap();

        let dst = tmp.join("dst");
        copy_dir_recursive(&src, &dst).unwrap();

        assert_eq!(fs::read_to_string(dst.join("a.txt")).unwrap(), "hello");
        assert_eq!(fs::read_to_string(dst.join("sub/b.txt")).unwrap(), "world");
        let _ = fs::remove_dir_all(&tmp);
    }

    #[test]
    fn copy_dir_recursive_overwrites_existing() {
        let tmp = std::env::temp_dir().join("codinal-overwrite-test");
        let _ = fs::remove_dir_all(&tmp);
        let src = tmp.join("src");
        let dst = tmp.join("dst");
        fs::create_dir_all(&src).unwrap();
        fs::write(src.join("new.txt"), "new").unwrap();
        fs::create_dir_all(&dst).unwrap();
        fs::write(dst.join("old.txt"), "old").unwrap();

        copy_dir_recursive(&src, &dst).unwrap();

        assert_eq!(fs::read_to_string(dst.join("new.txt")).unwrap(), "new");
        // old.txt is NOT removed (merge, not replace) — that's fine for backup.
        assert!(dst.join("old.txt").exists());
        let _ = fs::remove_dir_all(&tmp);
    }
}
