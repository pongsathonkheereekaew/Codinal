use std::fs;
use std::io;
use std::path::PathBuf;

const MAX_PATH_BYTES: usize = 4096;

pub fn validate_workspace_output(output: &[u8]) -> io::Result<PathBuf> {
    if output.is_empty() || output.len() > MAX_PATH_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "workspace selection is invalid",
        ));
    }
    let value = std::str::from_utf8(output)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "workspace path is not UTF-8"))?
        .trim_end_matches(['\r', '\n']);
    if value.is_empty() || value.as_bytes().contains(&0) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "workspace selection is invalid",
        ));
    }
    let path = PathBuf::from(value);
    if !path.is_absolute() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "workspace path must be absolute",
        ));
    }
    let canonical = fs::canonicalize(path)?;
    if !canonical.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace is not a directory",
        ));
    }
    Ok(canonical)
}

#[cfg(target_os = "macos")]
pub fn choose_workspace() -> io::Result<PathBuf> {
    let path = rfd::FileDialog::new()
        .set_title("Choose a Codinal workspace")
        .pick_folder()
        .ok_or_else(|| {
            io::Error::new(io::ErrorKind::Interrupted, "workspace selection cancelled")
        })?;
    validate_workspace_output(path.to_string_lossy().as_bytes())
}

#[cfg(not(target_os = "macos"))]
pub fn choose_workspace() -> io::Result<PathBuf> {
    Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "native workspace selection is unavailable",
    ))
}

#[cfg(test)]
mod tests {
    use super::validate_workspace_output;

    #[test]
    fn accepts_existing_absolute_directory_with_newline() {
        let current = std::env::current_dir().expect("current directory");
        let selected = format!("{}\n", current.display());

        assert_eq!(
            validate_workspace_output(selected.as_bytes()).expect("valid path"),
            current.canonicalize().expect("canonical directory")
        );
    }

    #[test]
    fn rejects_relative_and_oversized_paths() {
        assert!(validate_workspace_output(b"relative/path\n").is_err());
        assert!(validate_workspace_output(&vec![b'a'; 4097]).is_err());
    }
}
