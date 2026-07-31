use base64::Engine as _;
use flate2::read::GzDecoder;
use minisign_verify::{PublicKey, Signature};
use reqwest::blocking::{Client, Response};
use reqwest::redirect::{Action, Attempt, Policy};
use semver::Version;
use serde::Deserialize;
use std::collections::HashMap;
use std::fmt;
use std::fs;
use std::io::{self, Read};
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;
use tar::EntryType;
use tempfile::TempDir;
use url::Url;

pub const DEFAULT_UPDATE_ENDPOINT: &str =
    "https://github.com/pongsathonkheereekaew/Codinal/releases/latest/download/latest.json";
pub const DEFAULT_UPDATE_PUBLIC_KEY: &str = "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDI2MjA5MzQwRDE3NjQ4QjIKUldTeVNIYlJRSk1nSmtkdUZIcHdSZForOE52QkZJMWgrVXloOWhLRzhpajZjSzZieHhpQlp6NWcK";

const TARGET: &str = "darwin-aarch64";
const MAX_MANIFEST_BYTES: u64 = 1024 * 1024;
const MAX_ARCHIVE_BYTES: u64 = 512 * 1024 * 1024;
const MAX_EXTRACTED_BYTES: u64 = 2 * 1024 * 1024 * 1024;
const MAX_ARCHIVE_ENTRIES: usize = 100_000;
const REQUEST_TIMEOUT: Duration = Duration::from_secs(30);
const RESTART_HELPER_FLAG: &str = "--codinal-restart-after-pid";
const RESTART_WAIT_TIMEOUT: Duration = Duration::from_secs(60);

#[derive(Debug)]
pub enum UpdateError {
    InvalidConfig(String),
    Network(String),
    InvalidManifest(String),
    Signature(String),
    InvalidArchive(String),
    Io(io::Error),
}

impl fmt::Display for UpdateError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidConfig(message)
            | Self::Network(message)
            | Self::InvalidManifest(message)
            | Self::Signature(message)
            | Self::InvalidArchive(message) => f.write_str(message),
            Self::Io(error) => error.fmt(f),
        }
    }
}

impl std::error::Error for UpdateError {}

