use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt::{Display, Formatter};
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Component, Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

const SCHEMA: &str = "codinal.harness.v1";
const OWNERSHIP_FILE: &str = ".codinal-harness-ownership.json";
const MAX_FILES: usize = 50_000;
const MAX_FILE_BYTES: u64 = 16 * 1024 * 1024;
const MAX_TOTAL_BYTES: u64 = 512 * 1024 * 1024;
const MAX_RELATIVE_PATH: usize = 4_096;

#[derive(Debug)]
pub struct HarnessError {
    kind: io::ErrorKind,
    message: String,
}

impl HarnessError {
    fn new(kind: io::ErrorKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
        }
    }

    fn invalid(message: impl Into<String>) -> Self {
        Self::new(io::ErrorKind::InvalidInput, message)
    }

    fn conflict(message: impl Into<String>) -> Self {
        Self::new(io::ErrorKind::AlreadyExists, message)
    }

    fn not_found(message: impl Into<String>) -> Self {
        Self::new(io::ErrorKind::NotFound, message)
    }

    pub fn kind(&self) -> io::ErrorKind {
        self.kind
    }
}

impl Display for HarnessError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(&self.message)
    }
}

impl Error for HarnessError {}

impl From<io::Error> for HarnessError {
    fn from(error: io::Error) -> Self {
        Self::new(error.kind(), error.to_string())
    }
}

impl From<serde_json::Error> for HarnessError {
    fn from(error: serde_json::Error) -> Self {
        Self::new(io::ErrorKind::InvalidData, error.to_string())
    }
}

