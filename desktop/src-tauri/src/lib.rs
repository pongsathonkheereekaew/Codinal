pub mod host;

use std::process::Child;
use std::sync::Mutex;

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

use host::{
    development_runtime_root, free_loopback_port, initialization_script, mint_session_token,
    python_executable, SidecarLaunch,
};

struct SidecarProcess(Mutex<Option<Child>>);

impl SidecarProcess {
    fn stop(&self) {
        if let Ok(mut guard) = self.0.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

impl Drop for SidecarProcess {
    fn drop(&mut self) {
        if let Ok(child) = self.0.get_mut() {
            if let Some(mut child) = child.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

pub fn run() {
    let application = tauri::Builder::default()
        .setup(|app| {
            let token = mint_session_token()?;
            let port = free_loopback_port()?;
            let runtime_root = development_runtime_root();
            let launch = SidecarLaunch::new(
                python_executable(&runtime_root),
                runtime_root,
                app.path().app_data_dir()?,
                port,
                token.clone(),
            )?;
            let child = launch.spawn()?;
            app.manage(SidecarProcess(Mutex::new(Some(child))));

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
            app_handle.state::<SidecarProcess>().stop();
        }
    });
}
