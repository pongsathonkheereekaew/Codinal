//! Codinal's native theme tokens — light and dark.
//!
//! Colors are accessed via functions (`color::canvas()`) that read a global
//! dark-mode flag. Call `set_dark_mode(true)` at startup or on toggle.

use std::sync::atomic::{AtomicBool, Ordering};

static DARK_MODE: AtomicBool = AtomicBool::new(false);

pub fn set_dark_mode(dark: bool) {
    DARK_MODE.store(dark, Ordering::Release);
}

pub fn is_dark_mode() -> bool {
    DARK_MODE.load(Ordering::Acquire)
}

#[allow(non_snake_case)]
pub mod color {
    use super::is_dark_mode;

    pub fn canvas() -> u32 {
        if is_dark_mode() {
            0x181818
        } else {
            0xffffff
        }
    }
    pub fn sidebar() -> u32 {
        if is_dark_mode() {
            0x282828
        } else {
            0xfafafa
        }
    }
    pub fn surface() -> u32 {
        if is_dark_mode() {
            0x2d2d2d
        } else {
            0xf2f2f2
        }
    }
    pub fn surface_hover() -> u32 {
        if is_dark_mode() {
            0x383838
        } else {
            0xededed
        }
    }
    pub fn surface_selected() -> u32 {
        if is_dark_mode() {
            0x333333
        } else {
            0xe7e7e7
        }
    }
    pub fn elevated() -> u32 {
        if is_dark_mode() {
            0x2d2d2d
        } else {
            0xffffff
        }
    }
    pub fn border() -> u32 {
        if is_dark_mode() {
            0x333333
        } else {
            0xe6e6e6
        }
    }
    pub fn border_strong() -> u32 {
        if is_dark_mode() {
            0x444444
        } else {
            0xd8d8d8
        }
    }

    pub fn text_primary() -> u32 {
        if is_dark_mode() {
            0xd4d4d4
        } else {
            0x202124
        }
    }
    pub fn text_secondary() -> u32 {
        if is_dark_mode() {
            0x999999
        } else {
            0x686868
        }
    }
    pub fn text_tertiary() -> u32 {
        if is_dark_mode() {
            0x707070
        } else {
            0x989898
        }
    }

    pub fn accent() -> u32 {
        if is_dark_mode() {
            0x509878
        } else {
            0x1677ff
        }
    }
    pub fn accent_muted() -> u32 {
        if is_dark_mode() {
            0x1a3328
        } else {
            0xeaf2ff
        }
    }
    pub fn purple() -> u32 {
        0x8b5cf6
    }
    pub fn success() -> u32 {
        if is_dark_mode() {
            0x3fb950
        } else {
            0x1b8f45
        }
    }
    pub fn warning() -> u32 {
        if is_dark_mode() {
            0xd29922
        } else {
            0xa85600
        }
    }
    pub fn danger() -> u32 {
        if is_dark_mode() {
            0xf85149
        } else {
            0xc9362b
        }
    }
    pub fn danger_muted() -> u32 {
        if is_dark_mode() {
            0x3d1118
        } else {
            0xfeeceb
        }
    }
}

pub mod layout {
    pub const WINDOW_WIDTH: f32 = 1_710.0;
    pub const WINDOW_HEIGHT: f32 = 1_112.0;
    #[cfg(test)]
    pub const GOLDEN_VIEWPORT_WIDTH: f32 = 1_710.0;
    #[cfg(test)]
    pub const GOLDEN_VIEWPORT_HEIGHT: f32 = 1_112.0;
    pub const TOP_BAR_HEIGHT: f32 = 48.0;
    pub const CONTENT_MAX_WIDTH: f32 = 840.0;
    pub const MESSAGE_MAX_WIDTH: f32 = 620.0;
    pub const CONTEXT_WIDTH: f32 = 288.0;
    pub const CONTEXT_MAX_HEIGHT: f32 = 640.0;
    pub const COMPOSER_HEIGHT: f32 = 126.0;
    pub const RESIZE_HIT_WIDTH: f32 = 8.0;

    pub const TYPE_SECTION: f32 = 15.0;
    pub const TYPE_BODY: f32 = 13.0;
    pub const TYPE_CONTROL: f32 = 12.0;
    pub const TYPE_METADATA: f32 = 11.0;
    pub const TYPE_CODE: f32 = 12.0;
}

