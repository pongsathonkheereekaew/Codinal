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

pub fn validate_source_output(output: &[u8]) -> io::Result<PathBuf> {
    if output.is_empty() || output.len() > MAX_PATH_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "source selection is invalid",
        ));
    }
    let value = std::str::from_utf8(output)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "source path is not UTF-8"))?
        .trim_end_matches(['\r', '\n']);
    if value.is_empty() || value.as_bytes().contains(&0) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "source selection is invalid",
        ));
    }
    let path = PathBuf::from(value);
    if !path.is_absolute() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "source path must be absolute",
        ));
    }
    let metadata = fs::symlink_metadata(&path)?;
    if metadata.file_type().is_symlink() || (!metadata.is_file() && !metadata.is_dir()) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "source must be a regular file or folder",
        ));
    }
    fs::canonicalize(path)
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

#[cfg(target_os = "macos")]
pub fn choose_workspace_folders() -> io::Result<Vec<PathBuf>> {
    let paths = rfd::FileDialog::new()
        .set_title("Add project source folders")
        .pick_folders()
        .ok_or_else(|| io::Error::new(io::ErrorKind::Interrupted, "folder selection cancelled"))?;
    let mut validated = Vec::new();
    for path in paths {
        let path = validate_workspace_output(path.to_string_lossy().as_bytes())?;
        if !validated.contains(&path) {
            validated.push(path);
        }
    }
    if validated.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "no project source folders selected",
        ));
    }
    Ok(validated)
}

#[cfg(target_os = "macos")]
pub fn choose_source_file() -> io::Result<PathBuf> {
    let path = rfd::FileDialog::new()
        .set_title("Add a source file")
        .pick_file()
        .ok_or_else(|| io::Error::new(io::ErrorKind::Interrupted, "source selection cancelled"))?;
    validate_source_output(path.to_string_lossy().as_bytes())
}

#[cfg(target_os = "macos")]
pub fn choose_source_folder() -> io::Result<PathBuf> {
    let path = rfd::FileDialog::new()
        .set_title("Add a source folder")
        .pick_folder()
        .ok_or_else(|| io::Error::new(io::ErrorKind::Interrupted, "source selection cancelled"))?;
    validate_source_output(path.to_string_lossy().as_bytes())
}

#[cfg(not(target_os = "macos"))]
pub fn choose_workspace() -> io::Result<PathBuf> {
    Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "native workspace selection is unavailable",
    ))
}

#[cfg(not(target_os = "macos"))]
pub fn choose_workspace_folders() -> io::Result<Vec<PathBuf>> {
    Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "native folder selection is unavailable",
    ))
}

#[cfg(not(target_os = "macos"))]
pub fn choose_source_file() -> io::Result<PathBuf> {
    Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "native source selection is unavailable",
    ))
}

#[cfg(not(target_os = "macos"))]
pub fn choose_source_folder() -> io::Result<PathBuf> {
    Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "native source selection is unavailable",
    ))
}

#[cfg(test)]
mod tests {
    use super::{validate_source_output, validate_workspace_output};

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

    #[test]
    fn source_selection_accepts_existing_file_or_directory_only() {
        let current = std::env::current_dir().expect("current directory");
        let file = current.join("Cargo.toml");
        assert_eq!(
            validate_source_output(file.to_string_lossy().as_bytes()).expect("source file"),
            file.canonicalize().expect("canonical file")
        );
        assert_eq!(
            validate_source_output(current.to_string_lossy().as_bytes()).expect("source folder"),
            current.canonicalize().expect("canonical folder")
        );
    }
}
