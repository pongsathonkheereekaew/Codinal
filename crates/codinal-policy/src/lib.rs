//! Deny-by-default approval state for Rust runtime mutations.

use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::io;

mod audit;

pub use audit::{AuditLedger, AuditLedgerEvent, AuditLedgerInput, AuditRedactor};

const MAX_PENDING_GLOBAL: usize = 1_024;
const MAX_PENDING_PER_SESSION: usize = 128;

#[derive(Debug, PartialEq, Eq)]
pub struct AuditEvent {
    pub domain: String,
    pub action: String,
    pub subject: String,
}

impl AuditEvent {
    pub fn new(domain: &str, action: &str, subject: &str) -> Option<Self> {
        let valid = |value: &str| !value.is_empty() && value.len() <= 128 && !value.contains('\n');
        (valid(domain) && valid(action) && subject.len() <= 128).then(|| Self {
            domain: domain.to_owned(),
            action: action.to_owned(),
            subject: subject.to_owned(),
        })
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Risk {
    Read,
    WriteLocal,
    Exec,
    External,
}

#[derive(Clone, Debug, PartialEq)]
pub struct PermissionRequest {
    pub tool_call_id: String,
    pub tool_name: String,
    pub arguments: serde_json::Value,
    pub reason: String,
    pub risk: String,
    pub command: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct PendingApproval {
    pub approval_id: String,
    pub tool_name: String,
    pub arguments: serde_json::Value,
    pub reason: String,
    pub risk: String,
    pub command: Option<String>,
}

#[derive(Default)]
pub struct ApprovalBroker {
    pending: Vec<((String, String), PendingApproval)>,
}

impl ApprovalBroker {
    pub fn request(&mut self, session_id: &str, request: PermissionRequest) -> io::Result<String> {
        self.request_with_turn_id(session_id, None, request)
    }

    pub fn request_for_turn(
        &mut self,
        session_id: &str,
        turn_id: &str,
        request: PermissionRequest,
    ) -> io::Result<String> {
        validate_subject(turn_id, "turn")?;
        self.request_with_turn_id(session_id, Some(turn_id), request)
    }

    fn request_with_turn_id(
        &mut self,
        session_id: &str,
        turn_id: Option<&str>,
        request: PermissionRequest,
    ) -> io::Result<String> {
        validate_subject(session_id, "session")?;
        validate_subject(&request.tool_call_id, "tool call")?;
        validate_subject(&request.tool_name, "tool")?;
        validate_subject(&request.reason, "approval reason")?;
        if !matches!(request.risk.as_str(), "write_local" | "exec" | "external") {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid approval risk",
            ));
        }
        if request.arguments.to_string().len() > 32 * 1024
            || request
                .command
                .as_ref()
                .is_some_and(|value| value.len() > 4096)
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "approval request exceeds limit",
            ));
        }
        let approval_id = turn_id.map_or_else(
            || approval_id(session_id, &request.tool_call_id),
            |turn_id| approval_id_for_turn(session_id, turn_id, &request.tool_call_id),
        );
        let pending = PendingApproval {
            approval_id: approval_id.clone(),
            tool_name: request.tool_name,
            arguments: request.arguments,
            reason: request.reason,
            risk: request.risk,
            command: request.command,
        };
        let key = (session_id.to_owned(), approval_id.clone());
        if self.pending.iter().any(|(candidate, _)| candidate == &key) {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "approval already pending",
            ));
        }
        let session_count = self
            .pending
            .iter()
            .filter(|((candidate, _), _)| candidate == session_id)
            .count();
        if self.pending.len() >= MAX_PENDING_GLOBAL || session_count >= MAX_PENDING_PER_SESSION {
            return Err(io::Error::new(
                io::ErrorKind::OutOfMemory,
                "pending approval capacity reached",
            ));
        }
        self.pending.push((key, pending));
        Ok(approval_id)
    }

    pub fn pending(&self, session_id: &str) -> Vec<PendingApproval> {
        self.pending
            .iter()
            .filter(|((candidate, _), _)| candidate == session_id)
            .map(|(_, pending)| pending.clone())
            .collect()
    }

    pub fn resolve(&mut self, session_id: &str, approval_id: &str) -> bool {
        let key = (session_id.to_owned(), approval_id.to_owned());
        let Some(index) = self
            .pending
            .iter()
            .position(|(candidate, _)| candidate == &key)
        else {
            return false;
        };
        self.pending.remove(index);
        true
    }

    pub fn restore_pending(
        &mut self,
        session_id: &str,
        pending: PendingApproval,
    ) -> io::Result<()> {
        validate_subject(session_id, "session")?;
        if !valid_id(&pending.approval_id) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid approval id",
            ));
        }
        validate_subject(&pending.tool_name, "tool")?;
        validate_subject(&pending.reason, "approval reason")?;
        if !matches!(pending.risk.as_str(), "write_local" | "exec" | "external") {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "invalid approval risk",
            ));
        }
        let key = (session_id.to_owned(), pending.approval_id.clone());
        if self.pending.iter().any(|(candidate, _)| candidate == &key) {
            return Ok(());
        }
        let session_count = self
            .pending
            .iter()
            .filter(|((candidate, _), _)| candidate == session_id)
            .count();
        if self.pending.len() >= MAX_PENDING_GLOBAL || session_count >= MAX_PENDING_PER_SESSION {
            return Err(io::Error::new(
                io::ErrorKind::OutOfMemory,
                "pending approval capacity reached",
            ));
        }
        self.pending.push((key, pending));
        Ok(())
    }
}