impl From<io::Error> for UpdateError {
    fn from(value: io::Error) -> Self {
        Self::Io(value)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AvailableUpdate {
    pub version: Version,
    pub notes: Option<String>,
    pub download_url: Url,
    pub signature: String,
}

#[derive(Debug, Deserialize)]
struct ReleaseManifest {
    version: String,
    notes: Option<String>,
    platforms: HashMap<String, ReleasePlatform>,
}

#[derive(Debug, Deserialize)]
struct ReleasePlatform {
    url: Url,
    signature: String,
}

pub struct NativeUpdater {
    endpoint: Url,
    public_key: String,
    current_version: Version,
    app_bundle: PathBuf,
    client: Client,
}

impl NativeUpdater {
    pub fn for_release_bundle(
        current_version: &str,
        app_bundle: PathBuf,
    ) -> Result<Self, UpdateError> {
        let endpoint = Url::parse(DEFAULT_UPDATE_ENDPOINT)
            .map_err(|error| UpdateError::InvalidConfig(error.to_string()))?;
        let current_version = Version::parse(current_version.trim_start_matches('v'))
            .map_err(|error| UpdateError::InvalidConfig(error.to_string()))?;
        Self::new(
            endpoint,
            DEFAULT_UPDATE_PUBLIC_KEY,
            current_version,
            app_bundle,
        )
    }

    pub fn new(
        endpoint: Url,
        public_key: impl Into<String>,
        current_version: Version,
        app_bundle: PathBuf,
    ) -> Result<Self, UpdateError> {
        require_https(&endpoint)?;
        validate_app_bundle_path(&app_bundle)?;
        let client = Client::builder()
            .timeout(REQUEST_TIMEOUT)
            .redirect(Policy::custom(https_redirect))
            .user_agent("codinal-native-updater")
            .build()
            .map_err(|error| UpdateError::InvalidConfig(error.to_string()))?;
        Ok(Self {
            endpoint,
            public_key: public_key.into(),
            current_version,
            app_bundle,
            client,
        })
    }

    pub fn check(&self) -> Result<Option<AvailableUpdate>, UpdateError> {
        let response = self
            .client
            .get(self.endpoint.clone())
            .send()
            .map_err(network_error)?;
        let bytes = read_response(response, MAX_MANIFEST_BYTES)?;
        let manifest: ReleaseManifest = serde_json::from_slice(&bytes)
            .map_err(|error| UpdateError::InvalidManifest(error.to_string()))?;
        let version = Version::parse(manifest.version.trim_start_matches('v'))
            .map_err(|error| UpdateError::InvalidManifest(error.to_string()))?;
        if version <= self.current_version {
            return Ok(None);
        }
        let platform = manifest.platforms.get(TARGET).ok_or_else(|| {
            UpdateError::InvalidManifest(format!("manifest does not contain {TARGET}"))
        })?;
        require_https(&platform.url)?;
        if platform.signature.trim().is_empty() {
            return Err(UpdateError::InvalidManifest(
                "manifest signature is empty".to_owned(),
            ));
        }
        Ok(Some(AvailableUpdate {
            version,
            notes: manifest.notes,
            download_url: platform.url.clone(),
            signature: platform.signature.clone(),
        }))
    }

    pub fn download(&self, update: &AvailableUpdate) -> Result<Vec<u8>, UpdateError> {
        require_https(&update.download_url)?;
        let response = self
            .client
            .get(update.download_url.clone())
            .send()
            .map_err(network_error)?;
        let bytes = read_response(response, MAX_ARCHIVE_BYTES)?;
        verify_signature(&bytes, &update.signature, &self.public_key)?;
        Ok(bytes)
    }

    pub fn install(&self, update: &AvailableUpdate, archive: &[u8]) -> Result<(), UpdateError> {
        if update.version <= self.current_version {
            return Err(UpdateError::InvalidManifest(
                "refusing to install a non-newer version".to_owned(),
            ));
        }
        verify_signature(archive, &update.signature, &self.public_key)?;
        install_archive(&self.app_bundle, &update.version, archive)
    }

    pub fn rollback(&self) -> Result<(), UpdateError> {
        rollback_app(&self.app_bundle)
    }

    pub fn spawn_restart_helper(&self) -> Result<(), UpdateError> {
        let executable = std::env::current_exe()?;
        Command::new(executable)
            .arg(RESTART_HELPER_FLAG)
            .arg(std::process::id().to_string())
            .arg(&self.app_bundle)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()?;
        Ok(())
    }
}

#[cfg(target_os = "macos")]
pub fn run_restart_helper_if_requested() -> Result<bool, UpdateError> {
    let mut arguments = std::env::args_os();
    let _executable = arguments.next();
    let Some(flag) = arguments.next() else {
        return Ok(false);
    };
    if flag != RESTART_HELPER_FLAG {
        return Ok(false);
    }
    let pid = arguments
        .next()
        .ok_or_else(|| UpdateError::InvalidConfig("restart helper PID is missing".to_owned()))?
        .into_string()
        .map_err(|_| UpdateError::InvalidConfig("restart helper PID is invalid".to_owned()))?
        .parse::<i32>()
        .map_err(|_| UpdateError::InvalidConfig("restart helper PID is invalid".to_owned()))?;
    let app_bundle = arguments.next().map(PathBuf::from).ok_or_else(|| {
        UpdateError::InvalidConfig("restart helper app bundle is missing".to_owned())
    })?;
    if arguments.next().is_some() || pid <= 1 || pid == std::process::id() as i32 {
        return Err(UpdateError::InvalidConfig(
            "restart helper arguments are invalid".to_owned(),
        ));
    }
    validate_app_bundle_path(&app_bundle)?;
    let helper_bundle = app_bundle_for_executable(&std::env::current_exe()?)?;
    if fs::canonicalize(&app_bundle)? != fs::canonicalize(helper_bundle)? {
        return Err(UpdateError::InvalidConfig(
            "restart helper may reopen only its containing app bundle".to_owned(),
        ));
    }
    let deadline = std::time::Instant::now() + RESTART_WAIT_TIMEOUT;
    while process_exists(pid) {
        if std::time::Instant::now() >= deadline {
            return Err(UpdateError::Io(io::Error::new(
                io::ErrorKind::TimedOut,
                "timed out waiting for Codinal to exit",
            )));
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    if !app_bundle.is_dir() {
        return Err(UpdateError::InvalidConfig(
            "restart helper app bundle does not exist".to_owned(),
        ));
    }
    let status = Command::new("/usr/bin/open")
        .arg("-n")
        .arg(&app_bundle)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()?;
    if !status.success() {
        return Err(UpdateError::Io(io::Error::other(
            "could not reopen Codinal after update",
        )));
    }
    Ok(true)
}

#[cfg(target_os = "macos")]
fn process_exists(pid: i32) -> bool {
    let result = unsafe { libc::kill(pid, 0) };
    result == 0 || io::Error::last_os_error().raw_os_error() != Some(libc::ESRCH)
}

fn app_bundle_for_executable(executable: &Path) -> Result<PathBuf, UpdateError> {
    let contents = executable
        .parent()
        .and_then(Path::parent)
        .ok_or_else(|| UpdateError::InvalidConfig("invalid app bundle layout".to_owned()))?;
    let app_bundle = contents
        .parent()
        .ok_or_else(|| UpdateError::InvalidConfig("invalid app bundle layout".to_owned()))?
        .to_owned();
    validate_app_bundle_path(&app_bundle)?;
    Ok(app_bundle)
}

fn https_redirect(attempt: Attempt<'_>) -> Action {
    if attempt.previous().len() >= 5 {
        return attempt.error("too many redirects");
    }
    if attempt.url().scheme() != "https" {
        return attempt.error("updater redirects must use HTTPS");
    }
    attempt.follow()
}

fn require_https(url: &Url) -> Result<(), UpdateError> {
    if url.scheme() != "https" || url.host_str().is_none() {
        return Err(UpdateError::InvalidConfig(
            "updater URLs must be absolute HTTPS URLs".to_owned(),
        ));
    }
    Ok(())
}

fn network_error(error: reqwest::Error) -> UpdateError {
    UpdateError::Network(error.to_string())
}

fn read_response(mut response: Response, max_bytes: u64) -> Result<Vec<u8>, UpdateError> {
    if !response.status().is_success() {
        return Err(UpdateError::Network(format!(
            "update request failed with status {}",
            response.status()
        )));
    }
    if response
        .content_length()
        .is_some_and(|length| length > max_bytes)
    {
        return Err(UpdateError::Network(
            "update response is too large".to_owned(),
        ));
    }
    let mut bytes = Vec::new();
    response
        .by_ref()
        .take(max_bytes + 1)
        .read_to_end(&mut bytes)
        .map_err(UpdateError::Io)?;
    if bytes.len() as u64 > max_bytes {
        return Err(UpdateError::Network(
            "update response is too large".to_owned(),
        ));
    }
    Ok(bytes)
}

fn verify_signature(data: &[u8], signature: &str, public_key: &str) -> Result<(), UpdateError> {
    let public_key = decode_base64_text(public_key)?;
    let public_key = PublicKey::decode(&public_key)
        .map_err(|error| UpdateError::Signature(error.to_string()))?;
    let signature = decode_base64_text(signature)?;
    let signature =
        Signature::decode(&signature).map_err(|error| UpdateError::Signature(error.to_string()))?;
    public_key
        .verify(data, &signature, true)
        .map_err(|error| UpdateError::Signature(error.to_string()))
}

fn decode_base64_text(value: &str) -> Result<String, UpdateError> {
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(value)
        .map_err(|error| UpdateError::Signature(error.to_string()))?;
    String::from_utf8(bytes).map_err(|error| UpdateError::Signature(error.to_string()))
}

fn validate_app_bundle_path(path: &Path) -> Result<(), UpdateError> {
    if path.extension().and_then(|value| value.to_str()) != Some("app") || path.parent().is_none() {
        return Err(UpdateError::InvalidConfig(
            "updater target must be an .app bundle".to_owned(),
        ));
    }
    Ok(())
}

fn install_archive(
    app_bundle: &Path,
    expected_version: &Version,
    bytes: &[u8],
) -> Result<(), UpdateError> {
    validate_app_bundle_path(app_bundle)?;
    if !app_bundle.is_dir() {
        return Err(UpdateError::InvalidConfig(
            "current app bundle does not exist".to_owned(),
        ));
    }
    let parent = app_bundle.parent().expect("validated parent");
    let app_name = app_bundle.file_name().expect("validated app name");
    let staging = tempfile::Builder::new()
        .prefix(".codinal-update-")
        .tempdir_in(parent)?;
    extract_app_archive(bytes, &staging, app_name)?;
    let staged_app = staging.path().join(app_name);
    if !staged_app.join("Contents/MacOS").is_dir() {
        return Err(UpdateError::InvalidArchive(
            "archive does not contain a macOS app bundle".to_owned(),
        ));
    }
    validate_bundle_version(&staged_app, expected_version)?;

    let backup = backup_path(app_bundle);
    let next_backup = next_backup_path(app_bundle);
    recover_pending_backup(&backup, &next_backup)?;
    atomic_swap(app_bundle, &staged_app)?;
    if let Err(publish_error) = fs::rename(&staged_app, &next_backup) {
        let restore_result = atomic_swap(app_bundle, &staged_app);
        return match restore_result {
            Ok(()) => Err(UpdateError::Io(publish_error)),
            Err(restore_error) => {
                let retained = staging.keep();
                Err(UpdateError::Io(io::Error::new(
                    publish_error.kind(),
                    format!(
                        "backup publication failed: {publish_error}; atomic restore failed: {restore_error}; old app retained at {}",
                        retained.display()
                    ),
                )))
            }
        };
    }
    recover_pending_backup(&backup, &next_backup)?;
    Ok(())
}

fn extract_app_archive(
    bytes: &[u8],
    staging: &TempDir,
    app_name: &std::ffi::OsStr,
) -> Result<(), UpdateError> {
    let decoder = GzDecoder::new(bytes);
    let mut archive = tar::Archive::new(decoder);
    let mut extracted_bytes = 0_u64;
    for (index, entry) in archive.entries()?.enumerate() {
        if index >= MAX_ARCHIVE_ENTRIES {
            return Err(UpdateError::InvalidArchive(
                "archive contains too many entries".to_owned(),
            ));
        }
        let mut entry = entry?;
        extracted_bytes = extracted_bytes
            .checked_add(entry.header().size()?)
            .ok_or_else(|| UpdateError::InvalidArchive("archive size overflow".to_owned()))?;
        if extracted_bytes > MAX_EXTRACTED_BYTES {
            return Err(UpdateError::InvalidArchive(
                "archive expands beyond the allowed size".to_owned(),
            ));
        }
        let path = entry.path()?.into_owned();
        validate_archive_path(&path, app_name)?;
        let entry_type = entry.header().entry_type();
        if entry_type.is_symlink() {
            let target = entry.link_name()?.ok_or_else(|| {
                UpdateError::InvalidArchive(format!(
                    "symbolic link has no target at {}",
                    path.display()
                ))
            })?;
            validate_symlink_target(&path, &target)?;
        }
        if !is_safe_entry_type(entry_type) {
            return Err(UpdateError::InvalidArchive(format!(
                "unsupported archive entry type at {}",
                path.display()
            )));
        }
        entry.unpack_in(staging.path())?;
    }
    Ok(())
}

fn validate_bundle_version(
    app_bundle: &Path,
    expected_version: &Version,
) -> Result<(), UpdateError> {
    let info_plist = app_bundle.join("Contents/Info.plist");
    let plist = plist::Value::from_file(&info_plist)
        .map_err(|error| UpdateError::InvalidArchive(error.to_string()))?;
    let version = plist
        .as_dictionary()
        .and_then(|dictionary| dictionary.get("CFBundleShortVersionString"))
        .and_then(plist::Value::as_string)
        .ok_or_else(|| {
            UpdateError::InvalidArchive("updated app has no CFBundleShortVersionString".to_owned())
        })?;
    let version = Version::parse(version.trim_start_matches('v'))
        .map_err(|error| UpdateError::InvalidArchive(error.to_string()))?;
    if &version != expected_version {
        return Err(UpdateError::InvalidArchive(format!(
            "signed bundle version {version} does not match manifest version {expected_version}"
        )));
    }
    Ok(())
}

fn validate_archive_path(path: &Path, app_name: &std::ffi::OsStr) -> Result<(), UpdateError> {
    let mut components = path.components();
    if components.next() != Some(Component::Normal(app_name))
        || components.any(|component| !matches!(component, Component::Normal(_)))
    {
        return Err(UpdateError::InvalidArchive(format!(
            "archive entry escapes the expected app bundle: {}",
            path.display()
        )));
    }
    Ok(())
}

fn is_safe_entry_type(entry_type: EntryType) -> bool {
    entry_type.is_file() || entry_type.is_dir() || entry_type.is_symlink()
}

fn validate_symlink_target(link_path: &Path, target: &Path) -> Result<(), UpdateError> {
    let mut depth = link_path.parent().map_or(0, |parent| {
        parent
            .components()
            .filter(|component| matches!(component, Component::Normal(_)))
            .count()
    });
    for component in target.components() {
        match component {
            Component::Normal(_) => depth += 1,
            Component::CurDir => {}
            Component::ParentDir if depth > 1 => depth -= 1,
            _ => {
                return Err(UpdateError::InvalidArchive(format!(
                    "symbolic link escapes the app bundle: {} -> {}",
                    link_path.display(),
                    target.display()
                )))
            }
        }
    }
    Ok(())
}

fn backup_path(app_bundle: &Path) -> PathBuf {
    app_bundle.with_extension("app.backup")
}

fn next_backup_path(app_bundle: &Path) -> PathBuf {
    app_bundle.with_extension("app.backup.next")
}

fn recover_pending_backup(backup: &Path, next_backup: &Path) -> Result<(), UpdateError> {
    if !next_backup.exists() {
        return Ok(());
    }
    if backup.exists() {
        remove_path_if_exists(backup)?;
    }
    fs::rename(next_backup, backup).map_err(UpdateError::Io)
}

fn rollback_app(app_bundle: &Path) -> Result<(), UpdateError> {
    validate_app_bundle_path(app_bundle)?;
    let backup = backup_path(app_bundle);
    let next_backup = next_backup_path(app_bundle);
    recover_pending_backup(&backup, &next_backup)?;
    if !backup.is_dir() {
        return Err(UpdateError::InvalidConfig(
            "no update backup found".to_owned(),
        ));
    }
    atomic_swap(app_bundle, &backup)?;
    remove_path_if_exists(&backup)
}

#[cfg(target_os = "macos")]
fn atomic_swap(left: &Path, right: &Path) -> Result<(), UpdateError> {
    use std::ffi::CString;
    use std::os::unix::ffi::OsStrExt;

    let left = CString::new(left.as_os_str().as_bytes())
        .map_err(|_| UpdateError::InvalidConfig("app path contains a NUL byte".to_owned()))?;
    let right = CString::new(right.as_os_str().as_bytes())
        .map_err(|_| UpdateError::InvalidConfig("app path contains a NUL byte".to_owned()))?;
    // SAFETY: both C strings remain alive for the call and AT_FDCWD resolves
    // the validated absolute or caller-relative paths exactly as std::fs does.
    let result = unsafe {
        libc::renameatx_np(
            libc::AT_FDCWD,
            left.as_ptr(),
            libc::AT_FDCWD,
            right.as_ptr(),
            libc::RENAME_SWAP,
        )
    };
    if result == 0 {
        Ok(())
    } else {
        Err(UpdateError::Io(io::Error::last_os_error()))
    }
}

#[cfg(not(target_os = "macos"))]
fn atomic_swap(_left: &Path, _right: &Path) -> Result<(), UpdateError> {
    Err(UpdateError::InvalidConfig(
        "atomic app updates are supported only on macOS".to_owned(),
    ))
}

fn remove_path_if_exists(path: &Path) -> Result<(), UpdateError> {
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.is_dir() => fs::remove_dir_all(path)?,
        Ok(_) => fs::remove_file(path)?,
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(error) => return Err(UpdateError::Io(error)),
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use flate2::write::GzEncoder;
    use flate2::Compression;

    fn archive(entries: &[(&str, &[u8])]) -> Vec<u8> {
        let encoder = GzEncoder::new(Vec::new(), Compression::default());
        let mut builder = tar::Builder::new(encoder);
        for (path, contents) in entries {
            let mut header = tar::Header::new_gnu();
            header.set_size(contents.len() as u64);
            header.set_mode(0o755);
            header.set_cksum();
            builder.append_data(&mut header, path, *contents).unwrap();
        }
        builder.into_inner().unwrap().finish().unwrap()
    }

    fn write_info_plist(app: &Path, version: &str) {
        let mut dictionary = plist::Dictionary::new();
        dictionary.insert(
            "CFBundleShortVersionString".to_owned(),
            plist::Value::String(version.to_owned()),
        );
        plist::Value::Dictionary(dictionary)
            .to_file_xml(app.join("Contents/Info.plist"))
            .unwrap();
    }

    #[test]
    fn rejects_non_https_urls() {
        let error =
            require_https(&Url::parse("http://example.com/latest.json").unwrap()).unwrap_err();
        assert!(error.to_string().contains("HTTPS"));
    }

    #[test]
    fn release_bundle_constructor_rejects_invalid_versions() {
        let error = NativeUpdater::for_release_bundle(
            "not-a-version",
            PathBuf::from("/Applications/Codinal.app"),
        )
        .err()
        .expect("invalid version must be rejected");
        assert!(matches!(error, UpdateError::InvalidConfig(_)));
    }

    #[test]
    fn restart_helper_derives_only_the_containing_app_bundle() {
        let bundle = app_bundle_for_executable(Path::new(
            "/Applications/Codinal.app/Contents/MacOS/codinal",
        ))
        .unwrap();
        assert_eq!(bundle, Path::new("/Applications/Codinal.app"));
        assert!(app_bundle_for_executable(Path::new("/tmp/codinal")).is_err());
    }

    #[test]
    fn rejects_archive_path_traversal() {
        let error = validate_archive_path(
            Path::new("../Codinal.app/Contents/MacOS/codinal"),
            std::ffi::OsStr::new("Codinal.app"),
        )
        .unwrap_err();
        assert!(error.to_string().contains("escapes"));
    }

    #[test]
    fn rejects_symlink_that_escapes_app_bundle() {
        let error = validate_symlink_target(
            Path::new("Codinal.app/Contents/Frameworks/escape"),
            Path::new("../../../outside"),
        )
        .unwrap_err();
        assert!(error.to_string().contains("escapes"));

        validate_symlink_target(
            Path::new("Codinal.app/Contents/Frameworks/current"),
            Path::new("Versions/Current"),
        )
        .unwrap();
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn installs_and_rolls_back_atomically() {
        let temp = tempfile::tempdir().unwrap();
        let app = temp.path().join("Codinal.app");
        fs::create_dir_all(app.join("Contents/MacOS")).unwrap();
        fs::write(app.join("Contents/MacOS/codinal"), b"old").unwrap();
        write_info_plist(&app, "0.9.0");
        let previous_backup = backup_path(&app);
        fs::create_dir_all(previous_backup.join("Contents/MacOS")).unwrap();
        fs::write(previous_backup.join("Contents/MacOS/codinal"), b"older").unwrap();
        let update = archive(&[
            ("Codinal.app/Contents/MacOS/codinal", b"new"),
            (
                "Codinal.app/Contents/Info.plist",
                br#"<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict><key>CFBundleShortVersionString</key><string>1.0.0</string></dict></plist>"#,
            ),
        ]);

        install_archive(&app, &Version::new(1, 0, 0), &update).unwrap();
        assert_eq!(
            fs::read(app.join("Contents/MacOS/codinal")).unwrap(),
            b"new"
        );
        assert_eq!(
            fs::read(backup_path(&app).join("Contents/MacOS/codinal")).unwrap(),
            b"old"
        );

        rollback_app(&app).unwrap();
        assert_eq!(
            fs::read(app.join("Contents/MacOS/codinal")).unwrap(),
            b"old"
        );
        assert!(!backup_path(&app).exists());
    }

    #[test]
    fn rejects_bundle_version_that_differs_from_manifest() {
        let temp = tempfile::tempdir().unwrap();
        let app = temp.path().join("Codinal.app");
        fs::create_dir_all(app.join("Contents")).unwrap();
        write_info_plist(&app, "1.0.0");
        let error = validate_bundle_version(&app, &Version::new(2, 0, 0)).unwrap_err();
        assert!(error.to_string().contains("does not match"));
    }

    #[test]
    fn invalid_signature_is_rejected() {
        let error =
            verify_signature(b"payload", "not-base64", DEFAULT_UPDATE_PUBLIC_KEY).unwrap_err();
        assert!(error.to_string().contains("Invalid") || !error.to_string().is_empty());
    }
}
