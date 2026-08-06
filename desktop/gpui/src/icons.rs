//! Small monochrome vector icons used by the native shell.
//!
//! The desktop reference uses a compact SF-Symbol-like line language on one
//! optical 16px canvas. Assets stay monochrome and inherit the current color,
//! so GPUI and headless captures use the same asset set.

use std::borrow::Cow;

use gpui::{svg, AssetSource, IntoElement, Result, SharedString, Styled};

#[allow(dead_code)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Icon {
    AddFolder,
    ArrowLeft,
    ArrowRight,
    Bell,
    Browser,
    Bug,
    Check,
    Changes,
    Circle,
    ChevronDown,
    ChevronRight,
    Close,
    Files,
    Folder,
    FolderOpen,
    GitBranch,
    GitCommit,
    Github,
    Globe,
    Hammer,
    Image,
    Laptop,
    Link,
    Menu,
    Mic,
    MessageCircle,
    Model,
    More,
    NewChat,
    Navigation,
    Workbench,
    Permission,
    Pin,
    Plugins,
    Plus,
    PullRequest,
    RefreshCode,
    Review,
    Search,
    Send,
    Sliders,
    SideChat,
    Sites,
    Stop,
    Telescope,
    Terminal,
    Time,
    File,
    Archive,
    ArrowSquareOut,
    Gear,
    Worktree,
    Edit,
}

impl Icon {
    fn path(self) -> &'static str {
        match self {
            Self::AddFolder => "codinal/icons/add-folder.svg",
            Self::ArrowLeft => "codinal/icons/arrow-left.svg",
            Self::ArrowRight => "codinal/icons/arrow-right.svg",
            Self::Bell => "codinal/icons/bell.svg",
            Self::Browser | Self::Globe => "codinal/icons/globe.svg",
            Self::Bug => "codinal/icons/bug.svg",
            Self::Check => "codinal/icons/check.svg",
            Self::Changes => "codinal/icons/changes.svg",
            Self::Circle => "codinal/icons/circle.svg",
            Self::ChevronDown => "codinal/icons/chevron-down.svg",
            Self::ChevronRight => "codinal/icons/chevron-right.svg",
            Self::Close => "codinal/icons/close.svg",
            Self::Files => "codinal/icons/folders.svg",
            Self::Folder => "codinal/icons/folder.svg",
            Self::FolderOpen => "codinal/icons/folder-open.svg",
            Self::GitBranch => "codinal/icons/git-branch.svg",
            Self::GitCommit => "codinal/icons/git-commit.svg",
            Self::Github => "codinal/icons/github.svg",
            Self::Hammer => "codinal/icons/hammer.svg",
            Self::Image => "codinal/icons/image.svg",
            Self::Laptop => "codinal/icons/laptop.svg",
            Self::Link => "codinal/icons/link.svg",
            Self::Menu => "codinal/icons/menu.svg",
            Self::Mic => "codinal/icons/mic.svg",
            Self::MessageCircle => "codinal/icons/message-circle.svg",
            Self::Model => "codinal/icons/model.svg",
            Self::More => "codinal/icons/more.svg",
            Self::NewChat => "codinal/icons/new-chat.svg",
            Self::Navigation => "codinal/icons/navigation.svg",
            Self::Workbench => "codinal/icons/workbench.svg",
            Self::Permission => "codinal/icons/permission.svg",
            Self::Pin => "codinal/icons/pin.svg",
            Self::Plugins => "codinal/icons/plugins.svg",
            Self::Plus => "codinal/icons/plus.svg",
            Self::PullRequest => "codinal/icons/pull-request.svg",
            Self::RefreshCode => "codinal/icons/refresh-code.svg",
            Self::Review => "codinal/icons/review.svg",
            Self::Search => "codinal/icons/search.svg",
            Self::Send => "codinal/icons/send.svg",
            Self::Sliders => "codinal/icons/sliders.svg",
            Self::SideChat => "codinal/icons/side-chat.svg",
            Self::Sites => "codinal/icons/sites.svg",
            Self::Stop => "codinal/icons/stop.svg",
            Self::Telescope => "codinal/icons/telescope.svg",
            Self::Terminal => "codinal/icons/terminal.svg",
            Self::Time => "codinal/icons/time.svg",
            Self::File => "codinal/icons/file.svg",
            Self::Archive => "codinal/icons/archive.svg",
            Self::ArrowSquareOut => "codinal/icons/arrow-square-out.svg",
            Self::Gear => "codinal/icons/gear.svg",
            Self::Worktree => "codinal/icons/worktree.svg",
            Self::Edit => "codinal/icons/edit.svg",
        }
    }
}

