//! Pure state and read-only workspace projections for the native tool panel.

#[cfg(test)]
use std::fs;
#[cfg(test)]
use std::io::{self, Read};
#[cfg(test)]
use std::path::{Component, Path, PathBuf};
#[cfg(test)]
use std::process::{Command, ExitStatus, Stdio};
#[cfg(test)]
use std::sync::mpsc::{sync_channel, TryRecvError};
#[cfg(test)]
use std::thread;
#[cfg(test)]
use std::time::{Duration, Instant};

use crate::icons::Icon;

#[cfg(test)]
const GIT_COMMAND_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SidePanelTool {
    Review,
    Terminal,
    Browser,
    Files,
    SideChat,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct SidePanelTabs {
    open: Vec<SidePanelTool>,
    active: Option<SidePanelTool>,
}

impl SidePanelTabs {
    pub fn open(&self) -> &[SidePanelTool] {
        &self.open
    }

    pub fn active(&self) -> Option<SidePanelTool> {
        self.active
    }

    pub fn activate(&mut self, tool: SidePanelTool) {
        if !self.open.contains(&tool) {
            self.open.push(tool);
        }
        self.active = Some(tool);
    }

    pub fn close_active(&mut self) {
        let Some(active) = self.active else {
            return;
        };
        let Some(index) = self.open.iter().position(|tool| *tool == active) else {
            self.active = None;
            return;
        };
        self.open.remove(index);
        self.active = self
            .open
            .get(index)
            .copied()
            .or_else(|| self.open.last().copied());
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SidePanelItem {
    pub tool: SidePanelTool,
    pub icon: Icon,
    pub label: &'static str,
    pub shortcut: &'static str,
}

pub const SIDE_PANEL_ITEMS: [SidePanelItem; 5] = [
    SidePanelItem {
        tool: SidePanelTool::Review,
        icon: Icon::Review,
        label: "Review",
        shortcut: "⌃⇧G",
    },
    SidePanelItem {
        tool: SidePanelTool::Terminal,
        icon: Icon::Terminal,
        label: "Terminal",
        shortcut: "⌘J",
    },
    SidePanelItem {
        tool: SidePanelTool::Browser,
        icon: Icon::Browser,
        label: "Browser",
        shortcut: "⌘T",
    },
    SidePanelItem {
        tool: SidePanelTool::Files,
        icon: Icon::Files,
        label: "Files",
        shortcut: "⌘P",
    },
    SidePanelItem {
        tool: SidePanelTool::SideChat,
        icon: Icon::SideChat,
        label: "Side chat",
        shortcut: "⌥⌘S",
    },
];

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct WorkspaceEntry {
    pub relative_path: String,
    pub is_directory: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct WorkspaceSnapshot {
    pub root: String,
    pub entries: Vec<WorkspaceEntry>,
    pub truncated: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReviewSnapshot {
    pub branch: String,
    pub summary: String,
    pub diff: String,
    pub truncated: bool,
}

pub fn review_changed_paths(diff: &str, limit: usize) -> Vec<String> {
    if limit == 0 {
        return Vec::new();
    }
    let mut paths = Vec::new();
    for line in diff.lines() {
        let Some(rest) = line.strip_prefix("diff --git a/") else {
            continue;
        };
        let Some((_, path)) = rest.split_once(" b/") else {
            continue;
        };
        if !paths.iter().any(|existing| existing == path) {
            paths.push(path.to_owned());
        }
        if paths.len() >= limit {
            break;
        }
    }
    paths
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FilePreview {
    pub relative_path: String,
    pub text: String,
    pub truncated: bool,
    pub binary: bool,
}

pub fn tool_for_shortcut(
    key: &str,
    platform: bool,
    control: bool,
    alt: bool,
    shift: bool,
) -> Option<SidePanelTool> {
    match (
        key.to_ascii_lowercase().as_str(),
        platform,
        control,
        alt,
        shift,
    ) {
        ("g", false, true, false, true) => Some(SidePanelTool::Review),
        ("j", true, false, false, false) => Some(SidePanelTool::Terminal),
        ("t", true, false, false, false) => Some(SidePanelTool::Browser),
        ("p", true, false, false, false) => Some(SidePanelTool::Files),
        ("s", true, false, true, false) => Some(SidePanelTool::SideChat),
        _ => None,
    }
}

#[cfg(test)]
pub fn inspect_workspace(root: &Path, limit: usize) -> io::Result<WorkspaceSnapshot> {
    if limit == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace entry limit must be positive",
        ));
    }
    let root = validate_workspace_root(root)?;
    let mut entries = Vec::new();
    let mut truncated = false;
    collect_entries(
        &root,
        &root,
        0,
        limit.min(1_000),
        &mut entries,
        &mut truncated,
    )?;
    Ok(WorkspaceSnapshot {
        root: root.to_string_lossy().into_owned(),
        entries,
        truncated,
    })
}

#[cfg(test)]
pub fn read_workspace_file_preview(
    root: &Path,
    relative_path: &str,
    byte_limit: usize,
) -> io::Result<FilePreview> {
    if byte_limit == 0 || byte_limit > 1024 * 1024 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "file preview limit must be between 1 byte and 1 MiB",
        ));
    }
    let root = validate_workspace_root(root)?;
    let relative = Path::new(relative_path);
    if relative.is_absolute()
        || relative
            .components()
            .any(|component| !matches!(component, Component::Normal(_)))
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace file path must be relative and traversal-free",
        ));
    }
    let mut candidate = root.clone();
    for component in relative.components() {
        let Component::Normal(component) = component else {
            unreachable!("relative components were validated")
        };
        candidate.push(component);
        if fs::symlink_metadata(&candidate)?.file_type().is_symlink() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "workspace file path may not contain symlinks",
            ));
        }
    }
    let canonical = fs::canonicalize(&candidate)?;
    if !canonical.starts_with(&root) || !canonical.is_file() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace preview target must be a regular file inside the workspace",
        ));
    }
    let mut bytes = Vec::with_capacity(byte_limit.min(64 * 1024) + 1);
    fs::File::open(&canonical)?
        .take(byte_limit as u64 + 1)
        .read_to_end(&mut bytes)?;
    let truncated = bytes.len() > byte_limit;
    bytes.truncate(byte_limit);
    let binary = bytes.contains(&0) || std::str::from_utf8(&bytes).is_err();
    let text = if binary {
        format!("Binary file · {} byte preview suppressed", bytes.len())
    } else {
        String::from_utf8(bytes).expect("validated UTF-8 preview")
    };
    Ok(FilePreview {
        relative_path: relative.to_string_lossy().into_owned(),
        text,
        truncated,
        binary,
    })
}

