use std::io;

fn validated_browser_url(raw: &str) -> io::Result<url::Url> {
    let raw = raw.trim();
    if raw.is_empty()
        || raw.len() > 2_048
        || raw
            .bytes()
            .any(|byte| byte == 0 || byte == b'\r' || byte == b'\n')
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "browser URL is invalid",
        ));
    }
    let url = url::Url::parse(raw)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "browser URL is invalid"))?;
    if !matches!(url.scheme(), "http" | "https")
        || url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "browser URL must be credential-free HTTP(S)",
        ));
    }
    Ok(url)
}

#[cfg(target_os = "macos")]
mod macos {
    use std::env;
    use std::ffi::CStr;
    use std::io;
    use std::mem::MaybeUninit;
    use std::os::fd::RawFd;
    use std::os::unix::fs::MetadataExt;
    use std::path::Path;

    use objc2_app_kit::NSWorkspace;
    use objc2_foundation::{NSArray, NSString, NSURL};

    const HELPER_ARGUMENT: &str = "--codinal-open-fd";

    pub fn open_browser_url(raw: &str) -> io::Result<()> {
        let parsed = super::validated_browser_url(raw)?;
        let reference = NSURL::URLWithString(&NSString::from_str(parsed.as_str()))
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "browser URL is invalid"))?;
        if NSWorkspace::sharedWorkspace().openURL(&reference) {
            Ok(())
        } else {
            Err(io::Error::other("system browser did not accept the URL"))
        }
    }

    pub fn run_helper_from_args() -> bool {
        let arguments: Vec<String> = env::args().collect();
        if arguments.get(1).map(String::as_str) != Some(HELPER_ARGUMENT) {
            return false;
        }
        let result = (|| {
            if arguments.len() != 4 {
                return Err("invalid host helper arguments".to_owned());
            }
            let mode = arguments[2].as_str();
            if !matches!(mode, "open" | "reveal") {
                return Err("invalid open mode".to_owned());
            }
            let descriptor = arguments[3]
                .parse::<RawFd>()
                .map_err(|_| "invalid file descriptor".to_owned())?;
            open_descriptor(descriptor, mode)
        })();
        if let Err(error) = result {
            eprintln!("{error}");
            std::process::exit(1);
        }
        true
    }

    fn open_descriptor(descriptor: RawFd, mode: &str) -> Result<(), String> {
        let reference = file_reference_for_descriptor(descriptor)?;
        let workspace = NSWorkspace::sharedWorkspace();
        if mode == "reveal" {
            workspace.activateFileViewerSelectingURLs(&NSArray::from_retained_slice(&[reference]));
            return Ok(());
        }
        if workspace.openURL(&reference) {
            Ok(())
        } else {
            Err("could not open project item".to_owned())
        }
    }

    fn file_reference_for_descriptor(
        descriptor: RawFd,
    ) -> Result<objc2::rc::Retained<NSURL>, String> {
        let mut metadata = MaybeUninit::<libc::stat>::uninit();
        if unsafe { libc::fstat(descriptor, metadata.as_mut_ptr()) } != 0 {
            return Err("validated project item is unavailable".to_owned());
        }
        let metadata = unsafe { metadata.assume_init() };
        let mut buffer = [0_i8; libc::PATH_MAX as usize];
        if unsafe { libc::fcntl(descriptor, libc::F_GETPATH, buffer.as_mut_ptr()) } == -1 {
            return Err("validated project item path is unavailable".to_owned());
        }
        let path = unsafe { CStr::from_ptr(buffer.as_ptr()) }
            .to_str()
            .map_err(|_| "validated project item path is invalid".to_owned())?;
        let url = NSURL::fileURLWithPath(&NSString::from_str(path));
        let reference = url
            .fileReferenceURL()
            .ok_or_else(|| "file reference is unavailable".to_owned())?;
        let reference_path = reference
            .path()
            .ok_or_else(|| "file reference path is unavailable".to_owned())?
            .to_string();
        let reference_metadata = Path::new(&reference_path)
            .metadata()
            .map_err(|_| "file reference is unavailable".to_owned())?;
        if reference_metadata.dev() != metadata.st_dev as u64
            || reference_metadata.ino() != metadata.st_ino
        {
            return Err("project item identity changed".to_owned());
        }
        Ok(reference)
    }

    #[cfg(test)]
    mod tests {
        use std::fs;
        use std::os::fd::AsRawFd;

        use super::file_reference_for_descriptor;

        #[test]
        fn file_reference_keeps_vnode_identity_after_rename() {
            let temporary = tempfile::tempdir().expect("temporary directory");
            let original = temporary.path().join("original.txt");
            fs::write(&original, "allowed").expect("write original");
            let file = fs::File::open(&original).expect("open original");
            let renamed = temporary.path().join("renamed.txt");
            fs::rename(&original, &renamed).expect("rename original");
            fs::write(&original, "replacement").expect("write replacement");

            let reference = file_reference_for_descriptor(file.as_raw_fd())
                .expect("create identity-preserving reference");
            let moved_again = temporary.path().join("moved-again.txt");
            fs::rename(&renamed, &moved_again).expect("rename after reference");
            fs::write(&renamed, "second replacement").expect("replace referenced path");
            let path = reference.path().expect("reference path").to_string();

            assert_eq!(fs::read_to_string(path).expect("read reference"), "allowed");
        }
    }
}

#[cfg(target_os = "macos")]
pub use macos::{open_browser_url, run_helper_from_args};

#[cfg(not(target_os = "macos"))]
pub fn run_helper_from_args() -> bool {
    false
}

#[cfg(not(target_os = "macos"))]
pub fn open_browser_url(raw: &str) -> io::Result<()> {
    let _ = validated_browser_url(raw)?;
    Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "system browser bridge is available only on macOS",
    ))
}

#[cfg(test)]
mod validation_tests {
    use super::validated_browser_url;

    #[test]
    fn browser_bridge_accepts_only_credential_free_http_urls() {
        assert_eq!(
            validated_browser_url("https://example.com/path?q=1")
                .expect("valid URL")
                .scheme(),
            "https"
        );
        assert!(validated_browser_url("file:///tmp/index.html").is_err());
        assert!(validated_browser_url("javascript:alert(1)").is_err());
        assert!(validated_browser_url("https://user:secret@example.com").is_err());
        assert!(validated_browser_url("https://example.com\nfile:///tmp/leak").is_err());
    }
}