/// Per-icon render contract. The golden's row glyphs share one optical family:
/// lucide 24-unit line icons and Codinal 16/20/21-unit fill icons all render
/// their ink between roughly 11.5 and 13 logical px when placed in a 16 px box,
/// except `Changes`, whose ~87%-ink 20-unit canvas needs a smaller box to land
/// in the same optical band. Keep layout boxes (28-32 px hit targets) separate
/// from this rendered size.
#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct IconSpec {
    /// Rendered logical px box for the vector asset.
    pub rendered_size: f32,
    /// Fill vs line geometry, so callers can reason about optical weight.
    pub fill: bool,
}

impl Icon {
    pub(crate) fn spec(self) -> IconSpec {
        let fill = matches!(
            self,
            Self::Changes
                | Self::Folder
                | Self::NewChat
                | Self::Plugins
                | Self::Plus
                | Self::PullRequest
                | Self::Sites
                | Self::Time
        );
        let rendered_size = match self {
            Self::Changes => 15.0,
            _ => 16.0,
        };
        IconSpec {
            rendered_size,
            fill,
        }
    }
}

pub(crate) fn icon(kind: Icon, color: u32) -> impl IntoElement {
    svg()
        .path(kind.path())
        .size(gpui::px(kind.spec().rendered_size))
        .text_color(gpui::rgb(color))
}

#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct CodinalAssets;

impl AssetSource for CodinalAssets {
    fn load(&self, path: &str) -> Result<Option<Cow<'static, [u8]>>> {
        let bytes = match path {
            "codinal/icons/add-folder.svg" => ADD_FOLDER,
            "codinal/icons/arrow-left.svg" => ARROW_LEFT,
            "codinal/icons/arrow-right.svg" => ARROW_RIGHT,
            "codinal/icons/bell.svg" => BELL,
            "codinal/icons/bug.svg" => BUG,
            "codinal/icons/check.svg" => CHECK,
            "codinal/icons/changes.svg" => CHANGES,
            "codinal/icons/circle.svg" => CIRCLE,
            "codinal/icons/chevron-down.svg" => CHEVRON_DOWN,
            "codinal/icons/chevron-right.svg" => CHEVRON_RIGHT,
            "codinal/icons/close.svg" => CLOSE,
            "codinal/icons/folder.svg" => FOLDER,
            "codinal/icons/folder-open.svg" => FOLDER_OPEN,
            "codinal/icons/folders.svg" => FOLDERS,
            "codinal/icons/git-branch.svg" => GIT_BRANCH,
            "codinal/icons/git-commit.svg" => GIT_COMMIT,
            "codinal/icons/github.svg" => GITHUB,
            "codinal/icons/globe.svg" => GLOBE,
            "codinal/icons/hammer.svg" => HAMMER,
            "codinal/icons/image.svg" => IMAGE,
            "codinal/icons/laptop.svg" => LAPTOP,
            "codinal/icons/link.svg" => LINK,
            "codinal/icons/menu.svg" => MENU,
            "codinal/icons/mic.svg" => MIC,
            "codinal/icons/message-circle.svg" => MESSAGE_CIRCLE,
            "codinal/icons/model.svg" => MODEL,
            "codinal/icons/more.svg" => MORE,
            "codinal/icons/new-chat.svg" => NEW_CHAT,
            "codinal/icons/navigation.svg" => NAVIGATION,
            "codinal/icons/workbench.svg" => WORKBENCH,
            "codinal/icons/permission.svg" => PERMISSION,
            "codinal/icons/pin.svg" => PIN,
            "codinal/icons/plugins.svg" => PLUGINS,
            "codinal/icons/plus.svg" => PLUS,
            "codinal/icons/pull-request.svg" => PULL_REQUEST,
            "codinal/icons/refresh-code.svg" => REFRESH_CODE,
            "codinal/icons/review.svg" => REVIEW,
            "codinal/icons/search.svg" => SEARCH,
            "codinal/icons/send.svg" => SEND,
            "codinal/icons/sliders.svg" => SLIDERS,
            "codinal/icons/side-chat.svg" => SIDE_CHAT,
            "codinal/icons/sites.svg" => SITES,
            "codinal/icons/stop.svg" => STOP,
            "codinal/icons/telescope.svg" => TELESCOPE,
            "codinal/icons/terminal.svg" => TERMINAL,
            "codinal/icons/time.svg" => TIME,
            "codinal/icons/file.svg" => FILE,
            "codinal/icons/archive.svg" => ARCHIVE,
            "codinal/icons/arrow-square-out.svg" => ARROW_SQUARE_OUT,
            "codinal/icons/gear.svg" => GEAR,
            "codinal/icons/worktree.svg" => WORKTREE,
            "codinal/icons/edit.svg" => EDIT,
            _ => return Ok(None),
        };
        Ok(Some(Cow::Borrowed(bytes)))
    }

    fn list(&self, _path: &str) -> Result<Vec<SharedString>> {
        Ok(Vec::new())
    }
}