#[cfg(test)]
fn collect_entries(
    root: &Path,
    directory: &Path,
    depth: usize,
    limit: usize,
    output: &mut Vec<WorkspaceEntry>,
    truncated: &mut bool,
) -> io::Result<()> {
    let remaining = limit.saturating_sub(output.len());
    if remaining == 0 {
        *truncated = true;
        return Ok(());
    }
    let mut scanned = 0;
    let mut children = Vec::with_capacity(remaining.min(128));
    for entry in fs::read_dir(directory)?.take(remaining.saturating_add(1)) {
        scanned += 1;
        let entry = entry?;
        let path = entry.path();
        let metadata = fs::symlink_metadata(&path)?;
        if metadata.file_type().is_symlink() {
            *truncated = true;
            continue;
        }
        children.push((path, metadata.is_dir()));
    }
    if scanned > remaining {
        *truncated = true;
    }
    children.sort_by(|(left_path, left_dir), (right_path, right_dir)| {
        right_dir.cmp(left_dir).then_with(|| {
            left_path
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_ascii_lowercase()
                .cmp(
                    &right_path
                        .file_name()
                        .unwrap_or_default()
                        .to_string_lossy()
                        .to_ascii_lowercase(),
                )
        })
    });
    let mut directories = Vec::new();
    for (path, is_directory) in children.into_iter().take(remaining) {
        if output.len() == limit {
            *truncated = true;
            break;
        }
        let relative = path.strip_prefix(root).map_err(|_| {
            io::Error::new(io::ErrorKind::InvalidData, "workspace entry escaped root")
        })?;
        output.push(WorkspaceEntry {
            relative_path: relative.to_string_lossy().into_owned(),
            is_directory,
        });
        if is_directory && depth < 1 {
            directories.push(path);
        }
    }
    for directory in directories {
        if output.len() == limit {
            *truncated = true;
            break;
        }
        collect_entries(root, &directory, depth + 1, limit, output, truncated)?;
    }
    Ok(())
}

