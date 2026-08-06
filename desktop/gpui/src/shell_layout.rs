//! Pure layout contract for Codinal's native conversation workbench.

use crate::light_theme::layout::CONTEXT_WIDTH;
use std::fs::{self, File};
use std::io::{self, Write};
use std::path::Path;
use std::time::{Duration, Instant};

pub const NAVIGATION_DEFAULT_WIDTH: f32 = 308.0;
pub const NAVIGATION_MIN_WIDTH: f32 = 220.0;
pub const NAVIGATION_MAX_WIDTH: f32 = 420.0;
pub const WORKBENCH_DEFAULT_WIDTH: f32 = 320.0;
pub const WORKBENCH_MIN_WIDTH: f32 = 300.0;
pub const WORKBENCH_MAX_WIDTH: f32 = 640.0;
pub const FILE_TREE_DEFAULT_WIDTH: f32 = 120.0;
pub const FILE_TREE_MIN_WIDTH: f32 = 120.0;
pub const FILE_TREE_MAX_WIDTH: f32 = 320.0;
pub const FILE_DETAIL_MIN_WIDTH: f32 = 160.0;
pub const CONVERSATION_MIN_WIDTH: f32 = 560.0;
pub const CONTEXT_CARD_RESERVED_WIDTH: f32 = 320.0;
pub const CONTEXT_PANEL_INSET: f32 = 16.0;
pub const OVERLAY_HORIZONTAL_MARGIN: f32 = 16.0;

#[allow(dead_code)]
pub const SEAM_SLIDE: Duration = Duration::from_millis(260);

/// Evaluates whether a panel toggle shortcut should be honored.
/// Drops key-repeat toggles arriving mid-slide (<260ms) to prevent stutter.
pub fn toggle_has_settled(since_last: Option<Duration>) -> bool {
    since_last.is_none_or(|since| since >= SEAM_SLIDE)
}

/// Advances one panel's seam by a frame and returns the width to paint,
/// clearing the slide once it lands. An unfinished slide asks for the next
/// frame itself: the seam is a plain animated width rather than a GPUI
/// animation element, so nothing else will tick the window.
pub fn advance_seam(
    slide: &mut Option<SeamSlide>,
    settled: f32,
    now: Instant,
    window: &gpui::Window,
) -> f32 {
    match *slide {
        Some(active) if !active.is_done(now) => {
            window.request_animation_frame();
            active.seam_at(settled, now)
        }
        Some(_) => {
            *slide = None;
            settled
        }
        None => settled,
    }
}

/// A critically damped spring step response (0.0..=1.0).
/// Front-loads travel (>80% distance at t=0.5) and lands softly with zero overshoot,
/// preventing flex-sibling layout oscillation stutter.
pub fn spring_settle(delta: f32) -> f32 {
    const STIFFNESS: f32 = 7.0;
    let remaining = |t: f32| (1.0 + STIFFNESS * t) * (-STIFFNESS * t).exp();
    ((1.0 - remaining(delta.clamp(0.0, 1.0))) / (1.0 - remaining(1.0))).clamp(0.0, 1.0)
}

/// Motion tracker for panel open/close seam slide.
#[derive(Clone, Copy, Debug)]
pub struct SeamSlide {
    from: f32,
    started_at: Instant,
}

#[allow(dead_code)]
impl SeamSlide {
    pub fn begin(from: f32, to: f32) -> Option<Self> {
        (from != to).then(|| Self {
            from,
            started_at: Instant::now(),
        })
    }

    pub fn progress(&self, now: Instant) -> f32 {
        (now.duration_since(self.started_at).as_secs_f32() / SEAM_SLIDE.as_secs_f32())
            .clamp(0.0, 1.0)
    }

    pub fn is_done(&self, now: Instant) -> bool {
        self.progress(now) >= 1.0
    }