// Sidebar glyphs above use the Codex app's custom optical paths. Utility glyphs
// use the same Lucide stroke geometry as the desktop app and inherit tint from
// the surrounding GPUI element through `currentColor`.
const ADD_FOLDER: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 10v6"/><path d="M9 13h6"/><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>"#;
const ARROW_LEFT: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>"#;
const ARROW_RIGHT: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>"#;
const BELL: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>"#;
const BUG: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 2 1.88 1.88"/><path d="M14.12 3.88 16 2"/><path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/><path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"/><path d="M12 20v-9"/><path d="M6.53 9C4.6 8.8 3 7.1 3 5"/><path d="M6 13H2"/><path d="M3 21c0-2.1 1.7-3.9 3.8-4"/><path d="M20.97 5c0 2.1-1.6 3.8-3.5 4"/><path d="M22 13h-4"/><path d="M17.2 17c2.1.1 3.8 1.9 3.8 4"/></svg>"#;
const CHECK: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>"#;
const CHANGES: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 20 20"><path d="M12.084 12.668a.666.666 0 0 1 0 1.33H7.917a.665.665 0 1 1 0-1.33h4.167ZM10 5.585c.367 0 .665.298.665.665v1.418h1.419a.666.666 0 0 1 0 1.33h-1.419v1.419a.666.666 0 0 1-1.33 0V8.998H7.917a.665.665 0 0 1 0-1.33h1.418V6.25c0-.367.298-.665.665-.665Z"/><path fill-rule="evenodd" d="M12.667 2.668c.689 0 1.246 0 1.696.036.458.038.865.117 1.242.309a3.163 3.163 0 0 1 1.382 1.383c.192.377.272.783.309 1.24.037.45.036 1.008.036 1.697v5.333c0 .689 0 1.246-.036 1.696-.037.458-.117.865-.309 1.242a3.166 3.166 0 0 1-1.382 1.382c-.377.192-.784.271-1.242.309-.45.037-1.007.036-1.696.036H7.334c-.689 0-1.246 0-1.696-.036-.458-.038-.864-.117-1.24-.309a3.166 3.166 0 0 1-1.384-1.383c-.192-.376-.271-.783-.309-1.24-.037-.45-.036-1.008-.036-1.697V7.333c0-.689 0-1.246.036-1.696.038-.458.117-.864.309-1.24a3.17 3.17 0 0 1 1.383-1.384c.377-.192.783-.272 1.24-.309.45-.037 1.008-.036 1.697-.036h5.333Zm-5.333 1.33c-.71 0-1.204.001-1.588.032-.375.03-.587.088-.745.168A1.836 1.836 0 0 0 4.199 5c-.08.158-.137.37-.168.745C4 6.13 4 6.622 4 7.333v5.333c0 .71.001 1.204.032 1.588.03.375.088.587.168.745.176.345.457.627.802.803.158.08.37.137.745.168.384.031.877.031 1.588.031h5.333c.71 0 1.204 0 1.588-.031.375-.031.587-.088.745-.168a1.84 1.84 0 0 0 .803-.803c.08-.158.137-.37.168-.745.031-.383.031-.877.031-1.588V7.333c0-.71 0-1.204-.031-1.588-.031-.375-.088-.587-.168-.745A1.838 1.838 0 0 0 15 4.198c-.158-.08-.37-.137-.745-.168-.384-.031-.877-.032-1.588-.032H7.334Z" clip-rule="evenodd"/></svg>"#;
const CIRCLE: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg>"#;
const CHEVRON_DOWN: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>"#;
const CHEVRON_RIGHT: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>"#;
const CLOSE: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>"#;
const FOLDER: &[u8] = br#"<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="none"><path fill-rule="evenodd" clip-rule="evenodd" d="M5.36914 2.1416C5.92368 2.14164 6.3602 2.23705 6.73242 2.38965C7.09745 2.53934 7.38155 2.73818 7.61816 2.9043C8.07599 3.22573 8.42077 3.47464 9.16602 3.47461H11.9473C13.3336 3.47484 14.4453 4.61217 14.4453 6V7.06543C14.4453 7.07196 14.4435 7.07845 14.4434 7.08496V11.3311C14.4432 12.7187 13.3316 13.8562 11.9453 13.8564H4.05371C2.66747 13.8562 1.55583 12.7187 1.55566 11.3311V7.35059C1.55545 7.34451 1.55377 7.33815 1.55371 7.33203C1.55371 7.32563 1.55539 7.31884 1.55566 7.3125V4.66699C1.55566 3.27918 2.66737 2.14185 4.05371 2.1416H5.36914ZM2.60547 7.85645V11.3311C2.60563 12.1519 3.26037 12.8054 4.05371 12.8057H11.9453C12.7387 12.8054 13.3934 12.1519 13.3936 11.3311V7.85645H2.60547ZM4.05371 3.19238C3.26027 3.19264 2.60547 3.84598 2.60547 4.66699V6.80664H13.3955V6C13.3955 5.17898 12.7407 4.52562 11.9473 4.52539H9.16699C8.07975 4.52558 7.50694 4.10863 7.01562 3.76367C6.77766 3.5966 6.57849 3.46159 6.33398 3.36133C6.09656 3.264 5.79646 3.19242 5.36914 3.19238H4.05371Z" fill="currentColor"/></svg>"#;
const FOLDER_OPEN: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/></svg>"#;
const FOLDERS: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 17a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3.9a2 2 0 0 1-1.69-.9l-.81-1.2a2 2 0 0 0-1.67-.9H8a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2Z"/><path d="M2 8v11a2 2 0 0 0 2 2h14"/></svg>"#;
const GIT_BRANCH: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" x2="6" y1="3" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>"#;
const GIT_COMMIT: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><line x1="3" x2="9" y1="12" y2="12"/><line x1="15" x2="21" y1="12" y2="12"/></svg>"#;
const GITHUB: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/></svg>"#;
const GLOBE: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>"#;
const HAMMER: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 12-8.373 8.373a1 1 0 1 1-3-3L12 9"/><path d="m18 15 4-4"/><path d="m21.5 11.5-1.914-1.914A2 2 0 0 1 19 8.172V7l-2.26-2.26a6 6 0 0 0-4.202-1.756L9 2.96l.92.82A6.18 6.18 0 0 1 12 8.4V10l2 2h1.172a2 2 0 0 1 1.414.586L18.5 14.5"/></svg>"#;
const MENU: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/></svg>"#;
const MIC: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>"#;
const MESSAGE_CIRCLE: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>"#;
const MODEL: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/></svg>"#;
const MORE: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>"#;
const NEW_CHAT: &[u8] = br#"<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9.33496 16.5V10.665H3.5C3.13273 10.665 2.83496 10.3673 2.83496 10C2.83496 9.63273 3.13273 9.33496 3.5 9.33496H9.33496V3.5C9.33496 3.13273 9.63273 2.83496 10 2.83496C10.3673 2.83496 10.665 3.13273 10.665 3.5V9.33496H16.5L16.6338 9.34863C16.9369 9.41057 17.165 9.67857 17.165 10C17.165 10.3214 16.9369 10.5894 16.6338 10.6514L16.5 10.665H10.665V16.5C10.665 16.8673 10.3673 17.165 10 17.165C9.63273 17.165 9.33496 16.8673 9.33496 16.5Z" fill="currentColor"/></svg>"#;
const NAVIGATION: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/></svg>"#;
const WORKBENCH: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M15 3v18"/></svg>"#;
const PERMISSION: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>"#;
const PIN: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>"#;
const PLUGINS: &[u8] = br#"<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="none"><path fill-rule="evenodd" clip-rule="evenodd" d="M8.25031 1.46094C12.2175 1.46116 14.7053 4.56317 14.4573 8.11328C14.3646 9.44154 13.6395 10.4315 12.6556 10.834C11.7842 11.1903 10.7744 11.0568 9.95637 10.3848C9.43406 10.8255 8.8274 11.1141 8.19465 11.167C7.46206 11.2281 6.74478 10.9691 6.16535 10.3672L6.16145 10.3623C6.16145 10.3623 6.15859 10.3586 6.15656 10.3564C6.15204 10.3517 6.14556 10.344 6.13703 10.335C6.11976 10.3167 6.09427 10.29 6.06281 10.2568C5.9996 10.1901 5.90986 10.0966 5.80793 9.98926C5.60368 9.77412 5.34664 9.50307 5.1341 9.28125C4.86457 8.99958 4.87183 8.55158 5.15363 8.28027L5.31672 8.12207L4.72004 7.50195C4.5193 7.29309 4.52604 6.96077 4.73469 6.75977C4.94359 6.55869 5.27678 6.56454 5.47785 6.77344L6.07453 7.39355L7.51789 6.00391L6.92121 5.38379C6.72021 5.17497 6.72621 4.8427 6.93488 4.6416C7.14378 4.44052 7.47697 4.44638 7.67805 4.65527L8.27473 5.27539L8.44465 5.1123C8.72754 4.84001 9.17872 4.85048 9.44953 5.13477L10.4808 6.21777C11.074 6.8285 11.3084 7.55474 11.2132 8.28613C11.1518 8.75707 10.9544 9.20384 10.6683 9.60938C11.1897 10.0141 11.7752 10.0597 12.2581 9.8623C12.8307 9.6281 13.3423 9.01591 13.4105 8.04004C13.6191 5.05211 11.5645 2.51194 8.25031 2.51172C5.3194 2.51172 2.78634 4.7507 2.58918 7.57031C2.36888 10.7251 4.6005 13.3876 7.99836 13.3877C9.02878 13.3877 10.0514 13.1687 10.8314 12.7041C11.0805 12.5558 11.4027 12.6377 11.5511 12.8867C11.6992 13.1357 11.6174 13.4581 11.3685 13.6064C10.3813 14.1943 9.15795 14.4375 7.99836 14.4375C3.956 14.4374 1.28142 11.2234 1.54133 7.49805C1.77976 4.08387 4.81315 1.46094 8.25031 1.46094ZM6.12727 8.80176C6.27942 8.9613 6.43614 9.12597 6.56965 9.2666C6.67197 9.37438 6.76112 9.46823 6.82453 9.53516C6.856 9.56836 6.88138 9.59493 6.89875 9.61328L6.9261 9.6416C7.2937 10.0219 7.7023 10.154 8.10774 10.1201C8.52986 10.0848 8.998 9.86387 9.43293 9.44531C9.87269 9.02201 10.1181 8.56488 10.1722 8.14941C10.2235 7.75361 10.1099 7.34127 9.72492 6.94629L9.72102 6.94238L8.9261 6.10742L6.12727 8.80176Z" fill="currentColor"/></svg>"#;
const PLUS: &[u8] = br#"<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9.33496 16.5V10.665H3.5C3.13273 10.665 2.83496 10.3673 2.83496 10C2.83496 9.63273 3.13273 9.33496 3.5 9.33496H9.33496V3.5C9.33496 3.13273 9.63273 2.83496 10 2.83496C10.3673 2.83496 10.665 3.13273 10.665 3.5V9.33496H16.5L16.6338 9.34863C16.9369 9.41057 17.165 9.67857 17.165 10C17.165 10.3214 16.9369 10.5894 16.6338 10.6514L16.5 10.665H10.665V16.5C10.665 16.8673 10.3673 17.165 10 17.165C9.63273 17.165 9.33496 16.8673 9.33496 16.5Z" fill="currentColor"/></svg>"#;
const PULL_REQUEST: &[u8] = br#"<svg viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg" fill="currentColor"><path d="M6.12695 15.4998C6.12695 14.8315 5.58526 14.2898 4.91699 14.2898C4.24873 14.2898 3.70703 14.8315 3.70703 15.4998C3.70703 16.168 4.24873 16.7097 4.91699 16.7097C5.58526 16.7097 6.12695 16.168 6.12695 15.4998ZM16.96 5.49976C16.96 4.83149 16.4183 4.28979 15.75 4.28979C15.0819 4.28997 14.54 4.8316 14.54 5.49976C14.54 6.16791 15.0819 6.70954 15.75 6.70972C16.4183 6.70972 16.96 6.16802 16.96 5.49976ZM7.45703 15.4998C7.45703 16.9026 6.3198 18.0398 4.91699 18.0398C3.51419 18.0398 2.37695 16.9026 2.37695 15.4998C2.37695 14.3273 3.17207 13.3431 4.25195 13.0505V7.16675C4.25195 5.879 5.29624 4.83472 6.58398 4.83472H8.72754L8.19629 4.30347L8.11133 4.19897C7.94107 3.94099 7.96939 3.59025 8.19629 3.36304C8.42365 3.13568 8.77504 3.10735 9.0332 3.27808L9.1377 3.36304L10.8037 5.02905C11.0634 5.28875 11.0634 5.71076 10.8037 5.97046L9.1377 7.63647L9.0332 7.72144C8.77504 7.89216 8.42365 7.86383 8.19629 7.63647C7.93697 7.3768 7.93686 6.95565 8.19629 6.69604L8.72754 6.16479H6.58398C6.03078 6.16479 5.58203 6.61354 5.58203 7.16675V13.0505C6.66191 13.3431 7.45703 14.3273 7.45703 15.4998ZM18.29 5.49976C18.29 6.67221 17.4949 7.6555 16.415 7.948V13.8328C16.415 15.1204 15.3716 16.1646 14.084 16.1648H11.9395L12.4707 16.696L12.5557 16.8005C12.7261 17.0586 12.6978 17.4092 12.4707 17.6365C12.2435 17.8637 11.8929 17.8918 11.6348 17.7214L11.5303 17.6365L9.86328 15.9705C9.73857 15.8457 9.66895 15.6761 9.66895 15.4998C9.66895 15.3234 9.73857 15.1538 9.86328 15.0291L11.5303 13.363C11.79 13.1033 12.211 13.1033 12.4707 13.363C12.7302 13.6227 12.7303 14.0438 12.4707 14.3035L11.9395 14.8347H14.084C14.637 14.8345 15.085 14.3859 15.085 13.8328V7.948C14.0054 7.65529 13.21 6.67199 13.21 5.49976C13.21 4.09706 14.3473 2.95989 15.75 2.95972C17.1528 2.95972 18.29 4.09695 18.29 5.49976Z"/></svg>"#;
const REFRESH_CODE: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>"#;
const REVIEW: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M8 12h8"/><path d="M12 8v8"/></svg>"#;
const SEARCH: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>"#;
const SEND: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>"#;
const SLIDERS: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/><line x1="4" x2="20" y1="12" y2="12"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="18" r="2"/></svg>"#;
const SIDE_CHAT: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9a2 2 0 0 1-2 2H6l-4 4V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2z"/><path d="M18 9h2a2 2 0 0 1 2 2v11l-4-4h-6a2 2 0 0 1-2-2v-1"/></svg>"#;
const SITES: &[u8] = br#"<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="none"><path fill-rule="evenodd" clip-rule="evenodd" d="M4.33301 10.1416C5.17524 10.1416 5.8584 10.8248 5.8584 11.667V13C5.8584 13.8422 5.17524 14.5254 4.33301 14.5254H3C2.15792 14.5252 1.47461 13.8421 1.47461 13V11.667C1.47461 10.8249 2.15792 10.1418 3 10.1416H4.33301ZM3 11.1914C2.73782 11.1916 2.52441 11.4048 2.52441 11.667V13C2.52441 13.2622 2.73782 13.4744 3 13.4746H4.33301C4.59534 13.4746 4.80762 13.2623 4.80762 13V11.667C4.80762 11.4047 4.59534 11.1914 4.33301 11.1914H3Z" fill="currentColor"/><path fill-rule="evenodd" clip-rule="evenodd" d="M6.75 1.47461C7.73031 1.47461 8.52539 2.26969 8.52539 3.25V7.47461H12.75C13.7303 7.47461 14.5254 8.26969 14.5254 9.25V12.75C14.5254 13.7303 13.7303 14.5254 12.75 14.5254H9.25C8.26969 14.5254 7.47461 13.7303 7.47461 12.75V8.52539H3.25C2.26969 8.52539 1.47461 7.73031 1.47461 6.75V3.25C1.47461 2.26969 2.26969 1.47461 3.25 1.47461H6.75ZM8.52539 12.75C8.52539 13.1504 8.84959 13.4746 9.25 13.4746H12.75C13.1504 13.4746 13.4746 13.1504 13.4746 12.75V9.25C13.4746 8.84959 13.1504 8.52539 12.75 8.52539H8.52539V12.75ZM3.25 2.52539C2.84959 2.52539 2.52539 2.84959 2.52539 3.25V6.75C2.52539 7.15041 2.84959 7.47461 3.25 7.47461H7.47461V3.25C7.47461 2.84959 7.15041 2.52539 6.75 2.52539H3.25Z" fill="currentColor"/><path fill-rule="evenodd" clip-rule="evenodd" d="M13 1.47461C13.8421 1.47479 14.5254 2.15788 14.5254 3V4.33301C14.5254 5.17513 13.8421 5.85822 13 5.8584H11.667C10.8248 5.8584 10.1416 5.17524 10.1416 4.33301V3C10.1416 2.15777 10.8248 1.47461 11.667 1.47461H13ZM11.667 2.52539C11.4047 2.52539 11.1924 2.73767 11.1924 3V4.33301C11.1924 4.59534 11.4047 4.80859 11.667 4.80859H13C13.2622 4.80841 13.4756 4.59523 13.4756 4.33301V3C13.4756 2.73778 13.2622 2.52557 13 2.52539H11.667Z" fill="currentColor"/></svg>"#;
const STOP: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/></svg>"#;
const TELESCOPE: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m10.065 12.493-6.18 1.318a.934.934 0 0 1-1.108-.702l-.537-2.15a1.07 1.07 0 0 1 .691-1.265l13.504-4.44"/><path d="m13.56 11.747 4.332-.924"/><path d="m16 21-3.105-6.21"/><path d="M16.485 5.94a2 2 0 0 1 1.455-2.425l1.09-.272a1 1 0 0 1 1.212.727l1.515 6.06a1 1 0 0 1-.727 1.213l-1.09.272a2 2 0 0 1-2.425-1.455z"/><path d="m6.158 8.633 1.114 4.456"/><path d="m8 21 3.105-6.21"/><circle cx="12" cy="13" r="2"/></svg>"#;
const TERMINAL: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7 11 2-2-2-2"/><path d="M11 13h4"/><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/></svg>"#;
const TIME: &[u8] = br#"<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="none"><path d="M8 4.2168C8.24838 4.21697 8.44922 4.41857 8.44922 4.66699V7.8623C8.44911 8.06977 8.36732 8.26924 8.2207 8.41602L6.65137 9.98535C6.4756 10.1607 6.19025 10.161 6.01465 9.98535C5.83909 9.80975 5.83934 9.52439 6.01465 9.34863L7.5498 7.81348V4.66699C7.5498 4.41862 7.75168 4.21704 8 4.2168Z" fill="currentColor"/><path fill-rule="evenodd" clip-rule="evenodd" d="M8 1.5498C11.5622 1.5498 14.4502 4.43776 14.4502 8C14.4502 11.5622 11.5622 14.4502 8 14.4502C4.43776 14.4502 1.5498 11.5622 1.5498 8C1.5498 4.43776 4.43776 1.5498 8 1.5498ZM8 2.4502C4.93482 2.4502 2.4502 4.93482 2.4502 8C2.4502 11.0652 4.93482 13.5498 8 13.5498C11.0652 13.5498 13.5498 11.0652 13.5498 8C13.5498 4.93482 11.0652 2.4502 8 2.4502Z" fill="currentColor"/></svg>"#;
const IMAGE: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>"#;
const LAPTOP: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 16V7a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v9m16 0H4m16 0 1.28 2.55a1 1 0 0 1-.9 1.45H3.62a1 1 0 0 1-.9-1.45L4 16"/></svg>"#;
const LINK: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" x2="15.42" y1="13.51" y2="17.49"/><line x1="15.41" x2="8.59" y1="6.51" y2="10.49"/></svg>"#;
const FILE: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>"#;
const ARCHIVE: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/></svg>"#;
const ARROW_SQUARE_OUT: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>"#;
const GEAR: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>"#;
const WORKTREE: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" x2="14" y1="3" y2="10"/><line x1="3" x2="10" y1="21" y2="14"/></svg>"#;
const EDIT: &[u8] = br#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>"#;

