pub mod control_client;
pub mod gpui_control_plane;
pub mod host;
#[cfg(target_os = "macos")]
pub mod lsp;
pub mod oauth;
pub mod project_open;
#[cfg(target_os = "macos")]
pub mod pty;
pub mod secrets;
pub mod workspace;

use std::process::Child;
use std::sync::{Arc, Mutex};

use serde::Serialize;
use tauri::{Emitter, Manager, RunEvent, State, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_deep_link::DeepLinkExt;
use tauri_plugin_updater::UpdaterExt;
use url::Url;
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
    #[cfg(target_os = "macos")]
    ptys: pty::PtyRegistry,
    #[cfg(target_os = "macos")]
    lsp: lsp::LspRegistry,
    port: u16,
    token: String,
    secret_sync_token: String,
}

fn allows_preview_navigation(url: &Url) -> bool {
    if url.scheme() == "tauri" {
        return true;
    }
    matches!(url.scheme(), "http" | "https")
        && matches!(
            url.host_str(),
            Some("127.0.0.1") | Some("[::1]") | Some("::1")
        )
        && url.port().is_some()
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

#[cfg(not(target_os = "macos"))]
fn lsp_unsupported<T>() -> Result<T, String> {
    Err("lsp is unavailable on this platform".to_owned())
}

/// Start a language server. Emits `lsp-notification` events for diagnostics etc.
#[cfg(target_os = "macos")]
#[tauri::command]
fn lsp_start(
    language: String,
    workspace_root: String,
    app: tauri::AppHandle,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    let emit_app = app.clone();
    state
        .lsp
        .start(
            &language,
            &workspace_root,
            Arc::new(move |key, msg| {
                let _ = emit_app.emit(
                    "lsp-notification",
                    serde_json::json!({
                        "language": key.language,
                        "workspaceRoot": key.workspace_root,
                        "message": msg,
                    }),
                );
            }),
        )
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn lsp_start(
    _language: String,
    _workspace_root: String,
    _app: tauri::AppHandle,
    _state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    lsp_unsupported()
}

/// Send a JSON-RPC request (blocking, with timeout). Returns the result.
#[cfg(target_os = "macos")]
#[tauri::command]
fn lsp_request(
    language: String,
    workspace_root: String,
    method: String,
    params: serde_json::Value,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    state
        .lsp
        .request(&language, &workspace_root, &method, params, 10)
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn lsp_request(
    _language: String,
    _workspace_root: String,
    _method: String,
    _params: serde_json::Value,
    _state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    lsp_unsupported()
}

/// Send a notification (fire-and-forget, no response).
#[cfg(target_os = "macos")]
#[tauri::command]
fn lsp_notify(
    language: String,
    workspace_root: String,
    method: String,
    params: serde_json::Value,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    state
        .lsp
        .notify(&language, &workspace_root, &method, params)
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn lsp_notify(
    _language: String,
    _workspace_root: String,
    _method: String,
    _params: serde_json::Value,
    _state: State<'_, DesktopState>,
) -> Result<(), String> {
    lsp_unsupported()
}

#[cfg(target_os = "macos")]
#[tauri::command]
fn lsp_document_open(
    language: String,
    workspace_root: String,
    path: String,
    text: String,
    version: u64,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    state
        .lsp
        .document_open(&language, &workspace_root, &path, text, version)
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn lsp_document_open(
    _language: String,
    _workspace_root: String,
    _path: String,
    _text: String,
    _version: u64,
    _state: State<'_, DesktopState>,
) -> Result<(), String> {
    lsp_unsupported()
}

#[cfg(target_os = "macos")]
#[tauri::command]
fn lsp_document_change(
    language: String,
    workspace_root: String,
    path: String,
    text: String,
    version: u64,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    state
        .lsp
        .document_change(&language, &workspace_root, &path, text, version)
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn lsp_document_change(
    _language: String,
    _workspace_root: String,
    _path: String,
    _text: String,
    _version: u64,
    _state: State<'_, DesktopState>,
) -> Result<(), String> {
    lsp_unsupported()
}

#[cfg(target_os = "macos")]
#[tauri::command]
fn lsp_document_save(
    language: String,
    workspace_root: String,
    path: String,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    state
        .lsp
        .document_save(&language, &workspace_root, &path)
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn lsp_document_save(
    _language: String,
    _workspace_root: String,
    _path: String,
    _state: State<'_, DesktopState>,
) -> Result<(), String> {
    lsp_unsupported()
}

#[cfg(target_os = "macos")]
#[tauri::command]
fn lsp_document_close(
    language: String,
    workspace_root: String,
    path: String,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    state
        .lsp
        .document_close(&language, &workspace_root, &path)
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn lsp_document_close(
    _language: String,
    _workspace_root: String,
    _path: String,
    _state: State<'_, DesktopState>,
) -> Result<(), String> {
    lsp_unsupported()
}

#[cfg(target_os = "macos")]
#[tauri::command]
fn lsp_document_symbols(
    language: String,
    workspace_root: String,
    path: String,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    state
        .lsp
        .document_symbols(&language, &workspace_root, &path)
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn lsp_document_symbols(
    _language: String,
    _workspace_root: String,
    _path: String,
    _state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    lsp_unsupported()
}

#[cfg(target_os = "macos")]
#[tauri::command]
fn lsp_workspace_symbols(
    language: String,
    workspace_root: String,
    query: String,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    state
        .lsp
        .workspace_symbols(&language, &workspace_root, &query)
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn lsp_workspace_symbols(
    _language: String,
    _workspace_root: String,
    _query: String,
    _state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    lsp_unsupported()
}

/// Stop a language server.
#[cfg(target_os = "macos")]
#[tauri::command]
fn lsp_stop(
    language: String,
    workspace_root: String,
    state: State<'_, DesktopState>,
) -> Result<bool, String> {
    state
        .lsp
        .stop(&language, &workspace_root)
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn lsp_stop(
    _language: String,
    _workspace_root: String,
    _state: State<'_, DesktopState>,
) -> Result<bool, String> {
    lsp_unsupported()
}

#[tauri::command]
fn pick_workspace() -> Result<String, String> {
    choose_workspace()
        .map(|path| path.to_string_lossy().into_owned())
        .map_err(|error| error.to_string())
}

/// Payload for the `pty-data` event: raw bytes from the PTY master, base64
/// (not UTF-8) because terminal output may include arbitrary byte sequences
/// (binary cat, invalid UTF-8, etc.).
#[derive(Clone, Serialize)]
struct PtyData {
    session_id: String,
    /// base64-encoded bytes from the child.
    data: String,
}

/// Payload for the `pty-exit` event: emitted when the reader thread hits EOF.
#[derive(Clone, Serialize)]
struct PtyExit {
    session_id: String,
}

#[cfg(not(target_os = "macos"))]
fn pty_unsupported<T>() -> Result<T, String> {
    Err("pty terminal is unavailable on this platform".to_owned())
}

/// Open a new interactive PTY session in the workspace. Returns the session id
/// (caller-supplied) on success. The frontend listens for `pty-data` /
/// `pty-exit` events emitted from the reader thread.
#[cfg(target_os = "macos")]
#[tauri::command]
fn pty_open(
    session_id: String,
    workspace: String,
    cols: u16,
    rows: u16,
    app: tauri::AppHandle,
    state: State<'_, DesktopState>,
) -> Result<String, String> {
    let emit_app = app.clone();
    let target = session_id.clone();
    state
        .ptys
        .open(
            &session_id,
            &workspace,
            None,
            cols,
            rows,
            move |sid, chunk| match chunk {
                Some(bytes) => {
                    use base64::Engine;
                    let encoded = base64::engine::general_purpose::STANDARD.encode(bytes);
                    let _ = emit_app.emit(
                        "pty-data",
                        PtyData {
                            session_id: sid.to_owned(),
                            data: encoded,
                        },
                    );
                }
                None => {
                    let _ = emit_app.emit(
                        "pty-exit",
                        PtyExit {
                            session_id: sid.to_owned(),
                        },
                    );
                }
            },
        )
        .map_err(|error| error.to_string())?;
    Ok(target)
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn pty_open(
    _session_id: String,
    _workspace: String,
    _cols: u16,
    _rows: u16,
    _app: tauri::AppHandle,
    _state: State<'_, DesktopState>,
) -> Result<String, String> {
    pty_unsupported()
}

#[cfg(target_os = "macos")]
#[tauri::command]
fn pty_input(
    session_id: String,
    data: String,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    state
        .ptys
        .write(&session_id, data.as_bytes())
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn pty_input(
    _session_id: String,
    _data: String,
    _state: State<'_, DesktopState>,
) -> Result<(), String> {
    pty_unsupported()
}

#[cfg(target_os = "macos")]
#[tauri::command]
fn pty_resize(
    session_id: String,
    cols: u16,
    rows: u16,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    state
        .ptys
        .resize(&session_id, cols, rows)
        .map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn pty_resize(
    _session_id: String,
    _cols: u16,
    _rows: u16,
    _state: State<'_, DesktopState>,
) -> Result<(), String> {
    pty_unsupported()
}

#[cfg(target_os = "macos")]
#[tauri::command]
fn pty_kill(session_id: String, state: State<'_, DesktopState>) -> Result<bool, String> {
    state.ptys.kill(&session_id).map_err(|e| e.to_string())
}

#[cfg(not(target_os = "macos"))]
#[tauri::command]
fn pty_kill(_session_id: String, _state: State<'_, DesktopState>) -> Result<bool, String> {
    pty_unsupported()
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
            rollback_update,
            pty_open,
            pty_input,
            pty_resize,
            pty_kill,
            lsp_start,
            lsp_request,
            lsp_notify,
            lsp_stop,
            lsp_document_open,
            lsp_document_change,
            lsp_document_save,
            lsp_document_close,
            lsp_document_symbols,
            lsp_workspace_symbols
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
                #[cfg(target_os = "macos")]
                ptys: pty::PtyRegistry::default(),
                #[cfg(target_os = "macos")]
                lsp: lsp::LspRegistry::default(),
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
                    .initialization_script(initialization_script(port, &token))
                    .on_navigation(allows_preview_navigation);
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
    use super::{allows_preview_navigation, copy_dir_recursive};
    use std::fs;
    use url::Url;

    #[test]
    fn preview_navigation_allows_only_loopback_or_app_urls() {
        assert!(allows_preview_navigation(
            &Url::parse("tauri://localhost/").unwrap()
        ));
        assert!(allows_preview_navigation(
            &Url::parse("http://127.0.0.1:3000/").unwrap()
        ));
        assert!(!allows_preview_navigation(
            &Url::parse("https://example.com/").unwrap()
        ));
    }

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
