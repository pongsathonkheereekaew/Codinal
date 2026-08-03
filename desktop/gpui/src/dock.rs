//! Typed presentation state for the native tools dock.
//!
//! The dock owns only pane visibility, ordering, focus-facing selection, and
//! the kept-alive terminal presentation flag. Runtime data and commands stay
//! in `WorkspacePrototype` and the existing native-host/control-plane owners.

use crate::side_panel::{SidePanelTabs, SidePanelTool};
use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum DockAction {
    SelectSession(Option<String>),
    Toggle,
    TogglePicker,
    Activate(SidePanelTool),
    CloseActive,
    ObserveTerminalOpened,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
struct DockSnapshot {
    open: bool,
    tabs: SidePanelTabs,
    picker_open: bool,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct DockState {
    open: bool,
    tabs: SidePanelTabs,
    picker_open: bool,
    terminal_kept_alive: bool,
    session_id: Option<String>,
    sessions: BTreeMap<String, DockSnapshot>,
}

impl DockState {
    pub fn open(&self) -> bool {
        self.open
    }

    pub fn open_tabs(&self) -> &[SidePanelTool] {
        self.tabs.open()
    }

    pub fn active(&self) -> Option<SidePanelTool> {
        self.tabs.active()
    }

    pub fn picker_open(&self) -> bool {
        self.picker_open
    }

    pub fn terminal_kept_alive(&self) -> bool {
        self.terminal_kept_alive
    }

    pub fn set_open(&mut self, open: bool) {
        self.open = open;
        if !open {
            self.picker_open = false;
        }
    }

    pub fn dispatch(&mut self, action: DockAction) {
        match action {
            DockAction::SelectSession(session_id) => {
                if self.session_id == session_id {
                    return;
                }
                if let Some(current_session_id) = self.session_id.take() {
                    self.sessions.insert(current_session_id, self.snapshot());
                }
                self.session_id = session_id;
                if let Some(session_id) = self.session_id.as_ref() {
                    if let Some(snapshot) = self.sessions.get(session_id).cloned() {
                        self.restore(snapshot);
                    } else {
                        self.open = false;
                        self.tabs = SidePanelTabs::default();
                        self.picker_open = false;
                    }
                } else {
                    self.open = false;
                    self.tabs = SidePanelTabs::default();
                    self.picker_open = false;
                }
            }
            DockAction::Toggle => self.set_open(!self.open),
            DockAction::TogglePicker => {
                if self.open {
                    self.picker_open = !self.picker_open;
                }
            }
            DockAction::Activate(tool) => {
                self.open = true;
                self.picker_open = false;
                self.tabs.activate(tool);
                if tool == SidePanelTool::Terminal {
                    self.terminal_kept_alive = true;
                }
            }
            DockAction::CloseActive => {
                self.tabs.close_active();
                self.picker_open = false;
                if self.tabs.active().is_none() {
                    self.open = false;
                }
            }
            DockAction::ObserveTerminalOpened => {
                self.terminal_kept_alive = true;
            }
        }
    }

    fn snapshot(&self) -> DockSnapshot {
        DockSnapshot {
            open: self.open,
            tabs: self.tabs.clone(),
            picker_open: self.picker_open,
        }
    }

    fn restore(&mut self, snapshot: DockSnapshot) {
        self.open = snapshot.open;
        self.tabs = snapshot.tabs;
        self.picker_open = snapshot.picker_open;
    }
}

#[cfg(test)]
mod tests {
    use super::{DockAction, DockState};
    use crate::side_panel::SidePanelTool;

    #[test]
    fn dock_actions_keep_ordered_tabs_and_close_to_a_neighbor() {
        let mut dock = DockState::default();
        dock.dispatch(DockAction::Activate(SidePanelTool::Review));
        dock.dispatch(DockAction::Activate(SidePanelTool::Files));
        dock.dispatch(DockAction::Activate(SidePanelTool::Terminal));

        assert!(dock.open());
        assert_eq!(dock.active(), Some(SidePanelTool::Terminal));
        assert_eq!(
            dock.open_tabs(),
            &[
                SidePanelTool::Review,
                SidePanelTool::Files,
                SidePanelTool::Terminal
            ]
        );
        assert!(dock.terminal_kept_alive());

        dock.dispatch(DockAction::CloseActive);
        assert_eq!(dock.active(), Some(SidePanelTool::Files));
        assert!(dock.open());
    }

    #[test]
    fn hiding_dock_does_not_release_terminal_presentation() {
        let mut dock = DockState::default();
        dock.dispatch(DockAction::Activate(SidePanelTool::Terminal));
        dock.dispatch(DockAction::Toggle);

        assert!(!dock.open());
        assert!(dock.terminal_kept_alive());
        assert_eq!(dock.active(), Some(SidePanelTool::Terminal));
    }

    #[test]
    fn picker_is_only_visible_for_an_open_dock() {
        let mut dock = DockState::default();
        dock.dispatch(DockAction::TogglePicker);
        assert!(!dock.picker_open());

        dock.dispatch(DockAction::Toggle);
        dock.dispatch(DockAction::TogglePicker);
        assert!(dock.picker_open());

        dock.dispatch(DockAction::Toggle);
        assert!(!dock.picker_open());
    }

    #[test]
    fn session_switches_restore_only_that_sessions_dock_preferences() {
        let mut dock = DockState::default();
        dock.dispatch(DockAction::SelectSession(Some("session-a".to_owned())));
        dock.dispatch(DockAction::Activate(SidePanelTool::Review));
        dock.dispatch(DockAction::SelectSession(Some("session-b".to_owned())));
        assert_eq!(dock.active(), None);

        dock.dispatch(DockAction::Activate(SidePanelTool::Files));
        dock.dispatch(DockAction::SelectSession(Some("session-a".to_owned())));
        assert_eq!(dock.active(), Some(SidePanelTool::Review));
        assert_eq!(dock.open_tabs(), &[SidePanelTool::Review]);
    }
}