#[cfg(test)]
mod tests {
    use super::{CodinalAssets, Icon, IconSpec};
    use gpui::AssetSource;

    #[test]
    fn every_icon_has_a_loadable_vector_asset() {
        let assets = CodinalAssets;
        let icons = [
            Icon::AddFolder,
            Icon::ArrowLeft,
            Icon::ArrowRight,
            Icon::Bell,
            Icon::Browser,
            Icon::Bug,
            Icon::Check,
            Icon::Changes,
            Icon::Circle,
            Icon::ChevronDown,
            Icon::ChevronRight,
            Icon::Close,
            Icon::Files,
            Icon::Folder,
            Icon::FolderOpen,
            Icon::GitBranch,
            Icon::GitCommit,
            Icon::Github,
            Icon::Globe,
            Icon::Hammer,
            Icon::Image,
            Icon::Laptop,
            Icon::Link,
            Icon::Menu,
            Icon::Mic,
            Icon::MessageCircle,
            Icon::Model,
            Icon::More,
            Icon::NewChat,
            Icon::Navigation,
            Icon::Workbench,
            Icon::Permission,
            Icon::Pin,
            Icon::Plugins,
            Icon::Plus,
            Icon::PullRequest,
            Icon::RefreshCode,
            Icon::Review,
            Icon::Search,
            Icon::Send,
            Icon::Sliders,
            Icon::SideChat,
            Icon::Sites,
            Icon::Stop,
            Icon::Telescope,
            Icon::Terminal,
            Icon::Time,
            Icon::File,
            Icon::Archive,
            Icon::ArrowSquareOut,
            Icon::Gear,
            Icon::Worktree,
            Icon::Edit,
        ];
        for icon in icons {
            let path = icon.path();
            let loaded = assets.load(path).expect("asset load");
            let bytes = loaded.expect("missing vector asset");
            let svg = std::str::from_utf8(&bytes).expect("vector asset is UTF-8");
            assert!(
                svg.contains("viewBox=\"0 0 16 16\"")
                    || svg.contains("viewBox=\"0 0 21 21\"")
                    || svg.contains("viewBox=\"0 0 20 20\"")
                    || svg.contains("viewBox=\"0 0 24 24\"")
                    || svg.contains("viewBox=\"0 0 256 256\""),
                "unsupported icon canvas: {path}"
            );
            assert!(
                svg.contains("currentColor"),
                "asset is not tintable: {path}"
            );
            assert!(
                !svg.contains("stroke=\"black\"") && !svg.contains("fill=\"black\""),
                "hard-coded black asset: {path}"
            );
        }
    }