    pub fn seam_at(&self, to: f32, now: Instant) -> f32 {
        self.from + (to - self.from) * spring_settle(self.progress(now))
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WorkbenchPlacement {
    Hidden,
    Docked,
    Overlay,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PanelResizeTarget {
    Navigation,
    Workbench,
    FileTree,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PanelPreferences {
    pub navigation_width: f32,
    pub workbench_width: f32,
    pub file_tree_width: f32,
}

impl Default for PanelPreferences {
    fn default() -> Self {
        Self {
            navigation_width: NAVIGATION_DEFAULT_WIDTH,
            workbench_width: WORKBENCH_DEFAULT_WIDTH,
            file_tree_width: FILE_TREE_DEFAULT_WIDTH,
        }
    }
}

pub fn resize_panel_preferences(
    mut preferences: PanelPreferences,
    target: PanelResizeTarget,
    pointer_x: f32,
    far_edge_x: f32,
) -> PanelPreferences {
    match target {
        PanelResizeTarget::Navigation => {
            preferences.navigation_width =
                pointer_x.clamp(NAVIGATION_MIN_WIDTH, NAVIGATION_MAX_WIDTH);
        }
        PanelResizeTarget::Workbench => {
            preferences.workbench_width =
                (far_edge_x - pointer_x).clamp(WORKBENCH_MIN_WIDTH, WORKBENCH_MAX_WIDTH);
        }
        PanelResizeTarget::FileTree => {
            preferences.file_tree_width =
                (far_edge_x - pointer_x).clamp(FILE_TREE_MIN_WIDTH, FILE_TREE_MAX_WIDTH);
        }
    }
    preferences
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ShellRequest {
    pub viewport_width: f32,
    pub navigation_open: bool,
    pub workbench_open: bool,
    pub context_open: bool,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ResolvedShell {
    pub navigation_width: f32,
    pub workbench_width: f32,
    pub file_tree_width: f32,
    pub workbench_placement: WorkbenchPlacement,
    pub conversation_width: f32,
    pub context_width: f32,
    pub context_right: f32,
}

pub fn resolve_shell(preferences: PanelPreferences, request: ShellRequest) -> ResolvedShell {
    let viewport_width = request.viewport_width.max(0.0);
    let conversation_required_width = CONVERSATION_MIN_WIDTH
        + if request.context_open {
            CONTEXT_CARD_RESERVED_WIDTH
        } else {
            0.0
        };
    let navigation_width = if request.navigation_open {
        preferences
            .navigation_width
            .clamp(NAVIGATION_MIN_WIDTH, NAVIGATION_MAX_WIDTH)
    } else {
        0.0
    };
    let configured_workbench_width = preferences
        .workbench_width
        .clamp(WORKBENCH_MIN_WIDTH, WORKBENCH_MAX_WIDTH);
    let preferred_workbench_width = if request.workbench_open {
        configured_workbench_width
    } else {
        0.0
    };
    let workbench_placement = if !request.workbench_open {
        WorkbenchPlacement::Hidden
    } else if viewport_width - navigation_width - preferred_workbench_width
        >= conversation_required_width
    {
        WorkbenchPlacement::Docked
    } else {
        WorkbenchPlacement::Overlay
    };
    let workbench_width = match workbench_placement {
        WorkbenchPlacement::Hidden => 0.0,
        WorkbenchPlacement::Docked => preferred_workbench_width,
        WorkbenchPlacement::Overlay => preferred_workbench_width
            .min((viewport_width - navigation_width - OVERLAY_HORIZONTAL_MARGIN * 2.0).max(0.0)),
    };
    let conversation_width = match workbench_placement {
        WorkbenchPlacement::Docked => viewport_width - navigation_width - workbench_width,
        WorkbenchPlacement::Hidden | WorkbenchPlacement::Overlay => {
            viewport_width - navigation_width
        }
    }
    .max(0.0);
    let file_tree_container_width = if request.workbench_open {
        workbench_width
    } else {
        configured_workbench_width
    };
    let effective_file_tree_max = FILE_TREE_MAX_WIDTH
        .min((file_tree_container_width - FILE_DETAIL_MIN_WIDTH).max(FILE_TREE_MIN_WIDTH));
    let context_right = CONTEXT_PANEL_INSET
        + if workbench_placement == WorkbenchPlacement::Overlay {
            workbench_width
        } else {
            0.0
        };
    let context_width = if request.context_open {
        CONTEXT_WIDTH.min((conversation_width - context_right - CONTEXT_PANEL_INSET).max(0.0))
    } else {
        0.0
    };
    ResolvedShell {
        navigation_width,
        workbench_width,
        file_tree_width: preferences
            .file_tree_width
            .clamp(FILE_TREE_MIN_WIDTH, effective_file_tree_max),
        workbench_placement,
        conversation_width,
        context_width,
        context_right,
    }
}

pub fn load_panel_preferences(path: &Path) -> io::Result<PanelPreferences> {
    let bytes = match fs::read(path) {
        Ok(bytes) => bytes,
        Err(error) if error.kind() == io::ErrorKind::NotFound => {
            return Ok(PanelPreferences::default());
        }
        Err(error) => return Err(error),
    };
    let value: serde_json::Value = match serde_json::from_slice(&bytes) {
        Ok(value) => value,
        Err(_) => return Ok(PanelPreferences::default()),
    };
    let defaults = PanelPreferences::default();
    let width = |name: &str, fallback: f32, minimum: f32, maximum: f32| {
        value
            .get(name)
            .and_then(serde_json::Value::as_f64)
            .map(|value| value as f32)
            .filter(|value| value.is_finite())
            .unwrap_or(fallback)
            .clamp(minimum, maximum)
    };
    Ok(PanelPreferences {
        navigation_width: width(
            "navigation_width",
            defaults.navigation_width,
            NAVIGATION_MIN_WIDTH,
            NAVIGATION_MAX_WIDTH,
        ),
        workbench_width: width(
            "workbench_width",
            defaults.workbench_width,
            WORKBENCH_MIN_WIDTH,
            WORKBENCH_MAX_WIDTH,
        ),
        file_tree_width: width(
            "file_tree_width",
            defaults.file_tree_width,
            FILE_TREE_MIN_WIDTH,
            FILE_TREE_MAX_WIDTH,
        ),
    })
}

pub fn save_panel_preferences(path: &Path, preferences: PanelPreferences) -> io::Result<()> {
    let parent = path.parent().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "panel preference path requires a parent directory",
        )
    })?;
    fs::create_dir_all(parent)?;
    let temporary = path.with_extension("json.tmp");
    let payload = serde_json::to_vec_pretty(&serde_json::json!({
        "version": 1,
        "navigation_width": preferences.navigation_width.clamp(
            NAVIGATION_MIN_WIDTH,
            NAVIGATION_MAX_WIDTH,
        ),
        "workbench_width": preferences.workbench_width.clamp(
            WORKBENCH_MIN_WIDTH,
            WORKBENCH_MAX_WIDTH,
        ),
        "file_tree_width": preferences.file_tree_width.clamp(
            FILE_TREE_MIN_WIDTH,
            FILE_TREE_MAX_WIDTH,
        ),
    }))
    .map_err(io::Error::other)?;
    let write_result = (|| {
        let mut file = File::create(&temporary)?;
        file.write_all(&payload)?;
        file.sync_all()?;
        fs::rename(&temporary, path)
    })();
    if write_result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    write_result
}

#[cfg(test)]
mod tests {
    use super::{
        load_panel_preferences, resize_panel_preferences, resolve_shell, save_panel_preferences,
        PanelPreferences, PanelResizeTarget, ShellRequest,
    };
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temporary_preferences_path() -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        std::env::temp_dir().join(format!(
            "codinal-panel-preferences-{}-{unique}.json",
            std::process::id()
        ))
    }

    #[test]
    fn hidden_navigation_preserves_the_preferred_visible_width() {
        let preferences = PanelPreferences {
            navigation_width: 360.0,
            ..PanelPreferences::default()
        };

        let hidden = resolve_shell(
            preferences,
            ShellRequest {
                viewport_width: 1_440.0,
                navigation_open: false,
                workbench_open: false,
                context_open: false,
            },
        );
        assert_eq!(hidden.navigation_width, 0.0);

        let restored = resolve_shell(
            preferences,
            ShellRequest {
                viewport_width: 1_440.0,
                navigation_open: true,
                workbench_open: false,
                context_open: false,
            },
        );
        assert_eq!(restored.navigation_width, 360.0);
    }

    #[test]
    fn golden_codex_viewport_resolves_the_approved_shell_edges() {
        let shell = resolve_shell(
            PanelPreferences::default(),
            ShellRequest {
                viewport_width: 1_710.0,
                navigation_open: true,
                workbench_open: true,
                context_open: true,
            },
        );

        assert_eq!(shell.navigation_width, 308.0);
        assert_eq!(shell.workbench_width, 320.0);
        assert_eq!(shell.conversation_width, 1_082.0);
        assert_eq!(shell.file_tree_width, 120.0);
    }

    #[test]
    fn context_card_keeps_navigation_open_when_workbench_needs_overlay() {
        let shell = resolve_shell(
            PanelPreferences::default(),
            ShellRequest {
                viewport_width: 1_440.0,
                navigation_open: true,
                workbench_open: true,
                context_open: true,
            },
        );

        assert_eq!(shell.navigation_width, super::NAVIGATION_DEFAULT_WIDTH);
        assert_eq!(
            shell.workbench_placement,
            super::WorkbenchPlacement::Overlay
        );
        assert_eq!(shell.conversation_width, 1_132.0);
        assert_eq!(shell.context_width, 288.0);
    }

    #[test]
    fn resizable_regions_clamp_to_the_supported_ranges() {
        let resolved = resolve_shell(
            PanelPreferences {
                navigation_width: 900.0,
                workbench_width: 900.0,
                file_tree_width: 900.0,
            },
            ShellRequest {
                viewport_width: 2_000.0,
                navigation_open: true,
                workbench_open: true,
                context_open: false,
            },
        );

        assert_eq!(resolved.navigation_width, super::NAVIGATION_MAX_WIDTH);
        assert_eq!(resolved.workbench_width, super::WORKBENCH_MAX_WIDTH);
        assert_eq!(resolved.file_tree_width, super::FILE_TREE_MAX_WIDTH);
    }

    #[test]
    fn pointer_resize_updates_only_the_selected_preference() {
        let preferences = PanelPreferences::default();
        let navigation =
            resize_panel_preferences(preferences, PanelResizeTarget::Navigation, 360.0, 1_440.0);
        assert_eq!(navigation.navigation_width, 360.0);
        assert_eq!(navigation.workbench_width, preferences.workbench_width);

        let workbench =
            resize_panel_preferences(preferences, PanelResizeTarget::Workbench, 900.0, 1_440.0);
        assert_eq!(workbench.workbench_width, 540.0);

        let file_tree =
            resize_panel_preferences(preferences, PanelResizeTarget::FileTree, 1_240.0, 1_440.0);
        assert_eq!(file_tree.file_tree_width, 200.0);
    }

    #[test]
    fn narrow_windows_keep_navigation_and_overlay_the_workbench() {
        let preferences = PanelPreferences::default();

        let overlaid = resolve_shell(
            preferences,
            ShellRequest {
                viewport_width: 1_100.0,
                navigation_open: true,
                workbench_open: true,
                context_open: false,
            },
        );
        assert_eq!(overlaid.navigation_width, super::NAVIGATION_DEFAULT_WIDTH);
        assert_eq!(
            overlaid.workbench_placement,
            super::WorkbenchPlacement::Overlay
        );
        assert_eq!(overlaid.conversation_width, 792.0);

        let very_narrow = resolve_shell(
            preferences,
            ShellRequest {
                viewport_width: 800.0,
                navigation_open: true,
                workbench_open: true,
                context_open: false,
            },
        );
        assert_eq!(
            very_narrow.navigation_width,
            super::NAVIGATION_DEFAULT_WIDTH
        );
        assert_eq!(
            very_narrow.workbench_placement,
            super::WorkbenchPlacement::Overlay
        );
        assert_eq!(very_narrow.conversation_width, 492.0);
        assert_eq!(very_narrow.workbench_width, super::WORKBENCH_DEFAULT_WIDTH);

        let restored = resolve_shell(
            preferences,
            ShellRequest {
                viewport_width: 1_710.0,
                navigation_open: true,
                workbench_open: true,
                context_open: false,
            },
        );
        assert_eq!(restored.navigation_width, super::NAVIGATION_DEFAULT_WIDTH);
        assert_eq!(restored.workbench_width, super::WORKBENCH_DEFAULT_WIDTH);
        assert_eq!(
            restored.workbench_placement,
            super::WorkbenchPlacement::Docked
        );
    }

    #[test]
    fn workbench_dock_and_overlay_boundaries_include_navigation() {
        let docked = resolve_shell(
            PanelPreferences::default(),
            ShellRequest {
                viewport_width: 1_188.0,
                navigation_open: true,
                workbench_open: true,
                context_open: false,
            },
        );
        assert_eq!(
            docked.workbench_placement,
            super::WorkbenchPlacement::Docked
        );
        assert_eq!(docked.navigation_width, super::NAVIGATION_DEFAULT_WIDTH);

        let overlaid = resolve_shell(
            PanelPreferences::default(),
            ShellRequest {
                viewport_width: 1_187.0,
                navigation_open: true,
                workbench_open: true,
                context_open: false,
            },
        );
        assert_eq!(
            overlaid.workbench_placement,
            super::WorkbenchPlacement::Overlay
        );
        assert_eq!(overlaid.navigation_width, super::NAVIGATION_DEFAULT_WIDTH);

        let context_docked = resolve_shell(
            PanelPreferences::default(),
            ShellRequest {
                viewport_width: 1_508.0,
                navigation_open: true,
                workbench_open: true,
                context_open: true,
            },
        );
        assert_eq!(
            context_docked.workbench_placement,
            super::WorkbenchPlacement::Docked
        );
        assert_eq!(
            context_docked.navigation_width,
            super::NAVIGATION_DEFAULT_WIDTH
        );

        let context_overlaid = resolve_shell(
            PanelPreferences::default(),
            ShellRequest {
                viewport_width: 1_507.0,
                navigation_open: true,
                workbench_open: true,
                context_open: true,
            },
        );
        assert_eq!(
            context_overlaid.workbench_placement,
            super::WorkbenchPlacement::Overlay
        );
        assert_eq!(
            context_overlaid.navigation_width,
            super::NAVIGATION_DEFAULT_WIDTH
        );
    }

    #[test]
    fn every_right_surface_preserves_requested_navigation_visibility() {
        let preferences = PanelPreferences {
            navigation_width: 352.0,
            workbench_width: 508.0,
            file_tree_width: 184.0,
        };

        for (workbench_open, context_open) in
            [(false, false), (false, true), (true, false), (true, true)]
        {
            let shell = resolve_shell(
                preferences,
                ShellRequest {
                    viewport_width: 800.0,
                    navigation_open: true,
                    workbench_open,
                    context_open,
                },
            );
            assert_eq!(shell.navigation_width, preferences.navigation_width);
            if context_open {
                assert!(shell.context_width >= 0.0);
                assert!(
                    shell.context_right + shell.context_width
                        <= shell.conversation_width - super::CONTEXT_PANEL_INSET + f32::EPSILON
                );
            }
        }

        let hidden = resolve_shell(
            preferences,
            ShellRequest {
                viewport_width: 800.0,
                navigation_open: false,
                workbench_open: true,
                context_open: true,
            },
        );
        assert_eq!(hidden.navigation_width, 0.0);
    }

    #[test]
    fn overlay_keeps_the_context_card_outside_the_workbench() {
        let shell = resolve_shell(
            PanelPreferences::default(),
            ShellRequest {
                viewport_width: 800.0,
                navigation_open: false,
                workbench_open: true,
                context_open: true,
            },
        );

        assert_eq!(
            shell.workbench_placement,
            super::WorkbenchPlacement::Overlay
        );
        assert!(shell.context_right >= shell.workbench_width + 16.0);
        assert!(shell.context_right + shell.context_width <= 800.0 - 16.0);
    }

    #[test]
    fn file_tree_never_consumes_the_entire_workbench() {
        let shell = resolve_shell(
            PanelPreferences {
                workbench_width: super::WORKBENCH_MIN_WIDTH,
                file_tree_width: super::FILE_TREE_MAX_WIDTH,
                ..PanelPreferences::default()
            },
            ShellRequest {
                viewport_width: 1_440.0,
                navigation_open: false,
                workbench_open: true,
                context_open: false,
            },
        );

        assert!(shell.workbench_width - shell.file_tree_width >= super::FILE_DETAIL_MIN_WIDTH);
    }

    #[test]
    fn preferred_panel_widths_round_trip_without_persisting_responsive_state() {
        let path = temporary_preferences_path();
        let preferences = PanelPreferences {
            navigation_width: 352.0,
            workbench_width: 508.0,
            file_tree_width: 184.0,
        };

        save_panel_preferences(&path, preferences).expect("save panel preferences");
        let loaded = load_panel_preferences(&path).expect("load panel preferences");

        assert_eq!(loaded, preferences);
        assert!(path.exists());
        let _ = std::fs::remove_file(path);
    }

    #[test]
    fn malformed_preferences_fail_closed_to_defaults() {
        let path = temporary_preferences_path();
        std::fs::write(&path, b"not-json").expect("write malformed preferences");

        let loaded = load_panel_preferences(&path).expect("load fallback preferences");

        assert_eq!(loaded, PanelPreferences::default());
        let _ = std::fs::remove_file(path);
    }

    #[test]
    fn spring_settle_spans_zero_to_one_without_overshoot() {
        assert_eq!(super::spring_settle(0.0), 0.0);
        assert_eq!(super::spring_settle(1.0), 1.0);

        let mut prev = 0.0;
        for i in 0..=100 {
            let t = i as f32 / 100.0;
            let val = super::spring_settle(t);
            assert!((0.0..=1.0).contains(&val));
            assert!(val >= prev);
            prev = val;
        }
        // Check front-loaded curve (>80% distance covered by midpoint t=0.5)
        assert!(super::spring_settle(0.5) > 0.8);
    }

    #[test]
    fn toggle_debounce_drops_autorepeat_key_events() {
        use std::time::Duration;
        assert!(super::toggle_has_settled(None));
        assert!(!super::toggle_has_settled(Some(Duration::from_millis(30))));
        assert!(super::toggle_has_settled(Some(super::SEAM_SLIDE)));
    }

    #[test]
    fn seam_slide_retargets_dynamically() {
        use std::time::Instant;
        let slide = super::SeamSlide::begin(0.0, 308.0).unwrap();
        let now = Instant::now();
        assert!((slide.seam_at(308.0, now) - 0.0).abs() < 1e-4);
        let future = now + super::SEAM_SLIDE;
        assert_eq!(slide.seam_at(400.0, future), 400.0);
    }
}
