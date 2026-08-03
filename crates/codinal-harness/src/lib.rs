//! Rust ownership, projection, and workflow primitives for the universal
//! agents/skills harness.
//!
//! The manager deliberately separates source, user-owned overlay, generated
//! live content, and host projections. Scanning is read-only. Writes require
//! an exact plan approval and produce a durable receipt that can be verified or
//! rolled back without deleting paths the manager does not own.

mod inventory;
mod workflow;

pub use inventory::{
    CapabilityStatus, DriftEntry, DriftKind, HarnessApproval, HarnessError, HarnessInventory,
    HarnessManager, HarnessPlan, HarnessReceipt, HarnessRoots, HostAdapter, HostProjectionFile,
    HostProjectionInventory, HostProjectionRoot, HostProjectionSpec, InventoryEntry,
    InventoryOwner, OwnedPathRecord, PlanAction, PlanBlock, PlanOperation, ProjectionSource,
    ProjectionWriteMode, ReceiptOperation, TreeInventory, TreeKind, VerificationResult,
};
pub use workflow::{
    ArtifactRef, DurableHandoff, EvaluationLedgerEntry, EvidenceRef, RoleProfile, StageAttempt,
    StageKind, StageOutcome, StageState, WorkflowApproval, WorkflowBudget, WorkflowError,
    WorkflowLedger, WorkflowPlan, WorkflowReceipt, WorkflowRun, WorkflowState,
};