fn approval_id(session_id: &str, tool_call_id: &str) -> String {
    let mut digest = Sha256::new();
    digest.update(session_id.as_bytes());
    digest.update([0]);
    digest.update(tool_call_id.as_bytes());
    format!("{:x}", digest.finalize())[..32].to_owned()
}

fn approval_id_for_turn(session_id: &str, turn_id: &str, tool_call_id: &str) -> String {
    let mut digest = Sha256::new();
    digest.update(session_id.as_bytes());
    digest.update([0]);
    digest.update(turn_id.as_bytes());
    digest.update([0]);
    digest.update(tool_call_id.as_bytes());
    format!("{:x}", digest.finalize())[..32].to_owned()
}

fn validate_subject(value: &str, name: &str) -> io::Result<()> {
    if value.is_empty() || value.len() > 256 || value.contains(['\r', '\n']) {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("invalid {name}"),
        ))
    } else {
        Ok(())
    }
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

    pub fn authorize_with_audit(
        &mut self,
        risk: Risk,
        approval_id: Option<&str>,
        subject: &str,
    ) -> (bool, Option<AuditEvent>) {
        let granted = self.authorize(risk, approval_id);
        let action = if granted {
            "approval_consumed"
        } else {
            "approval_denied"
        };
        (granted, AuditEvent::new("policy", action, subject))
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
    use super::{
        ApprovalBroker, ApprovalChokepoint, AuditEvent, PermissionRequest, Risk,
        MAX_PENDING_PER_SESSION,
    };

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

    #[test]
    fn audit_events_are_bounded_metadata_not_secret_payloads() {
        assert_eq!(
            AuditEvent::new("policy", "approval_granted", "session-1")
                .expect("event")
                .action,
            "approval_granted"
        );
        assert!(AuditEvent::new("policy\nsecret", "approval", "").is_none());
    }

    #[test]
    fn approval_outcome_has_secret_free_audit_metadata() {
        let mut gate = ApprovalChokepoint::default();
        assert!(gate.approve_once(APPROVAL));
        let (granted, event) =
            gate.authorize_with_audit(Risk::WriteLocal, Some(APPROVAL), "session-1");
        assert!(granted);
        assert_eq!(event.expect("event").action, "approval_consumed");
    }

    #[test]
    fn pending_approval_read_model_is_session_scoped_and_stable() {
        let mut broker = ApprovalBroker::default();
        let id = broker
            .request(
                "session-1",
                PermissionRequest {
                    tool_call_id: "call-1".to_owned(),
                    tool_name: "write_file".to_owned(),
                    arguments: serde_json::json!({"path": "README.md"}),
                    reason: "write workspace file".to_owned(),
                    risk: "write_local".to_owned(),
                    command: None,
                },
            )
            .expect("pending request");
        assert_eq!(id, "eb8ccf651372cda868564a602768dbbd");
        assert_eq!(broker.pending("session-1").len(), 1);
        assert!(broker.pending("session-2").is_empty());
        assert!(broker.resolve("session-1", &id));
        assert!(broker.pending("session-1").is_empty());
        assert!(!broker.resolve("session-1", &id));
    }

    #[test]
    fn pending_approvals_are_bounded_per_session() {
        let mut broker = ApprovalBroker::default();
        for index in 0..MAX_PENDING_PER_SESSION {
            broker
                .request(
                    "session-1",
                    PermissionRequest {
                        tool_call_id: format!("call-{index}"),
                        tool_name: "write_file".to_owned(),
                        arguments: serde_json::json!({}),
                        reason: "write workspace file".to_owned(),
                        risk: "write_local".to_owned(),
                        command: None,
                    },
                )
                .expect("within capacity");
        }
        assert!(broker
            .request(
                "session-1",
                PermissionRequest {
                    tool_call_id: "overflow".to_owned(),
                    tool_name: "write_file".to_owned(),
                    arguments: serde_json::json!({}),
                    reason: "write workspace file".to_owned(),
                    risk: "write_local".to_owned(),
                    command: None,
                },
            )
            .is_err());
    }

    #[test]
    fn approval_id_is_bound_to_turn_identity() {
        let mut broker = ApprovalBroker::default();
        let request = |path: &str| PermissionRequest {
            tool_call_id: "call-1".to_owned(),
            tool_name: "apply_patch".to_owned(),
            arguments: serde_json::json!({"path": path}),
            reason: "write workspace file".to_owned(),
            risk: "write_local".to_owned(),
            command: None,
        };
        let first = broker
            .request_for_turn("session-1", "turn-1", request("one.txt"))
            .expect("first pending request");
        let second = broker
            .request_for_turn("session-1", "turn-2", request("two.txt"))
            .expect("second pending request");
        assert_ne!(first, second);
        assert_eq!(broker.pending("session-1").len(), 2);
    }
}