#[cfg(test)]
pub fn inspect_git_review(root: &Path, byte_limit: usize) -> io::Result<ReviewSnapshot> {
    if byte_limit < 1_024 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "review byte limit is too small",
        ));
    }
    let root = validate_workspace_root(root)?;
    const STAGED_SEPARATOR: &str = "\n\n--- Staged changes ---\n";
    let summary_limit = (byte_limit / 4).min(24 * 1_024);
    let (summary, summary_truncated) = run_git_bounded(
        &root,
        &["status", "--short", "--branch", "--untracked-files=normal"],
        summary_limit,
    )?;
    let remaining = byte_limit.saturating_sub(summary.len());
    let diff_budget = remaining.saturating_sub(STAGED_SEPARATOR.len());
    let unstaged_limit = diff_budget / 2;
    let staged_limit = diff_budget.saturating_sub(unstaged_limit);
    let (unstaged, unstaged_truncated) = run_git_bounded(
        &root,
        &[
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            "--unified=3",
            "--",
        ],
        unstaged_limit,
    )?;
    let (staged, staged_truncated) = run_git_bounded(
        &root,
        &[
            "diff",
            "--cached",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            "--unified=3",
            "--",
        ],
        staged_limit,
    )?;
    let branch = summary
        .lines()
        .find_map(|line| line.strip_prefix("## "))
        .map(|line| line.split_once("...").map_or(line, |(branch, _)| branch))
        .filter(|branch| !branch.trim().is_empty())
        .unwrap_or("Detached HEAD")
        .trim()
        .to_owned();
    let summary = if summary.trim().is_empty() {
        "Working tree clean".to_owned()
    } else {
        summary
    };
    let mut diff = unstaged;
    if !staged.trim().is_empty() {
        if !diff.trim().is_empty() {
            diff.push_str(STAGED_SEPARATOR);
        }
        diff.push_str(&staged);
    }
    if diff.trim().is_empty() {
        diff = "No tracked diff".to_owned();
    }
    Ok(ReviewSnapshot {
        branch,
        summary,
        diff,
        truncated: summary_truncated || unstaged_truncated || staged_truncated,
    })
}

#[cfg(test)]
fn validate_workspace_root(root: &Path) -> io::Result<PathBuf> {
    let metadata = fs::symlink_metadata(root)?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace root must be a non-symlink directory",
        ));
    }
    fs::canonicalize(root)
}

#[cfg(test)]
fn run_git_bounded(root: &Path, args: &[&str], limit: usize) -> io::Result<(String, bool)> {
    let mut command = Command::new("git");
    command
        .arg("-c")
        .arg("core.pager=cat")
        .arg("-c")
        .arg("core.fsmonitor=false")
        .arg("-c")
        .arg("core.hooksPath=/dev/null")
        .arg("-c")
        .arg("diff.external=")
        .arg("-C")
        .arg(root)
        .args(args)
        .env("GIT_OPTIONAL_LOCKS", "0")
        .env("GIT_PAGER", "cat");
    let output = run_command_bounded(command, limit, GIT_COMMAND_TIMEOUT)?;
    if !output.status.success() && !output.truncated {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace is not an available Git worktree",
        ));
    }
    let mut bytes = output.bytes;
    let mut truncated = output.truncated;
    while std::str::from_utf8(&bytes).is_err() && bytes.pop().is_some() {
        truncated = true;
    }
    Ok((String::from_utf8_lossy(&bytes).into_owned(), truncated))
}

#[cfg(test)]
#[derive(Debug)]
struct BoundedCommandOutput {
    bytes: Vec<u8>,
    truncated: bool,
    status: ExitStatus,
}

