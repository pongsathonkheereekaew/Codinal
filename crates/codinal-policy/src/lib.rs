//! Deny-by-default approval state for Rust runtime mutations.

use std::collections::BTreeSet;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Risk {
    Read,
    WriteLocal,
    Exec,
    External,
}

impl Risk {
    pub fn requires_approval(self) -> bool {
        !matches!(self, Self::Read)
    }
}

/// One-shot approval register. Approval IDs are consumed when authorized, so
/// duplicate or replayed mutations fail closed.
#[derive(Default)]
pub struct ApprovalChokepoint {
    approved: BTreeSet<String>,
}

impl ApprovalChokepoint {
    pub fn approve_once(&mut self, approval_id: &str) -> bool {
        valid_id(approval_id) && self.approved.insert(approval_id.to_owned())
    }

    pub fn authorize(&mut self, risk: Risk, approval_id: Option<&str>) -> bool {
        if !risk.requires_approval() {
            return approval_id.is_none();
        }
        approval_id
            .filter(|id| valid_id(id))
            .is_some_and(|id| self.approved.remove(id))
    }
}

fn valid_id(id: &str) -> bool {
    (16..=128).contains(&id.len())
        && id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
}

#[cfg(test)]
mod tests {
    use super::{ApprovalChokepoint, Risk};

    const APPROVAL: &str = "approval-token-0123456789";

    #[test]
    fn mutations_fail_closed_until_explicitly_approved() {
        let mut gate = ApprovalChokepoint::default();
        assert!(!gate.authorize(Risk::WriteLocal, None));
        assert!(!gate.authorize(Risk::Exec, Some(APPROVAL)));
        assert!(gate.approve_once(APPROVAL));
        assert!(gate.authorize(Risk::Exec, Some(APPROVAL)));
    }

    #[test]
    fn approval_is_one_shot_and_cannot_be_replayed() {
        let mut gate = ApprovalChokepoint::default();
        assert!(gate.approve_once(APPROVAL));
        assert!(!gate.approve_once(APPROVAL));
        assert!(gate.authorize(Risk::External, Some(APPROVAL)));
        assert!(!gate.authorize(Risk::External, Some(APPROVAL)));
    }

    #[test]
    fn read_does_not_accept_an_approval_token() {
        let mut gate = ApprovalChokepoint::default();
        assert!(gate.authorize(Risk::Read, None));
        assert!(!gate.authorize(Risk::Read, Some(APPROVAL)));
    }
}