    #[test]
    fn icon_specs_match_the_asset_geometry_and_optical_band() {
        let assets = CodinalAssets;
        for icon in [
            Icon::AddFolder,
            Icon::ArrowLeft,
            Icon::ArrowRight,
            Icon::Bell,
            Icon::Browser,
            Icon::Bug,
            Icon::Check,
            Icon::Changes,
            Icon::Circle,
            Icon::ChevronDown,
            Icon::ChevronRight,
            Icon::Close,
            Icon::Files,
            Icon::Folder,
            Icon::FolderOpen,
            Icon::GitBranch,
            Icon::GitCommit,
            Icon::Github,
            Icon::Globe,
            Icon::Hammer,
            Icon::Image,
            Icon::Laptop,
            Icon::Link,
            Icon::Menu,
            Icon::Mic,
            Icon::MessageCircle,
            Icon::Model,
            Icon::More,
            Icon::NewChat,
            Icon::Navigation,
            Icon::Workbench,
            Icon::Permission,
            Icon::Pin,
            Icon::Plugins,
            Icon::Plus,
            Icon::PullRequest,
            Icon::RefreshCode,
            Icon::Review,
            Icon::Search,
            Icon::Send,
            Icon::Sliders,
            Icon::SideChat,
            Icon::Sites,
            Icon::Stop,
            Icon::Telescope,
            Icon::Terminal,
            Icon::Time,
            Icon::File,
            Icon::Archive,
            Icon::ArrowSquareOut,
            Icon::Gear,
            Icon::Worktree,
            Icon::Edit,
        ] {
            let spec: IconSpec = icon.spec();
            let bytes = assets
                .load(icon.path())
                .expect("asset load")
                .expect("missing vector asset");
            let svg = std::str::from_utf8(&bytes).expect("vector asset is UTF-8");
            let is_fill = svg.contains("fill=\"currentColor\"");
            assert_eq!(
                spec.fill, is_fill,
                "spec fill flag disagrees with asset: {:?}",
                icon
            );
            assert!(
                (11.0..=16.0).contains(&spec.rendered_size),
                "rendered size out of the 16 px optical family: {:?}",
                icon
            );
        }
        assert_eq!(Icon::Changes.spec().rendered_size, 15.0);
    }
}