#[cfg(test)]
fn run_command_bounded(
    mut command: Command,
    limit: usize,
    timeout: Duration,
) -> io::Result<BoundedCommandOutput> {
    let mut child = command
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| io::Error::other("bounded command stdout unavailable"))?;
    let (limit_sender, limit_receiver) = sync_channel(1);
    let reader = thread::spawn(move || -> io::Result<(Vec<u8>, bool)> {
        let mut stdout = stdout;
        let mut bytes = Vec::with_capacity(limit.min(16 * 1_024));
        let mut buffer = [0_u8; 8 * 1_024];
        loop {
            let read = stdout.read(&mut buffer)?;
            if read == 0 {
                return Ok((bytes, false));
            }
            let remaining = limit.saturating_sub(bytes.len());
            if read > remaining {
                bytes.extend_from_slice(&buffer[..remaining]);
                let _ = limit_sender.try_send(());
                return Ok((bytes, true));
            }
            bytes.extend_from_slice(&buffer[..read]);
        }
    });

    let deadline = Instant::now() + timeout;
    let (status, timed_out) = loop {
        match limit_receiver.try_recv() {
            Ok(()) => {
                let _ = child.kill();
                break (child.wait()?, false);
            }
            Err(TryRecvError::Empty) | Err(TryRecvError::Disconnected) => {}
        }
        if let Some(status) = child.try_wait()? {
            break (status, false);
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            break (child.wait()?, true);
        }
        thread::sleep(Duration::from_millis(10));
    };
    let (bytes, truncated) = reader
        .join()
        .map_err(|_| io::Error::other("bounded command reader panicked"))??;
    if timed_out {
        return Err(io::Error::new(
            io::ErrorKind::TimedOut,
            "workspace inspection command timed out",
        ));
    }
    Ok(BoundedCommandOutput {
        bytes,
        truncated,
        status,
    })
}

#[cfg(test)]
mod tests {
    use super::{
        inspect_git_review, inspect_workspace, read_workspace_file_preview, review_changed_paths,
        tool_for_shortcut, SidePanelTabs, SidePanelTool, SIDE_PANEL_ITEMS,
    };
    use std::fs;
    #[cfg(unix)]
    use std::os::unix::fs::PermissionsExt;
    use std::process::Command;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{Duration, Instant};

    static NEXT_TEMP: AtomicU64 = AtomicU64::new(0);