type Result<T> = std::result::Result<T, HarnessError>;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CapabilityStatus {
    Supported,
    Partial,
    Unsupported,
    Unverified,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum HostAdapter {
    OpenCodeCli,
    ClaudeCode,
    Codex,
    Cursor,
    GeminiCli,
    Other(String),
}

impl HostAdapter {
    pub fn id(&self) -> &str {
        match self {
            Self::OpenCodeCli => "opencode",
            Self::ClaudeCode => "claude-code",
            Self::Codex => "codex",
            Self::Cursor => "cursor",
            Self::GeminiCli => "gemini-cli",
            Self::Other(value) => value,
        }
    }

    pub fn writes_enabled(&self) -> bool {
        matches!(self, Self::OpenCodeCli)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct HostProjectionRoot {
    pub id: String,
    pub path: PathBuf,
    pub adapter: HostAdapter,
    pub capability: CapabilityStatus,
}

impl HostProjectionRoot {
    pub fn new(
        id: impl Into<String>,
        path: impl Into<PathBuf>,
        adapter: HostAdapter,
        capability: CapabilityStatus,
    ) -> Result<Self> {
        let root = Self {
            id: id.into(),
            path: path.into(),
            adapter,
            capability,
        };
        validate_host_id(&root.id)?;
        if !root.path.is_absolute() {
            return Err(HarnessError::invalid(
                "host projection path must be absolute",
            ));
        }
        Ok(root)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct HarnessRoots {
    pub source_bundle: PathBuf,
    pub user_overlay: PathBuf,
    pub live_projection: PathBuf,
    pub state_dir: PathBuf,
    pub host_projections: Vec<HostProjectionRoot>,
}

impl HarnessRoots {
    pub fn validate(&self) -> Result<()> {
        for (name, path) in [
            ("source bundle", &self.source_bundle),
            ("user overlay", &self.user_overlay),
            ("live projection", &self.live_projection),
            ("harness state", &self.state_dir),
        ] {
            if !path.is_absolute() {
                return Err(HarnessError::invalid(format!(
                    "{name} path must be absolute"
                )));
            }
            if path.to_string_lossy().contains('\0') {
                return Err(HarnessError::invalid(format!("{name} path contains NUL")));
            }
        }
        let mut ids = BTreeSet::new();
        let mut paths = BTreeSet::new();
        for host in &self.host_projections {
            validate_host_id(&host.id)?;
            if !host.path.is_absolute() {
                return Err(HarnessError::invalid(
                    "host projection path must be absolute",
                ));
            }
            if !ids.insert(host.id.clone()) {
                return Err(HarnessError::conflict("duplicate host projection id"));
            }
            if !paths.insert(host.path.to_string_lossy().into_owned()) {
                return Err(HarnessError::conflict("duplicate host projection path"));
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TreeKind {
    File,
    Directory,
    Symlink,
    Other,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum InventoryOwner {
    SourceBundle,
    UserOverlay,
    Managed,
    NonOwned,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct InventoryEntry {
    pub path: String,
    pub kind: TreeKind,
    pub bytes: u64,
    pub sha256: Option<String>,
    pub link_target: Option<String>,
    pub owner: InventoryOwner,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct TreeInventory {
    pub root: String,
    pub exists: bool,
    pub entries: Vec<InventoryEntry>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct HostProjectionInventory {
    pub id: String,
    pub root: String,
    pub adapter: HostAdapter,
    pub capability: CapabilityStatus,
    pub tree: TreeInventory,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum DriftKind {
    MissingLive,
    ContentDrift,
    ExtraManaged,
    ExtraNonOwned,
    OverlayOverridesSource,
    HostCapabilityUnverified,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DriftEntry {
    pub scope: String,
    pub path: String,
    pub kind: DriftKind,
    pub detail: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct HarnessInventory {
    pub schema: String,
    pub fingerprint: String,
    pub source_bundle: TreeInventory,
    pub user_overlay: TreeInventory,
    pub live_projection: TreeInventory,
    pub host_projections: Vec<HostProjectionInventory>,
    pub drift: Vec<DriftEntry>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OwnedPathRecord {
    pub target_key: String,
    pub source: String,
    pub digest: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
struct OwnershipJournal {
    schema: String,
    entries: BTreeMap<String, OwnedPathRecord>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct HarnessPlan {
    pub schema: String,
    pub plan_id: String,
    pub inventory_fingerprint: String,
    pub target: String,
    pub adapter: Option<HostAdapter>,
    pub operations: Vec<PlanOperation>,
    pub blocks: Vec<PlanBlock>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PlanAction {
    Create,
    Update,
    Remove,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProjectionSource {
    pub root: String,
    pub relative_path: String,
    pub digest: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PlanOperation {
    pub target: String,
    pub ownership_key: String,
    pub relative_path: String,
    pub action: PlanAction,
    pub source: Option<ProjectionSource>,
    pub expected_before_sha256: Option<String>,
    pub after_sha256: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PlanBlock {
    pub target: String,
    pub relative_path: String,
    pub reason: String,
    pub owner: Option<InventoryOwner>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct HarnessApproval {
    pub approval_id: String,
    pub plan_id: String,
    pub approved_at_ms: u128,
    pub expires_at_ms: u128,
}

impl HarnessApproval {
    pub fn new(
        approval_id: impl Into<String>,
        plan_id: impl Into<String>,
        approved_at_ms: u128,
        expires_at_ms: u128,
    ) -> Result<Self> {
        let approval = Self {
            approval_id: approval_id.into(),
            plan_id: plan_id.into(),
            approved_at_ms,
            expires_at_ms,
        };
        validate_id(&approval.approval_id, "approval")?;
        validate_id(&approval.plan_id, "plan")?;
        if expires_at_ms <= approved_at_ms {
            return Err(HarnessError::invalid(
                "approval expiry must be in the future",
            ));
        }
        Ok(approval)
    }

    fn valid_for(&self, plan_id: &str, now_ms: u128) -> bool {
        self.plan_id == plan_id && now_ms >= self.approved_at_ms && now_ms < self.expires_at_ms
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReceiptOperation {
    pub target: String,
    pub ownership_key: String,
    pub relative_path: String,
    pub action: PlanAction,
    pub before_sha256: Option<String>,
    pub after_sha256: Option<String>,
    pub backup_file: Option<String>,
    pub previous_owner: Option<OwnedPathRecord>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct HarnessReceipt {
    pub schema: String,
    pub receipt_id: String,
    pub plan_id: String,
    pub approval_id: String,
    pub applied_at_ms: u128,
    pub operations: Vec<ReceiptOperation>,
    pub rolled_back: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VerificationResult {
    pub receipt_id: String,
    pub valid: bool,
    pub rolled_back: bool,
    pub mismatches: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ProjectionWriteMode {
    Copy,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct HostProjectionFile {
    pub source_relative: String,
    pub target_relative: String,
    pub mode: ProjectionWriteMode,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct HostProjectionSpec {
    pub adapter: HostAdapter,
    pub files: Vec<HostProjectionFile>,
}

#[derive(Clone, Debug)]
pub struct HarnessManager {
    roots: HarnessRoots,
}

impl HarnessManager {
    pub fn new(roots: HarnessRoots) -> Result<Self> {
        roots.validate()?;
        Ok(Self { roots })
    }

    pub fn roots(&self) -> &HarnessRoots {
        &self.roots
    }

    /// Read-only. This method never creates a root, journal, backup, receipt,
    /// or parent directory.
    pub fn scan(&self) -> Result<HarnessInventory> {
        let journal = self.load_journal()?;
        let source_bundle = scan_tree(
            &self.roots.source_bundle,
            InventoryOwner::SourceBundle,
            None,
        )?;
        let user_overlay = scan_tree(&self.roots.user_overlay, InventoryOwner::UserOverlay, None)?;
        let live_projection = scan_tree(
            &self.roots.live_projection,
            InventoryOwner::NonOwned,
            Some((&journal.entries, "live")),
        )?;
        let mut host_projections = Vec::with_capacity(self.roots.host_projections.len());
        for host in &self.roots.host_projections {
            host_projections.push(HostProjectionInventory {
                id: host.id.clone(),
                root: host.path.to_string_lossy().into_owned(),
                adapter: host.adapter.clone(),
                capability: host.capability.clone(),
                tree: scan_tree(
                    &host.path,
                    InventoryOwner::NonOwned,
                    Some((&journal.entries, &format!("host:{}", host.id))),
                )?,
            });
        }

        let mut drift = projection_drift(&source_bundle, &user_overlay, &live_projection);
        for host in &host_projections {
            if !matches!(host.capability, CapabilityStatus::Supported) {
                drift.push(DriftEntry {
                    scope: format!("host:{}", host.id),
                    path: String::new(),
                    kind: DriftKind::HostCapabilityUnverified,
                    detail: format!("host capability is {:?}", host.capability),
                });
            }
        }
        drift.sort_by(|left, right| {
            (&left.scope, &left.path, format!("{:?}", left.kind)).cmp(&(
                &right.scope,
                &right.path,
                format!("{:?}", right.kind),
            ))
        });
        let mut inventory = HarnessInventory {
            schema: SCHEMA.to_owned(),
            fingerprint: String::new(),
            source_bundle,
            user_overlay,
            live_projection,
            host_projections,
            drift,
        };
        inventory.fingerprint = fingerprint(&inventory)?;
        Ok(inventory)
    }

    pub fn plan_live_projection(&self, inventory: &HarnessInventory) -> Result<HarnessPlan> {
        let mut desired = BTreeMap::new();
        let mut blocks = Vec::new();
        collect_desired_files(
            &inventory.source_bundle,
            "source_bundle",
            &mut desired,
            &mut blocks,
        );
        collect_desired_files(
            &inventory.user_overlay,
            "user_overlay",
            &mut desired,
            &mut blocks,
        );
        let mut plan = build_plan(
            inventory,
            "live",
            None,
            &inventory.live_projection,
            desired,
            blocks,
        )?;
        plan.plan_id = plan_id(&plan)?;
        Ok(plan)
    }

    pub fn plan_host_projection(
        &self,
        inventory: &HarnessInventory,
        host_id: &str,
        spec: &HostProjectionSpec,
    ) -> Result<HarnessPlan> {
        validate_host_id(host_id)?;
        let host = self
            .roots
            .host_projections
            .iter()
            .find(|host| host.id == host_id)
            .ok_or_else(|| HarnessError::not_found("host projection is not configured"))?;
        let inventory_host = inventory
            .host_projections
            .iter()
            .find(|candidate| candidate.id == host_id)
            .ok_or_else(|| HarnessError::not_found("host projection inventory is missing"))?;
        let mut desired = BTreeMap::new();
        let mut blocks = Vec::new();
        if spec.adapter != host.adapter {
            blocks.push(PlanBlock {
                target: format!("host:{host_id}"),
                relative_path: String::new(),
                reason: "host adapter does not match the configured projection".to_owned(),
                owner: None,
            });
        }
        if !host.adapter.writes_enabled() || !matches!(host.capability, CapabilityStatus::Supported)
        {
            blocks.push(PlanBlock {
                target: format!("host:{host_id}"),
                relative_path: String::new(),
                reason: "host adapter is read-only until its Rust conformance gate passes"
                    .to_owned(),
                owner: None,
            });
        }
        for file in &spec.files {
            let source_relative = validate_relative(&file.source_relative)?;
            let target_relative = validate_relative(&file.target_relative)?;
            let Some(source) = inventory
                .live_projection
                .entries
                .iter()
                .find(|entry| entry.path == path_string(&source_relative))
            else {
                blocks.push(PlanBlock {
                    target: format!("host:{host_id}"),
                    relative_path: path_string(&target_relative),
                    reason: "host projection source does not exist in the live projection"
                        .to_owned(),
                    owner: None,
                });
                continue;
            };
            if !matches!(source.kind, TreeKind::File) {
                blocks.push(PlanBlock {
                    target: format!("host:{host_id}"),
                    relative_path: path_string(&target_relative),
                    reason: "host projection source must be a regular file".to_owned(),
                    owner: Some(source.owner.clone()),
                });
                continue;
            }
            if !matches!(file.mode, ProjectionWriteMode::Copy) {
                blocks.push(PlanBlock {
                    target: format!("host:{host_id}"),
                    relative_path: path_string(&target_relative),
                    reason: "unsupported host projection write mode".to_owned(),
                    owner: None,
                });
                continue;
            }
            desired.insert(
                path_string(&target_relative),
                DesiredFile {
                    source: ProjectionSource {
                        root: "live".to_owned(),
                        relative_path: source.path.clone(),
                        digest: source
                            .sha256
                            .clone()
                            .ok_or_else(|| HarnessError::invalid("source digest is missing"))?,
                    },
                    digest: source
                        .sha256
                        .clone()
                        .ok_or_else(|| HarnessError::invalid("source digest is missing"))?,
                },
            );
        }
        let mut plan = build_plan(
            inventory,
            &format!("host:{host_id}"),
            Some(spec.adapter.clone()),
            &inventory_host.tree,
            desired,
            blocks,
        )?;
        plan.plan_id = plan_id(&plan)?;
        Ok(plan)
    }

    pub fn apply(&self, plan: &HarnessPlan, approval: &HarnessApproval) -> Result<HarnessReceipt> {
        if plan.schema != SCHEMA || plan_id(plan)? != plan.plan_id {
            return Err(HarnessError::new(
                io::ErrorKind::InvalidData,
                "harness plan identity is invalid",
            ));
        }
        if !approval.valid_for(&plan.plan_id, now_ms()) {
            return Err(HarnessError::new(
                io::ErrorKind::PermissionDenied,
                "harness approval is missing, mismatched, or expired",
            ));
        }
        if !plan.blocks.is_empty() {
            return Err(HarnessError::new(
                io::ErrorKind::PermissionDenied,
                "harness plan contains blocked operations",
            ));
        }
        let current = self.scan()?;
        if current.fingerprint != plan.inventory_fingerprint {
            return Err(HarnessError::new(
                io::ErrorKind::WouldBlock,
                "harness inventory changed after the plan was created",
            ));
        }
        ensure_directory(&self.roots.state_dir)?;
        let mut journal = self.load_journal()?;
        let receipt_id = short_hash(&format!(
            "{}:{}:{}",
            plan.plan_id,
            approval.approval_id,
            now_ms()
        ));
        let backup_dir = self.roots.state_dir.join("backups").join(&receipt_id);
        ensure_directory(&backup_dir)?;
        let mut applied = Vec::new();
        for (index, operation) in plan.operations.iter().enumerate() {
            match self.apply_operation(operation, &backup_dir, index, &journal) {
                Ok(receipt_operation) => applied.push(receipt_operation),
                Err(error) => {
                    let _ = self.restore_operations(&applied, &journal);
                    let _ = fs::remove_dir_all(&backup_dir);
                    return Err(error);
                }
            }
        }
        let previous_journal = journal.clone();
        for operation in &applied {
            match operation.action {
                PlanAction::Remove => {
                    journal.entries.remove(&operation.ownership_key);
                }
                PlanAction::Create | PlanAction::Update => {
                    let digest = operation
                        .after_sha256
                        .clone()
                        .ok_or_else(|| HarnessError::invalid("write receipt is missing digest"))?;
                    let source = plan
                        .operations
                        .iter()
                        .find(|candidate| candidate.ownership_key == operation.ownership_key)
                        .and_then(|candidate| candidate.source.as_ref())
                        .map(|source| format!("{}:{}", source.root, source.relative_path))
                        .unwrap_or_else(|| "harness".to_owned());
                    journal.entries.insert(
                        operation.ownership_key.clone(),
                        OwnedPathRecord {
                            target_key: operation.ownership_key.clone(),
                            source,
                            digest,
                        },
                    );
                }
            }
        }
        if let Err(error) = self.write_journal(&journal) {
            let _ = self.restore_operations(&applied, &previous_journal);
            let _ = fs::remove_dir_all(&backup_dir);
            return Err(error);
        }
        let receipt = HarnessReceipt {
            schema: SCHEMA.to_owned(),
            receipt_id: receipt_id.clone(),
            plan_id: plan.plan_id.clone(),
            approval_id: approval.approval_id.clone(),
            applied_at_ms: now_ms(),
            operations: applied,
            rolled_back: false,
        };
        if let Err(error) = self.write_receipt(&receipt) {
            let _ = self.write_journal(&previous_journal);
            let _ = self.restore_operations(&receipt.operations, &previous_journal);
            let _ = fs::remove_dir_all(&backup_dir);
            return Err(error);
        }
        Ok(receipt)
    }

    pub fn verify_receipt(&self, receipt: &HarnessReceipt) -> Result<VerificationResult> {
        let mut mismatches = Vec::new();
        for operation in &receipt.operations {
            let root = self.root_for_target(&operation.target)?;
            let current = current_file_state(root, &operation.relative_path)?;
            let expected = if receipt.rolled_back {
                operation.before_sha256.clone()
            } else {
                operation.after_sha256.clone()
            };
            if current.as_ref().map(|state| state.digest.clone()) != expected {
                mismatches.push(format!(
                    "{}:{} does not match the {} receipt state",
                    operation.target,
                    operation.relative_path,
                    if receipt.rolled_back {
                        "before"
                    } else {
                        "after"
                    }
                ));
            }
        }
        Ok(VerificationResult {
            receipt_id: receipt.receipt_id.clone(),
            valid: mismatches.is_empty(),
            rolled_back: receipt.rolled_back,
            mismatches,
        })
    }

    pub fn rollback(&self, receipt_id: &str) -> Result<HarnessReceipt> {
        validate_id(receipt_id, "receipt")?;
        let mut receipt = self.read_receipt(receipt_id)?;
        if receipt.rolled_back {
            return Ok(receipt);
        }
        for operation in &receipt.operations {
            let root = self.root_for_target(&operation.target)?;
            let current = current_file_state(root, &operation.relative_path)?;
            if current.as_ref().map(|state| state.digest.clone()) != operation.after_sha256 {
                return Err(HarnessError::new(
                    io::ErrorKind::WouldBlock,
                    format!(
                        "cannot roll back {}:{} because its content changed",
                        operation.target, operation.relative_path
                    ),
                ));
            }
        }
        let journal = self.load_journal()?;
        self.restore_operations(&receipt.operations, &journal)?;
        let mut restored_journal = journal;
        for operation in &receipt.operations {
            if let Some(previous) = &operation.previous_owner {
                restored_journal
                    .entries
                    .insert(operation.ownership_key.clone(), previous.clone());
            } else {
                restored_journal.entries.remove(&operation.ownership_key);
            }
        }
        self.write_journal(&restored_journal)?;
        receipt.rolled_back = true;
        self.write_receipt(&receipt)?;
        Ok(receipt)
    }

    fn apply_operation(
        &self,
        operation: &PlanOperation,
        backup_dir: &Path,
        index: usize,
        journal: &OwnershipJournal,
    ) -> Result<ReceiptOperation> {
        let root = self.root_for_target(&operation.target)?;
        let current = current_file_state(root, &operation.relative_path)?;
        if current.as_ref().map(|state| state.digest.clone()) != operation.expected_before_sha256 {
            return Err(HarnessError::new(
                io::ErrorKind::WouldBlock,
                format!(
                    "{}:{} changed since the approved plan",
                    operation.target, operation.relative_path
                ),
            ));
        }
        let backup_file = if let Some(state) = &current {
            let filename = format!("before-{index:06}.bin");
            write_atomic_file(
                &backup_dir.join(&filename),
                &state.bytes,
                &format!("backup-{index}"),
            )?;
            Some(format!(
                "backups/{}/{}",
                backup_dir.file_name().unwrap_or_default().to_string_lossy(),
                filename
            ))
        } else {
            None
        };
        match operation.action {
            PlanAction::Create | PlanAction::Update => {
                let source = operation
                    .source
                    .as_ref()
                    .ok_or_else(|| HarnessError::invalid("write operation has no source"))?;
                let source_root = self.source_root_for(source.root.as_str())?;
                let bytes = read_regular_file(source_root, &source.relative_path)?;
                let digest = sha256(&bytes);
                if digest != source.digest || Some(digest.clone()) != operation.after_sha256 {
                    return Err(HarnessError::new(
                        io::ErrorKind::WouldBlock,
                        "harness source changed since the plan was created",
                    ));
                }
                let target = target_path_for_write(root, &operation.relative_path)?;
                write_atomic_file(&target, &bytes, &format!("apply-{index}"))?;
            }
            PlanAction::Remove => {
                let target = target_path_for_write(root, &operation.relative_path)?;
                let metadata = fs::symlink_metadata(&target).map_err(HarnessError::from)?;
                if metadata.file_type().is_symlink() || !metadata.is_file() {
                    return Err(HarnessError::invalid(
                        "managed removal target must be a regular file",
                    ));
                }
                fs::remove_file(&target)?;
                sync_directory(target.parent().unwrap_or(root))?;
            }
        }
        Ok(ReceiptOperation {
            target: operation.target.clone(),
            ownership_key: operation.ownership_key.clone(),
            relative_path: operation.relative_path.clone(),
            action: operation.action.clone(),
            before_sha256: operation.expected_before_sha256.clone(),
            after_sha256: operation.after_sha256.clone(),
            backup_file,
            previous_owner: journal.entries.get(&operation.ownership_key).cloned(),
        })
    }

    fn restore_operations(
        &self,
        operations: &[ReceiptOperation],
        _journal: &OwnershipJournal,
    ) -> Result<()> {
        for operation in operations.iter().rev() {
            let root = self.root_for_target(&operation.target)?;
            let target = target_path_for_write(root, &operation.relative_path)?;
            match &operation.backup_file {
                Some(backup_file) => {
                    let backup = self.read_backup(backup_file)?;
                    write_atomic_file(&target, &backup, "rollback")?;
                }
                None => {
                    if let Ok(metadata) = fs::symlink_metadata(&target) {
                        if metadata.file_type().is_symlink() || !metadata.is_file() {
                            return Err(HarnessError::invalid(
                                "rollback target is not a regular file",
                            ));
                        }
                        fs::remove_file(&target)?;
                        sync_directory(target.parent().unwrap_or(root))?;
                    }
                }
            }
        }
        Ok(())
    }

    fn root_for_target(&self, target: &str) -> Result<&Path> {
        if target == "live" {
            return Ok(&self.roots.live_projection);
        }
        let host_id = target
            .strip_prefix("host:")
            .ok_or_else(|| HarnessError::invalid("invalid harness plan target"))?;
        self.roots
            .host_projections
            .iter()
            .find(|host| host.id == host_id)
            .map(|host| host.path.as_path())
            .ok_or_else(|| HarnessError::not_found("host projection root is missing"))
    }

    fn source_root_for(&self, source: &str) -> Result<&Path> {
        match source {
            "source_bundle" => Ok(&self.roots.source_bundle),
            "user_overlay" => Ok(&self.roots.user_overlay),
            "live" => Ok(&self.roots.live_projection),
            _ => Err(HarnessError::invalid("invalid harness plan source")),
        }
    }

    fn load_journal(&self) -> Result<OwnershipJournal> {
        let path = self.roots.state_dir.join(OWNERSHIP_FILE);
        if let Ok(metadata) = fs::symlink_metadata(&path) {
            if metadata.file_type().is_symlink() || !metadata.is_file() {
                return Err(HarnessError::invalid(
                    "harness ownership journal must be a regular file",
                ));
            }
        }
        let bytes = match fs::read(&path) {
            Ok(bytes) => bytes,
            Err(error) if error.kind() == io::ErrorKind::NotFound => {
                return Ok(OwnershipJournal {
                    schema: SCHEMA.to_owned(),
                    entries: BTreeMap::new(),
                })
            }
            Err(error) => return Err(error.into()),
        };
        let journal: OwnershipJournal = serde_json::from_slice(&bytes)?;
        if journal.schema != SCHEMA {
            return Err(HarnessError::new(
                io::ErrorKind::InvalidData,
                "unsupported harness ownership journal schema",
            ));
        }
        Ok(journal)
    }

    fn write_journal(&self, journal: &OwnershipJournal) -> Result<()> {
        let mut value = journal.clone();
        value.schema = SCHEMA.to_owned();
        ensure_directory(&self.roots.state_dir)?;
        let bytes = serde_json::to_vec_pretty(&value)?;
        write_atomic_file(
            &self.roots.state_dir.join(OWNERSHIP_FILE),
            &bytes,
            "ownership",
        )
    }

    fn write_receipt(&self, receipt: &HarnessReceipt) -> Result<()> {
        let receipts = self.roots.state_dir.join("receipts");
        ensure_directory(&receipts)?;
        let bytes = serde_json::to_vec_pretty(receipt)?;
        write_atomic_file(
            &receipts.join(format!("{}.json", receipt.receipt_id)),
            &bytes,
            "receipt",
        )
    }

    fn read_receipt(&self, receipt_id: &str) -> Result<HarnessReceipt> {
        let path = self
            .roots
            .state_dir
            .join("receipts")
            .join(format!("{receipt_id}.json"));
        let metadata = fs::symlink_metadata(&path)?;
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(HarnessError::invalid(
                "harness receipt must be a regular file",
            ));
        }
        let bytes = fs::read(path)?;
        let receipt: HarnessReceipt = serde_json::from_slice(&bytes)?;
        if receipt.schema != SCHEMA || receipt.receipt_id != receipt_id {
            return Err(HarnessError::new(
                io::ErrorKind::InvalidData,
                "invalid harness receipt",
            ));
        }
        Ok(receipt)
    }

    fn read_backup(&self, backup_file: &str) -> Result<Vec<u8>> {
        let relative = validate_relative(backup_file)?;
        if !relative.starts_with(Path::new("backups")) {
            return Err(HarnessError::invalid(
                "receipt backup escapes backup directory",
            ));
        }
        let path = self.roots.state_dir.join(relative);
        read_regular_file(
            &self.roots.state_dir,
            &path
                .strip_prefix(&self.roots.state_dir)
                .unwrap()
                .to_string_lossy(),
        )
    }
}

#[derive(Clone)]
struct DesiredFile {
    source: ProjectionSource,
    digest: String,
}

#[derive(Clone)]
struct FileState {
    bytes: Vec<u8>,
    digest: String,
}

fn build_plan(
    inventory: &HarnessInventory,
    target: &str,
    adapter: Option<HostAdapter>,
    current: &TreeInventory,
    desired: BTreeMap<String, DesiredFile>,
    mut blocks: Vec<PlanBlock>,
) -> Result<HarnessPlan> {
    let mut operations = Vec::new();
    let current_by_path: BTreeMap<_, _> = current
        .entries
        .iter()
        .map(|entry| (entry.path.clone(), entry))
        .collect();
    let mut desired_paths = BTreeSet::new();
    for (path, desired_file) in desired {
        desired_paths.insert(path.clone());
        let ownership_key = format!("{target}:{path}");
        match current_by_path.get(&path) {
            None => operations.push(PlanOperation {
                target: target.to_owned(),
                ownership_key,
                relative_path: path,
                action: PlanAction::Create,
                source: Some(desired_file.source),
                expected_before_sha256: None,
                after_sha256: Some(desired_file.digest),
            }),
            Some(existing)
                if matches!(existing.kind, TreeKind::File)
                    && existing.sha256.as_deref() == Some(desired_file.digest.as_str()) => {}
            Some(existing) if !matches!(existing.owner, InventoryOwner::Managed) => {
                blocks.push(PlanBlock {
                    target: target.to_owned(),
                    relative_path: path,
                    reason: "target exists but is not owned by the harness".to_owned(),
                    owner: Some(existing.owner.clone()),
                });
            }
            Some(existing) if !matches!(existing.kind, TreeKind::File) => {
                blocks.push(PlanBlock {
                    target: target.to_owned(),
                    relative_path: path,
                    reason: "target is not a regular file".to_owned(),
                    owner: Some(existing.owner.clone()),
                });
            }
            Some(existing) => operations.push(PlanOperation {
                target: target.to_owned(),
                ownership_key,
                relative_path: path,
                action: PlanAction::Update,
                source: Some(desired_file.source),
                expected_before_sha256: existing.sha256.clone(),
                after_sha256: Some(desired_file.digest),
            }),
        }
    }
    for existing in &current.entries {
        if desired_paths.contains(&existing.path) {
            continue;
        }
        if matches!(existing.owner, InventoryOwner::Managed)
            && matches!(existing.kind, TreeKind::File)
        {
            operations.push(PlanOperation {
                target: target.to_owned(),
                ownership_key: format!("{target}:{}", existing.path),
                relative_path: existing.path.clone(),
                action: PlanAction::Remove,
                source: None,
                expected_before_sha256: existing.sha256.clone(),
                after_sha256: None,
            });
        }
    }
    operations.sort_by(|left, right| left.relative_path.cmp(&right.relative_path));
    blocks.sort_by(|left, right| {
        (&left.target, &left.relative_path, &left.reason).cmp(&(
            &right.target,
            &right.relative_path,
            &right.reason,
        ))
    });
    Ok(HarnessPlan {
        schema: SCHEMA.to_owned(),
        plan_id: String::new(),
        inventory_fingerprint: inventory.fingerprint.clone(),
        target: target.to_owned(),
        adapter,
        operations,
        blocks,
    })
}

fn collect_desired_files(
    tree: &TreeInventory,
    root: &str,
    desired: &mut BTreeMap<String, DesiredFile>,
    blocks: &mut Vec<PlanBlock>,
) {
    for entry in &tree.entries {
        if matches!(entry.kind, TreeKind::Directory) {
            continue;
        }
        if !matches!(entry.kind, TreeKind::File) {
            blocks.push(PlanBlock {
                target: "live".to_owned(),
                relative_path: entry.path.clone(),
                reason: "source projection contains a non-regular entry".to_owned(),
                owner: Some(entry.owner.clone()),
            });
            continue;
        }
        let Some(digest) = entry.sha256.clone() else {
            blocks.push(PlanBlock {
                target: "live".to_owned(),
                relative_path: entry.path.clone(),
                reason: "source projection entry has no digest".to_owned(),
                owner: Some(entry.owner.clone()),
            });
            continue;
        };
        desired.insert(
            entry.path.clone(),
            DesiredFile {
                source: ProjectionSource {
                    root: root.to_owned(),
                    relative_path: entry.path.clone(),
                    digest: digest.clone(),
                },
                digest,
            },
        );
    }
}

fn projection_drift(
    source: &TreeInventory,
    overlay: &TreeInventory,
    live: &TreeInventory,
) -> Vec<DriftEntry> {
    let source_files = file_map(source);
    let overlay_files = file_map(overlay);
    let live_files = file_map(live);
    let mut drift = Vec::new();
    for (path, source_entry) in &source_files {
        if let Some(overlay_entry) = overlay_files.get(path) {
            if source_entry.sha256 != overlay_entry.sha256 {
                drift.push(DriftEntry {
                    scope: "live".to_owned(),
                    path: path.clone(),
                    kind: DriftKind::OverlayOverridesSource,
                    detail: "user overlay wins over managed source content".to_owned(),
                });
            }
        }
    }
    let mut desired = source_files;
    desired.extend(overlay_files);
    for (path, desired_entry) in &desired {
        match live_files.get(path) {
            None => drift.push(DriftEntry {
                scope: "live".to_owned(),
                path: path.clone(),
                kind: DriftKind::MissingLive,
                detail: "effective projection file is missing".to_owned(),
            }),
            Some(live_entry) if live_entry.sha256 != desired_entry.sha256 => {
                drift.push(DriftEntry {
                    scope: "live".to_owned(),
                    path: path.clone(),
                    kind: DriftKind::ContentDrift,
                    detail: "effective projection content differs from source plus overlay"
                        .to_owned(),
                })
            }
            Some(_) => {}
        }
    }
    for (path, entry) in &live_files {
        if !desired.contains_key(path) {
            drift.push(DriftEntry {
                scope: "live".to_owned(),
                path: path.clone(),
                kind: if matches!(entry.owner, InventoryOwner::Managed) {
                    DriftKind::ExtraManaged
                } else {
                    DriftKind::ExtraNonOwned
                },
                detail: "live projection contains content absent from the desired projection"
                    .to_owned(),
            });
        }
    }
    drift
}

fn file_map(tree: &TreeInventory) -> BTreeMap<String, InventoryEntry> {
    tree.entries
        .iter()
        .filter(|entry| matches!(entry.kind, TreeKind::File))
        .map(|entry| (entry.path.clone(), entry.clone()))
        .collect()
}

fn scan_tree(
    root: &Path,
    default_owner: InventoryOwner,
    managed: Option<(&BTreeMap<String, OwnedPathRecord>, &str)>,
) -> Result<TreeInventory> {
    let root_string = root.to_string_lossy().into_owned();
    let metadata = match fs::symlink_metadata(root) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => {
            return Ok(TreeInventory {
                root: root_string,
                exists: false,
                entries: Vec::new(),
            })
        }
        Err(error) => return Err(error.into()),
    };
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(HarnessError::invalid(
            "harness projection root must be a directory",
        ));
    }
    let mut entries = Vec::new();
    let mut total_bytes = 0;
    scan_directory(
        root,
        root,
        &default_owner,
        managed,
        &mut entries,
        &mut total_bytes,
    )?;
    entries.sort_by(|left, right| left.path.cmp(&right.path));
    Ok(TreeInventory {
        root: root_string,
        exists: true,
        entries,
    })
}

fn scan_directory(
    root: &Path,
    directory: &Path,
    default_owner: &InventoryOwner,
    managed: Option<(&BTreeMap<String, OwnedPathRecord>, &str)>,
    entries: &mut Vec<InventoryEntry>,
    total_bytes: &mut u64,
) -> Result<()> {
    let mut children = fs::read_dir(directory)?.collect::<io::Result<Vec<_>>>()?;
    children.sort_by_key(|entry| entry.file_name());
    for child in children {
        if entries.len() >= MAX_FILES {
            return Err(HarnessError::new(
                io::ErrorKind::InvalidData,
                "harness inventory file limit exceeded",
            ));
        }
        let path = child.path();
        let relative = path
            .strip_prefix(root)
            .map_err(|_| HarnessError::invalid("inventory path escaped root"))?;
        let relative = path_string(relative);
        let metadata = fs::symlink_metadata(&path)?;
        let owner = if let Some((journal, scope)) = managed {
            if journal.contains_key(&format!("{scope}:{relative}")) {
                InventoryOwner::Managed
            } else {
                default_owner.clone()
            }
        } else {
            default_owner.clone()
        };
        if metadata.file_type().is_symlink() {
            let target = fs::read_link(&path)?.to_string_lossy().into_owned();
            entries.push(InventoryEntry {
                path: relative,
                kind: TreeKind::Symlink,
                bytes: 0,
                sha256: Some(sha256(target.as_bytes())),
                link_target: Some(target),
                owner,
            });
        } else if metadata.is_dir() {
            entries.push(InventoryEntry {
                path: relative,
                kind: TreeKind::Directory,
                bytes: 0,
                sha256: None,
                link_target: None,
                owner,
            });
            scan_directory(root, &path, default_owner, managed, entries, total_bytes)?;
        } else if metadata.is_file() {
            if metadata.len() > MAX_FILE_BYTES
                || total_bytes.saturating_add(metadata.len()) > MAX_TOTAL_BYTES
            {
                return Err(HarnessError::new(
                    io::ErrorKind::InvalidData,
                    "harness inventory byte limit exceeded",
                ));
            }
            let digest = hash_file(&path)?;
            *total_bytes += metadata.len();
            entries.push(InventoryEntry {
                path: relative,
                kind: TreeKind::File,
                bytes: metadata.len(),
                sha256: Some(digest),
                link_target: None,
                owner,
            });
        } else {
            entries.push(InventoryEntry {
                path: relative,
                kind: TreeKind::Other,
                bytes: metadata.len(),
                sha256: None,
                link_target: None,
                owner,
            });
        }
    }
    Ok(())
}

fn current_file_state(root: &Path, relative: &str) -> Result<Option<FileState>> {
    match fs::symlink_metadata(root) {
        Ok(metadata) if metadata.file_type().is_symlink() || !metadata.is_dir() => {
            return Err(HarnessError::invalid("root must be a regular directory"));
        }
        Ok(_) => {}
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error.into()),
    }
    let path = target_path_for_read(root, relative)?;
    let metadata = match fs::symlink_metadata(&path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error.into()),
    };
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(HarnessError::invalid(
            "target must be a regular non-symlink file",
        ));
    }
    let bytes = read_bounded(&path)?;
    let digest = sha256(&bytes);
    Ok(Some(FileState { bytes, digest }))
}

fn read_regular_file(root: &Path, relative: &str) -> Result<Vec<u8>> {
    let path = target_path_for_read(root, relative)?;
    let metadata = fs::symlink_metadata(&path)?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(HarnessError::invalid(
            "source must be a regular non-symlink file",
        ));
    }
    read_bounded(&path)
}

fn read_bounded(path: &Path) -> Result<Vec<u8>> {
    let metadata = fs::symlink_metadata(path)?;
    if metadata.len() > MAX_FILE_BYTES {
        return Err(HarnessError::new(
            io::ErrorKind::InvalidData,
            "harness file exceeds size limit",
        ));
    }
    let mut file = File::open(path)?;
    let mut bytes = Vec::with_capacity(metadata.len() as usize);
    file.read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_FILE_BYTES {
        return Err(HarnessError::new(
            io::ErrorKind::InvalidData,
            "harness file exceeds size limit",
        ));
    }
    Ok(bytes)
}

fn hash_file(path: &Path) -> Result<String> {
    let metadata = fs::symlink_metadata(path)?;
    if metadata.len() > MAX_FILE_BYTES {
        return Err(HarnessError::new(
            io::ErrorKind::InvalidData,
            "harness file exceeds size limit",
        ));
    }
    let mut file = File::open(path)?;
    let mut digest = Sha256::new();
    let mut buffer = [0_u8; 16 * 1024];
    let mut total = 0_u64;
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        total += read as u64;
        if total > MAX_FILE_BYTES {
            return Err(HarnessError::new(
                io::ErrorKind::InvalidData,
                "harness file exceeds size limit",
            ));
        }
        digest.update(&buffer[..read]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn target_path_for_read(root: &Path, relative: &str) -> Result<PathBuf> {
    let relative = validate_relative(relative)?;
    validate_root(root)?;
    let path = root.join(relative);
    validate_existing_ancestors(root, path.parent().unwrap_or(root))?;
    Ok(path)
}

fn target_path_for_write(root: &Path, relative: &str) -> Result<PathBuf> {
    let relative = validate_relative(relative)?;
    ensure_directory(root)?;
    let path = root.join(&relative);
    let parent = path
        .parent()
        .ok_or_else(|| HarnessError::invalid("target has no parent directory"))?;
    ensure_directory_path(root, parent)?;
    if let Ok(metadata) = fs::symlink_metadata(&path) {
        if metadata.file_type().is_symlink() {
            return Err(HarnessError::invalid("target path cannot be a symlink"));
        }
    }
    Ok(path)
}

fn validate_root(root: &Path) -> Result<()> {
    let metadata = fs::symlink_metadata(root)?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(HarnessError::invalid("root must be a regular directory"));
    }
    Ok(())
}

fn ensure_directory(root: &Path) -> Result<()> {
    if let Ok(metadata) = fs::symlink_metadata(root) {
        if metadata.file_type().is_symlink() || !metadata.is_dir() {
            return Err(HarnessError::invalid(
                "managed directory must not be a symlink",
            ));
        }
        return Ok(());
    }
    validate_creation_ancestors(root)?;
    fs::create_dir_all(root)?;
    validate_root(root)
}

fn validate_creation_ancestors(path: &Path) -> Result<()> {
    if path
        .components()
        .any(|component| matches!(component, Component::ParentDir | Component::CurDir))
    {
        return Err(HarnessError::invalid(
            "directory creation path contains an unsafe component",
        ));
    }
    let mut current = path.to_path_buf();
    let mut missing = Vec::new();
    loop {
        match fs::symlink_metadata(&current) {
            Ok(metadata) => {
                if metadata.file_type().is_symlink() || !metadata.is_dir() {
                    return Err(HarnessError::invalid(
                        "directory creation path contains a symlink or non-directory",
                    ));
                }
                let canonical = fs::canonicalize(&current)?;
                let mut projected = canonical.clone();
                for component in missing.iter().rev() {
                    projected.push(component);
                }
                if !projected.starts_with(&canonical) {
                    return Err(HarnessError::invalid(
                        "directory creation path escaped root",
                    ));
                }
                return Ok(());
            }
            Err(error) if error.kind() == io::ErrorKind::NotFound => {
                let Some(parent) = current.parent() else {
                    return Err(HarnessError::not_found(
                        "directory creation parent is missing",
                    ));
                };
                missing.push(
                    current
                        .file_name()
                        .ok_or_else(|| HarnessError::invalid("directory creation path is invalid"))?
                        .to_owned(),
                );
                current = parent.to_path_buf();
            }
            Err(error) => return Err(error.into()),
        }
    }
}

fn ensure_directory_path(root: &Path, directory: &Path) -> Result<()> {
    ensure_directory(root)?;
    let canonical_root = fs::canonicalize(root)?;
    let relative = directory
        .strip_prefix(root)
        .map_err(|_| HarnessError::invalid("target directory escaped root"))?;
    validate_relative_allow_empty(relative)?;
    let mut current = root.to_path_buf();
    for component in relative.components() {
        let Component::Normal(name) = component else {
            return Err(HarnessError::invalid("invalid target directory component"));
        };
        current.push(name);
        match fs::symlink_metadata(&current) {
            Ok(metadata) if metadata.file_type().is_symlink() || !metadata.is_dir() => {
                return Err(HarnessError::invalid(
                    "target directory contains a symlink or non-directory",
                ));
            }
            Ok(_) => {}
            Err(error) if error.kind() == io::ErrorKind::NotFound => fs::create_dir(&current)?,
            Err(error) => return Err(error.into()),
        }
        if !fs::canonicalize(&current)?.starts_with(&canonical_root) {
            return Err(HarnessError::invalid("target directory escaped root"));
        }
    }
    Ok(())
}

fn validate_existing_ancestors(root: &Path, directory: &Path) -> Result<()> {
    validate_root(root)?;
    let canonical_root = fs::canonicalize(root)?;
    let relative = directory
        .strip_prefix(root)
        .map_err(|_| HarnessError::invalid("target directory escaped root"))?;
    validate_relative_allow_empty(relative)?;
    let mut current = root.to_path_buf();
    for component in relative.components() {
        let Component::Normal(name) = component else {
            return Err(HarnessError::invalid("invalid target directory component"));
        };
        current.push(name);
        let metadata = fs::symlink_metadata(&current).map_err(|error| {
            if error.kind() == io::ErrorKind::NotFound {
                HarnessError::not_found("target parent directory does not exist")
            } else {
                error.into()
            }
        })?;
        if metadata.file_type().is_symlink() || !metadata.is_dir() {
            return Err(HarnessError::invalid(
                "target parent directory contains a symlink or non-directory",
            ));
        }
        if !fs::canonicalize(&current)?.starts_with(&canonical_root) {
            return Err(HarnessError::invalid("target directory escaped root"));
        }
    }
    Ok(())
}

fn write_atomic_file(path: &Path, bytes: &[u8], token: &str) -> Result<()> {
    let parent = path
        .parent()
        .ok_or_else(|| HarnessError::invalid("atomic file has no parent"))?;
    ensure_directory(parent)?;
    let temp = parent.join(format!(".codinal-harness-{token}.tmp"));
    if let Ok(metadata) = fs::symlink_metadata(&temp) {
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(HarnessError::invalid("atomic temporary path is unsafe"));
        }
        fs::remove_file(&temp)?;
    }
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temp)?;
    file.write_all(bytes)?;
    file.sync_all()?;
    drop(file);
    fs::rename(&temp, path)?;
    sync_directory(parent)?;
    Ok(())
}

fn sync_directory(directory: &Path) -> Result<()> {
    File::open(directory)?.sync_all()?;
    Ok(())
}

fn fingerprint(inventory: &HarnessInventory) -> Result<String> {
    let mut value = inventory.clone();
    value.fingerprint.clear();
    Ok(short_hash(&serde_json::to_string(&value)?))
}

fn plan_id(plan: &HarnessPlan) -> Result<String> {
    let mut value = plan.clone();
    value.plan_id.clear();
    Ok(short_hash(&serde_json::to_string(&value)?))
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn short_hash(value: &str) -> String {
    sha256(value.as_bytes())[..32].to_owned()
}

fn path_string(path: &Path) -> String {
    path.to_string_lossy().replace('\\', "/")
}

fn validate_relative(value: &str) -> Result<PathBuf> {
    if value.is_empty() || value.len() > MAX_RELATIVE_PATH || value.contains('\0') {
        return Err(HarnessError::invalid("invalid relative harness path"));
    }
    let path = Path::new(value);
    validate_relative_allow_empty(path)?;
    Ok(path.to_path_buf())
}

fn validate_relative_allow_empty(path: &Path) -> Result<()> {
    for component in path.components() {
        if !matches!(component, Component::Normal(_)) {
            return Err(HarnessError::invalid(
                "relative path contains an unsafe component",
            ));
        }
    }
    Ok(())
}

fn validate_id(value: &str, name: &str) -> Result<()> {
    if value.is_empty()
        || value.len() > 128
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
    {
        return Err(HarnessError::invalid(format!("invalid {name} id")));
    }
    Ok(())
}

fn validate_host_id(value: &str) -> Result<()> {
    if value.is_empty()
        || value.len() > 64
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || matches!(byte, b'-'))
    {
        return Err(HarnessError::invalid("invalid host projection id"));
    }
    Ok(())
}

fn now_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::Path;

    fn temp_root(name: &str) -> PathBuf {
        let root = std::env::temp_dir().join(format!("codinal-harness-{name}-{}", now_ms()));
        fs::create_dir_all(&root).expect("temp root");
        root
    }

    fn roots(root: &Path) -> HarnessRoots {
        HarnessRoots {
            source_bundle: root.join("source"),
            user_overlay: root.join("overlay"),
            live_projection: root.join("live"),
            state_dir: root.join("state"),
            host_projections: vec![
                HostProjectionRoot::new(
                    "opencode",
                    root.join("opencode"),
                    HostAdapter::OpenCodeCli,
                    CapabilityStatus::Supported,
                )
                .expect("host"),
                HostProjectionRoot::new(
                    "cursor",
                    root.join("cursor"),
                    HostAdapter::Cursor,
                    CapabilityStatus::Unverified,
                )
                .expect("host"),
            ],
        }
    }

    fn write(path: &Path, contents: &[u8]) {
        fs::create_dir_all(path.parent().expect("parent")).expect("parent");
        fs::write(path, contents).expect("write");
    }

    fn approval(plan: &HarnessPlan) -> HarnessApproval {
        HarnessApproval::new(
            "approval-0123456789",
            plan.plan_id.clone(),
            now_ms().saturating_sub(1),
            now_ms() + 60_000,
        )
        .expect("approval")
    }

    #[test]
    fn scan_is_read_only_and_reports_ownership_and_drift() {
        let root = temp_root("scan");
        let roots = roots(&root);
        write(&roots.source_bundle.join("AGENTS.md"), b"source");
        write(&roots.user_overlay.join("local.md"), b"overlay");
        write(&roots.live_projection.join("AGENTS.md"), b"old");
        let manager = HarnessManager::new(roots.clone()).expect("manager");
        let before = fs::read_dir(&root).expect("root read").count();
        let inventory = manager.scan().expect("scan");
        assert!(!inventory.fingerprint.is_empty());
        assert!(inventory
            .drift
            .iter()
            .any(|entry| entry.kind == DriftKind::ContentDrift));
        assert_eq!(fs::read_dir(&root).expect("root read").count(), before);
        assert!(!roots.state_dir.exists());
    }

    #[test]
    fn plan_preserves_non_owned_files_and_user_overlay_wins() {
        let root = temp_root("plan");
        let roots = roots(&root);
        write(&roots.source_bundle.join("AGENTS.md"), b"source");
        write(&roots.user_overlay.join("AGENTS.md"), b"overlay");
        write(&roots.live_projection.join("AGENTS.md"), b"user-edited");
        write(&roots.live_projection.join("keep.txt"), b"keep");
        let manager = HarnessManager::new(roots).expect("manager");
        let inventory = manager.scan().expect("scan");
        let plan = manager.plan_live_projection(&inventory).expect("plan");
        assert!(plan.operations.is_empty());
        assert!(plan
            .blocks
            .iter()
            .any(|block| block.relative_path == "AGENTS.md"));
        assert!(plan
            .blocks
            .iter()
            .all(|block| block.reason.contains("not owned")));
    }

    #[test]
    fn approved_apply_is_atomic_owned_and_rolls_back() {
        let root = temp_root("apply");
        let roots = roots(&root);
        write(&roots.source_bundle.join("AGENTS.md"), b"source");
        fs::create_dir_all(&roots.live_projection).expect("live");
        let manager = HarnessManager::new(roots.clone()).expect("manager");
        let inventory = manager.scan().expect("scan");
        let plan = manager.plan_live_projection(&inventory).expect("plan");
        assert_eq!(plan.operations.len(), 1);
        let receipt = manager.apply(&plan, &approval(&plan)).expect("apply");
        assert_eq!(
            fs::read(roots.live_projection.join("AGENTS.md")).expect("read"),
            b"source"
        );
        assert!(manager.verify_receipt(&receipt).expect("verify").valid);
        let rolled_back = manager.rollback(&receipt.receipt_id).expect("rollback");
        assert!(rolled_back.rolled_back);
        assert!(!roots.live_projection.join("AGENTS.md").exists());
        assert!(
            manager
                .verify_receipt(&rolled_back)
                .expect("verify rollback")
                .valid
        );
    }

    #[test]
    fn apply_creates_missing_projection_root_and_never_deletes_overlay_source() {
        let root = temp_root("overlay");
        let roots = roots(&root);
        write(&roots.source_bundle.join("AGENTS.md"), b"source");
        write(&roots.user_overlay.join("local.md"), b"overlay");
        let manager = HarnessManager::new(roots.clone()).expect("manager");
        let inventory = manager.scan().expect("scan");
        let plan = manager.plan_live_projection(&inventory).expect("plan");
        manager.apply(&plan, &approval(&plan)).expect("apply");
        assert_eq!(
            fs::read(roots.user_overlay.join("local.md")).expect("overlay"),
            b"overlay"
        );
        assert_eq!(
            fs::read(roots.live_projection.join("local.md")).expect("projection"),
            b"overlay"
        );
    }

    #[test]
    fn malformed_host_target_is_byte_preserved_and_not_overwritten() {
        let root = temp_root("malformed-host");
        let roots = roots(&root);
        write(&roots.live_projection.join("AGENTS.md"), b"valid");
        write(
            &roots.host_projections[0].path.join("AGENTS.md"),
            b"{ malformed",
        );
        let manager = HarnessManager::new(roots.clone()).expect("manager");
        let inventory = manager.scan().expect("scan");
        let spec = HostProjectionSpec {
            adapter: HostAdapter::OpenCodeCli,
            files: vec![HostProjectionFile {
                source_relative: "AGENTS.md".to_owned(),
                target_relative: "AGENTS.md".to_owned(),
                mode: ProjectionWriteMode::Copy,
            }],
        };
        let plan = manager
            .plan_host_projection(&inventory, "opencode", &spec)
            .expect("plan");
        assert!(!plan.blocks.is_empty());
        assert!(manager.apply(&plan, &approval(&plan)).is_err());
        assert_eq!(
            fs::read(roots.host_projections[0].path.join("AGENTS.md")).expect("host"),
            b"{ malformed"
        );
    }

    #[test]
    fn removal_plan_only_removes_journal_owned_paths() {
        let root = temp_root("uninstall");
        let roots = roots(&root);
        write(&roots.source_bundle.join("managed.md"), b"managed");
        write(&roots.live_projection.join("unowned.md"), b"keep");
        let manager = HarnessManager::new(roots.clone()).expect("manager");
        let inventory = manager.scan().expect("scan");
        let plan = manager.plan_live_projection(&inventory).expect("plan");
        manager.apply(&plan, &approval(&plan)).expect("apply");
        fs::remove_file(roots.source_bundle.join("managed.md")).expect("remove source");
        let inventory = manager.scan().expect("rescan");
        let plan = manager
            .plan_live_projection(&inventory)
            .expect("removal plan");
        assert!(plan
            .operations
            .iter()
            .any(|operation| operation.relative_path == "managed.md"));
        manager
            .apply(&plan, &approval(&plan))
            .expect("remove managed");
        assert!(!roots.live_projection.join("managed.md").exists());
        assert_eq!(
            fs::read(roots.live_projection.join("unowned.md")).expect("unowned"),
            b"keep"
        );
    }

    #[test]
    fn source_drift_after_approval_fails_closed() {
        let root = temp_root("drift");
        let roots = roots(&root);
        write(&roots.source_bundle.join("AGENTS.md"), b"source");
        let manager = HarnessManager::new(roots.clone()).expect("manager");
        let inventory = manager.scan().expect("scan");
        let plan = manager.plan_live_projection(&inventory).expect("plan");
        write(&roots.source_bundle.join("AGENTS.md"), b"changed");
        assert!(manager.apply(&plan, &approval(&plan)).is_err());
        assert!(!roots.live_projection.join("AGENTS.md").exists());
    }

    #[test]
    fn unverified_host_cannot_be_written() {
        let root = temp_root("host");
        let roots = roots(&root);
        write(&roots.source_bundle.join("AGENTS.md"), b"source");
        write(&roots.live_projection.join("AGENTS.md"), b"source");
        let manager = HarnessManager::new(roots).expect("manager");
        let inventory = manager.scan().expect("scan");
        let spec = HostProjectionSpec {
            adapter: HostAdapter::Cursor,
            files: vec![HostProjectionFile {
                source_relative: "AGENTS.md".to_owned(),
                target_relative: "rules/AGENTS.md".to_owned(),
                mode: ProjectionWriteMode::Copy,
            }],
        };
        let plan = manager
            .plan_host_projection(&inventory, "cursor", &spec)
            .expect("plan");
        assert!(plan
            .blocks
            .iter()
            .any(|block| block.relative_path.is_empty()));
        assert!(manager.apply(&plan, &approval(&plan)).is_err());
    }

    #[cfg(unix)]
    #[test]
    fn symlinked_target_parent_is_rejected() {
        use std::os::unix::fs::symlink;
        let root = temp_root("symlink");
        let roots = roots(&root);
        write(&roots.source_bundle.join("AGENTS.md"), b"source");
        fs::create_dir_all(&roots.live_projection).expect("live");
        symlink(&root, roots.live_projection.join("escape")).expect("symlink");
        let manager = HarnessManager::new(roots).expect("manager");
        let inventory = manager.scan().expect("scan");
        let _ = manager.plan_live_projection(&inventory).expect("plan");
        assert!(target_path_for_write(&root.join("live"), "escape/out.txt").is_err());
    }
}