/// Named semantic type roles. Sizes are taken from the golden fixture: the
/// header title, brand, and sidebar section captions measure ~13 logical px,
/// chat/project rows sit at 11 logical px, and technical content uses SF Mono
/// via `TYPE_CODE`. Keep one role per surface so a token change cannot
/// silently move unrelated text.
pub mod typography {
    /// Header/folder title and brand/mode labels.
    pub const HEADER_TITLE: f32 = 13.0;
    /// Sidebar brand/mode trigger (semibold).
    pub const BRAND_MODE: f32 = 13.0;
    /// Sidebar row labels (chats and projects).
    pub const NAV_LABEL: f32 = 11.0;
    /// Sidebar primary action labels (New chat).
    pub const NAV_ACTION: f32 = 13.0;
    /// Sidebar group captions (Pinned/Projects/Chats).
    pub const NAV_SECTION: f32 = 13.0;
    /// Conversation body and card content.
    pub const BODY: f32 = 13.0;
    /// Card and panel titles (current header size; golden measurement pending
    /// at the capture gate).
    pub const PANEL_TITLE: f32 = 15.0;
    /// Metadata, status, and captions.
    pub const METADATA: f32 = 11.0;
    /// Keyboard shortcut hints.
    pub const SHORTCUT: f32 = 11.0;
    /// Composer input and footer labels.
    pub const COMPOSER: f32 = 13.0;
    /// Code and terminal content (SF Mono).
    pub const CODE: f32 = super::layout::TYPE_CODE;
}

#[cfg(test)]
fn contrast_ratio(foreground: u32, background: u32) -> f32 {
    fn channel(value: u32, shift: u32) -> f32 {
        let encoded = ((value >> shift) & 0xff) as f32 / 255.0;
        if encoded <= 0.04045 {
            encoded / 12.92
        } else {
            ((encoded + 0.055) / 1.055).powf(2.4)
        }
    }

    fn luminance(value: u32) -> f32 {
        0.2126 * channel(value, 16) + 0.7152 * channel(value, 8) + 0.0722 * channel(value, 0)
    }

    let foreground = luminance(foreground);
    let background = luminance(background);
    let lighter = foreground.max(background);
    let darker = foreground.min(background);
    (lighter + 0.05) / (darker + 0.05)
}

#[cfg(test)]
mod tests {
    use super::{color, contrast_ratio, layout};
    use crate::shell_layout::{
        CONTEXT_CARD_RESERVED_WIDTH, CONTEXT_PANEL_INSET, NAVIGATION_DEFAULT_WIDTH,
        WORKBENCH_DEFAULT_WIDTH,
    };

    #[test]
    fn approved_shell_metrics_are_stable() {
        assert_eq!(layout::TOP_BAR_HEIGHT, 48.0);
        assert_eq!(NAVIGATION_DEFAULT_WIDTH, 308.0);
        assert_eq!(layout::CONTENT_MAX_WIDTH, 840.0);
        assert_eq!(layout::CONTEXT_WIDTH, 288.0);
        assert_eq!(
            CONTEXT_CARD_RESERVED_WIDTH,
            layout::CONTEXT_WIDTH + CONTEXT_PANEL_INSET * 2.0
        );
        assert_eq!(WORKBENCH_DEFAULT_WIDTH, 320.0);
        assert_eq!(layout::GOLDEN_VIEWPORT_WIDTH, 1_710.0);
        assert_eq!(layout::GOLDEN_VIEWPORT_HEIGHT, 1_112.0);
    }

    #[test]
    fn codex_semantic_type_scale_is_stable() {
        assert_eq!(layout::TYPE_SECTION, 15.0);
        assert_eq!(layout::TYPE_BODY, 13.0);
        assert_eq!(layout::TYPE_CONTROL, 12.0);
        assert_eq!(layout::TYPE_METADATA, 11.0);
        assert_eq!(layout::TYPE_CODE, 12.0);
    }

    #[test]
    fn approved_light_palette_is_stable() {
        assert_eq!(color::canvas(), 0xffffff);
        assert_eq!(color::sidebar(), 0xfafafa);
        assert_eq!(color::surface(), 0xf2f2f2);
        assert_eq!(color::border(), 0xe6e6e6);
        assert_eq!(color::accent(), 0x1677ff);
    }

    #[test]
    fn light_text_contrast_meets_accessibility_floor() {
        assert!(contrast_ratio(color::text_primary(), color::canvas()) >= 7.0);
        assert!(contrast_ratio(color::text_secondary(), color::canvas()) >= 4.5);
    }
}