    fn fresh_dir() -> std::path::PathBuf {
        let path = std::env::temp_dir().join(format!(
            "codinal-side-panel-{}-{}",
            std::process::id(),
            NEXT_TEMP.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).expect("create temporary workspace");
        path
    }

    #[test]
    fn codex_style_tool_list_and_shortcuts_are_stable() {
        assert_eq!(
            SIDE_PANEL_ITEMS.map(|item| item.label),
            ["Review", "Terminal", "Browser", "Files", "Side chat"]
        );
        assert_eq!(
            tool_for_shortcut("g", false, true, false, true),
            Some(SidePanelTool::Review)
        );
        assert_eq!(
            tool_for_shortcut("j", true, false, false, false),
            Some(SidePanelTool::Terminal)
        );
        assert_eq!(
            tool_for_shortcut("t", true, false, false, false),
            Some(SidePanelTool::Browser)
        );
        assert_eq!(
            tool_for_shortcut("p", true, false, false, false),
            Some(SidePanelTool::Files)
        );
        assert_eq!(
            tool_for_shortcut("s", true, false, true, false),
            Some(SidePanelTool::SideChat)
        );
        assert_eq!(tool_for_shortcut("t", false, false, false, false), None);
    }

    #[test]
    fn workspace_tool_tabs_keep_open_order_and_select_a_neighbor_on_close() {
        let mut tabs = SidePanelTabs::default();
        tabs.activate(SidePanelTool::Review);
        tabs.activate(SidePanelTool::Terminal);
        tabs.activate(SidePanelTool::Files);
        tabs.activate(SidePanelTool::Review);

        assert_eq!(
            tabs.open(),
            &[
                SidePanelTool::Review,
                SidePanelTool::Terminal,
                SidePanelTool::Files,
            ]
        );
        assert_eq!(tabs.active(), Some(SidePanelTool::Review));

        tabs.close_active();
        assert_eq!(
            tabs.open(),
            &[SidePanelTool::Terminal, SidePanelTool::Files]
        );
        assert_eq!(tabs.active(), Some(SidePanelTool::Terminal));
    }

    #[test]
    fn workspace_projection_is_sorted_bounded_and_does_not_follow_symlinks() {
        let root = fresh_dir();
        fs::create_dir(root.join("src")).expect("create source directory");
        fs::write(root.join("README.md"), "hello").expect("write readme");
        fs::write(root.join("src/main.rs"), "fn main() {}").expect("write source");
        #[cfg(unix)]
        std::os::unix::fs::symlink("/", root.join("outside")).expect("create symlink");

        let snapshot = inspect_workspace(&root, 2).expect("inspect workspace");
        assert_eq!(snapshot.entries.len(), 2);
        assert_eq!(snapshot.entries[0].relative_path, "src");
        assert!(snapshot.entries[0].is_directory);
        assert_eq!(snapshot.entries[1].relative_path, "README.md");
        assert!(snapshot.truncated);
        assert!(!snapshot
            .entries
            .iter()
            .any(|entry| entry.relative_path.starts_with("outside/")));

        fs::remove_dir_all(root).expect("remove temporary workspace");
    }

    #[test]
    fn file_preview_is_bounded_and_rejects_workspace_escape() {
        let root = fresh_dir();
        fs::create_dir(root.join("src")).expect("create source directory");
        fs::write(root.join("src/main.rs"), "hello world").expect("write source");

        let preview = read_workspace_file_preview(&root, "src/main.rs", 5)
            .expect("read bounded workspace file");
        assert_eq!(preview.relative_path, "src/main.rs");
        assert_eq!(preview.text, "hello");
        assert!(preview.truncated);
        assert!(!preview.binary);

        let error = read_workspace_file_preview(&root, "../outside", 5)
            .expect_err("workspace traversal must fail");
        assert_eq!(error.kind(), std::io::ErrorKind::InvalidInput);

        fs::remove_dir_all(root).expect("remove temporary workspace");
    }

    #[test]
    fn review_projection_includes_staged_diff_and_bounds_output() {
        let root = fresh_dir();
        assert!(Command::new("git")
            .args(["init", "--quiet"])
            .current_dir(&root)
            .status()
            .expect("initialize Git repository")
            .success());
        fs::write(root.join("README.md"), "hello\n".repeat(1_000)).expect("write review file");
        assert!(Command::new("git")
            .args(["add", "--", "README.md"])
            .current_dir(&root)
            .status()
            .expect("stage review file")
            .success());

        let review = inspect_git_review(&root, 1_024).expect("inspect Git review");
        assert!(review.summary.contains("README.md"));
        assert!(review.diff.contains("README.md"));
        assert!(review.truncated);
        assert!(review.summary.len() + review.diff.len() <= 1_024);

        fs::remove_dir_all(root).expect("remove temporary workspace");
    }

    #[cfg(unix)]
    #[test]
    fn review_projection_disables_repository_fsmonitor() {
        let root = fresh_dir();
        assert!(Command::new("git")
            .args(["init", "--quiet"])
            .current_dir(&root)
            .status()
            .expect("initialize Git repository")
            .success());
        let marker = root.join("fsmonitor-ran");
        let monitor = root.join("fsmonitor.sh");
        fs::write(
            &monitor,
            format!("#!/bin/sh\nprintf ran > '{}'\nsleep 2\n", marker.display()),
        )
        .expect("write fsmonitor");
        fs::set_permissions(&monitor, fs::Permissions::from_mode(0o700))
            .expect("make fsmonitor executable");
        assert!(Command::new("git")
            .args(["config", "core.fsmonitor", monitor.to_str().unwrap()])
            .current_dir(&root)
            .status()
            .expect("configure fsmonitor")
            .success());

        let started = Instant::now();
        inspect_git_review(&root, 2_048).expect("inspect Git review");
        assert!(started.elapsed() < Duration::from_secs(1));
        assert!(!marker.exists(), "configured fsmonitor was executed");
        fs::remove_dir_all(root).expect("remove temporary workspace");
    }

    #[cfg(unix)]
    #[test]
    fn bounded_process_enforces_its_deadline() {
        let mut command = Command::new("sh");
        command.args(["-c", "sleep 2"]);
        let started = Instant::now();
        let error = super::run_command_bounded(command, 1_024, Duration::from_millis(50))
            .expect_err("sleeping process should time out");
        assert_eq!(error.kind(), std::io::ErrorKind::TimedOut);
        assert!(started.elapsed() < Duration::from_secs(1));
    }

    #[test]
    fn review_changed_paths_is_bounded_and_deduplicated() {
        let diff = "diff --git a/src/main.rs b/src/main.rs\n@@\n\ndiff --git a/README.md b/README.md\ndiff --git a/src/main.rs b/src/main.rs";
        assert_eq!(review_changed_paths(diff, 10), ["src/main.rs", "README.md"]);
        assert_eq!(review_changed_paths(diff, 1), ["src/main.rs"]);
        assert!(review_changed_paths(diff, 0).is_empty());
    }
}
