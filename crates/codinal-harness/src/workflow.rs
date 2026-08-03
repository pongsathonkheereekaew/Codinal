use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::error::Error;
use std::fmt::{Display, Formatter};
use std::fs::{self, File, OpenOptions};
use std::io::{self, Write};
use std::path::{Component, Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

const SCHEMA: &str = "codinal.workflow.v1";
const MAX_TEXT: usize = 16 * 1024;
const MAX_ITEMS: usize = 512;

#[derive(Debug)]
pub struct WorkflowError {
    kind: io::ErrorKind,
    message: String,
}

impl WorkflowError {
    fn new(kind: io::ErrorKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
        }
    }

    fn invalid(message: impl Into<String>) -> Self {
        Self::new(io::ErrorKind::InvalidInput, message)
    }

    pub fn kind(&self) -> io::ErrorKind {
        self.kind
    }
}

impl Display for WorkflowError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(&self.message)
    }
}

impl Error for WorkflowError {}

impl From<io::Error> for WorkflowError {
    fn from(error: io::Error) -> Self {
        Self::new(error.kind(), error.to_string())
    }
}

impl From<serde_json::Error> for WorkflowError {
    fn from(error: serde_json::Error) -> Self {
        Self::new(io::ErrorKind::InvalidData, error.to_string())
    }
}

type Result<T> = std::result::Result<T, WorkflowError>;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum StageKind {
    Planner,
    Implementer,
    Reviewer,
}

impl StageKind {
    fn index(&self) -> usize {
        match self {
            Self::Planner => 0,
            Self::Implementer => 1,
            Self::Reviewer => 2,
        }
    }

    fn next(&self) -> Option<Self> {
        match self {
            Self::Planner => Some(Self::Implementer),
            Self::Implementer => Some(Self::Reviewer),
            Self::Reviewer => None,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProfileRoute {
    pub provider: String,
    pub model: String,
    pub effort: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct RoleProfile {
    pub role: StageKind,
    pub provider: String,
    pub model: String,
    pub effort: String,
    pub fallback: Option<ProfileRoute>,
    pub max_turn_tokens: u64,
}

impl RoleProfile {
    pub fn new(
        role: StageKind,
        provider: impl Into<String>,
        model: impl Into<String>,
        effort: impl Into<String>,
        fallback: Option<ProfileRoute>,
        max_turn_tokens: u64,
    ) -> Result<Self> {
        let profile = Self {
            role,
            provider: provider.into(),
            model: model.into(),
            effort: effort.into(),
            fallback,
            max_turn_tokens,
        };
        profile.validate()?;
        Ok(profile)
    }

    fn validate(&self) -> Result<()> {
        validate_text(&self.provider, "provider")?;
        validate_text(&self.model, "model")?;
        validate_text(&self.effort, "effort")?;
        if self.max_turn_tokens == 0 {
            return Err(WorkflowError::invalid(
                "role profile token limit must be positive",
            ));
        }
        if let Some(fallback) = &self.fallback {
            validate_text(&fallback.provider, "fallback provider")?;
            validate_text(&fallback.model, "fallback model")?;
            validate_text(&fallback.effort, "fallback effort")?;
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkflowBudget {
    pub max_tokens: u64,
    pub reserved_tokens: u64,
    pub used_tokens: u64,
    pub unknown_settlement_tokens: u64,
}

impl WorkflowBudget {
    pub fn new(max_tokens: u64) -> Result<Self> {
        if max_tokens == 0 {
            return Err(WorkflowError::invalid("workflow budget must be positive"));
        }
        Ok(Self {
            max_tokens,
            reserved_tokens: 0,
            used_tokens: 0,
            unknown_settlement_tokens: 0,
        })
    }

    fn reserve(&mut self, tokens: u64) -> Result<()> {
        if self
            .used_tokens
            .saturating_add(self.reserved_tokens)
            .saturating_add(tokens)
            > self.max_tokens
        {
            return Err(WorkflowError::new(
                io::ErrorKind::WouldBlock,
                "workflow budget would be exceeded",
            ));
        }
        self.reserved_tokens += tokens;
        Ok(())
    }

    fn settle(&mut self, reserved: u64, actual: Option<u64>) -> Result<()> {
        if reserved > self.reserved_tokens {
            return Err(WorkflowError::invalid(
                "workflow budget reservation is inconsistent",
            ));
        }
        let settled = actual.unwrap_or(reserved);
        if settled > reserved || self.used_tokens.saturating_add(settled) > self.max_tokens {
            return Err(WorkflowError::new(
                io::ErrorKind::WouldBlock,
                "workflow usage exceeds the approved budget",
            ));
        }
        self.reserved_tokens -= reserved;
        self.used_tokens += settled;
        if actual.is_none() {
            self.unknown_settlement_tokens += settled;
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkflowPlan {
    pub schema: String,
    pub workflow_id: String,
    pub objective: String,
    pub constraints: Vec<String>,
    pub roles: Vec<RoleProfile>,
    pub budget: WorkflowBudget,
}

impl WorkflowPlan {
    pub fn new(
        workflow_id: impl Into<String>,
        objective: impl Into<String>,
        constraints: Vec<String>,
        roles: Vec<RoleProfile>,
        budget: WorkflowBudget,
    ) -> Result<Self> {
        let plan = Self {
            schema: SCHEMA.to_owned(),
            workflow_id: workflow_id.into(),
            objective: objective.into(),
            constraints,
            roles,
            budget,
        };
        plan.validate()?;
        Ok(plan)
    }

    pub fn digest(&self) -> Result<String> {
        hash_json(self)
    }

    fn validate(&self) -> Result<()> {
        validate_id(&self.workflow_id, "workflow")?;
        validate_text(&self.objective, "workflow objective")?;
        if self.constraints.len() > MAX_ITEMS {
            return Err(WorkflowError::invalid("workflow constraint limit exceeded"));
        }
        for constraint in &self.constraints {
            validate_text(constraint, "workflow constraint")?;
        }
        if self.roles.len() != 3 {
            return Err(WorkflowError::invalid(
                "workflow requires Planner, Implementer, and Reviewer roles",
            ));
        }
        for (index, (role, expected)) in self.roles.iter().zip(required_stages()).enumerate() {
            role.validate()?;
            if role.role != expected {
                return Err(WorkflowError::invalid(format!(
                    "workflow role {} is not the required stage",
                    index + 1
                )));
            }
        }
        if self.budget.max_tokens == 0 {
            return Err(WorkflowError::invalid("workflow budget must be positive"));
        }
        Ok(())
    }

    fn role(&self, stage: &StageKind) -> &RoleProfile {
        &self.roles[stage.index()]
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkflowApproval {
    pub approval_id: String,
    pub plan_digest: String,
    pub approved_at_ms: u128,
    pub expires_at_ms: u128,
}

impl WorkflowApproval {
    pub fn new(
        approval_id: impl Into<String>,
        plan_digest: impl Into<String>,
        approved_at_ms: u128,
        expires_at_ms: u128,
    ) -> Result<Self> {
        let approval = Self {
            approval_id: approval_id.into(),
            plan_digest: plan_digest.into(),
            approved_at_ms,
            expires_at_ms,
        };
        validate_id(&approval.approval_id, "workflow approval")?;
        if approval.plan_digest.len() != 64 {
            return Err(WorkflowError::invalid("workflow plan digest is invalid"));
        }
        if approval.expires_at_ms <= approval.approved_at_ms {
            return Err(WorkflowError::invalid(
                "workflow approval expiry is invalid",
            ));
        }
        Ok(approval)
    }

    fn valid_for(&self, plan_digest: &str, now_ms: u128) -> bool {
        self.plan_digest == plan_digest
            && now_ms >= self.approved_at_ms
            && now_ms < self.expires_at_ms
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct ArtifactRef {
    pub path: String,
    pub sha256: String,
    pub owner: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct EvidenceRef {
    pub kind: String,
    pub command: String,
    pub result: String,
    pub artifact: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct DurableHandoff {
    pub objective: String,
    pub constraints: Vec<String>,
    pub plan: Vec<String>,
    pub changed_artifacts: Vec<ArtifactRef>,
    pub evidence: Vec<EvidenceRef>,
    pub unresolved_risks: Vec<String>,
}

impl DurableHandoff {
    pub fn initial(plan: &WorkflowPlan) -> Self {
        Self {
            objective: plan.objective.clone(),
            constraints: plan.constraints.clone(),
            plan: Vec::new(),
            changed_artifacts: Vec::new(),
            evidence: Vec::new(),
            unresolved_risks: Vec::new(),
        }
    }

    fn validate_against(&self, objective: &str) -> Result<()> {
        validate_text(&self.objective, "handoff objective")?;
        if self.objective != objective {
            return Err(WorkflowError::invalid(
                "handoff objective does not match workflow objective",
            ));
        }
        for collection in [&self.constraints, &self.plan, &self.unresolved_risks] {
            if collection.len() > MAX_ITEMS {
                return Err(WorkflowError::invalid("handoff item limit exceeded"));
            }
            for item in collection {
                validate_text(item, "handoff item")?;
            }
        }
        if self.changed_artifacts.len() > MAX_ITEMS || self.evidence.len() > MAX_ITEMS {
            return Err(WorkflowError::invalid("handoff evidence limit exceeded"));
        }
        for artifact in &self.changed_artifacts {
            validate_text(&artifact.path, "artifact path")?;
            validate_text(&artifact.owner, "artifact owner")?;
            if artifact.sha256.len() != 64 {
                return Err(WorkflowError::invalid("artifact digest is invalid"));
            }
        }
        for evidence in &self.evidence {
            validate_text(&evidence.kind, "evidence kind")?;
            validate_text(&evidence.command, "evidence command")?;
            validate_text(&evidence.result, "evidence result")?;
            if evidence
                .artifact
                .as_ref()
                .is_some_and(|artifact| artifact.len() > MAX_TEXT)
            {
                return Err(WorkflowError::invalid(
                    "evidence artifact reference is too long",
                ));
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum StageState {
    Pending,
    Running,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct StageOutcome {
    pub state: StageState,
    pub handoff: DurableHandoff,
    pub artifacts: Vec<ArtifactRef>,
    pub evidence: Vec<EvidenceRef>,
    pub usage_tokens: Option<u64>,
    pub verification_passed: bool,
    pub error: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct StageAttempt {
    pub attempt_id: String,
    pub stage: StageKind,
    pub attempt_number: u32,
    pub retry_of: Option<String>,
    pub profile: RoleProfile,
    pub state: StageState,
    pub handoff_in: DurableHandoff,
    pub handoff_out: Option<DurableHandoff>,
    pub artifacts: Vec<ArtifactRef>,
    pub evidence: Vec<EvidenceRef>,
    pub usage_tokens: Option<u64>,
    pub verification_passed: bool,
    pub error: Option<String>,
    pub started_at_ms: u128,
    pub ended_at_ms: Option<u128>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum WorkflowState {
    Planned,
    Running,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct EvaluationLedgerEntry {
    pub evaluation_id: String,
    pub workflow_id: String,
    pub stage: StageKind,
    pub attempt_id: String,
    pub provider: String,
    pub model: String,
    pub effort: String,
    pub usage_tokens: Option<u64>,
    pub latency_ms: Option<u64>,
    pub policy_failures: u32,
    pub rolled_back: bool,
    pub verification_passed: bool,
    pub created_at_ms: u128,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkflowRun {
    pub schema: String,
    pub run_id: String,
    pub plan: WorkflowPlan,
    pub plan_digest: String,
    pub approval_id: String,
    pub state: WorkflowState,
    pub current_stage: Option<StageKind>,
    pub attempts: Vec<StageAttempt>,
    pub budget: WorkflowBudget,
    pub created_at_ms: u128,
    pub updated_at_ms: u128,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkflowReceipt {
    pub schema: String,
    pub workflow_id: String,
    pub plan_digest: String,
    pub approval_id: String,
    pub state: WorkflowState,
    pub attempts: Vec<StageAttempt>,
    pub budget: WorkflowBudget,
    pub evaluations: Vec<EvaluationLedgerEntry>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
struct WorkflowDocument {
    schema: String,
    run: WorkflowRun,
    evaluations: Vec<EvaluationLedgerEntry>,
}

#[derive(Clone, Debug)]
pub struct WorkflowLedger {
    path: PathBuf,
    document: WorkflowDocument,
}

impl WorkflowLedger {
    pub fn create(
        path: impl Into<PathBuf>,
        plan: WorkflowPlan,
        approval: WorkflowApproval,
    ) -> Result<Self> {
        plan.validate()?;
        let path = path.into();
        validate_store_path(&path)?;
        if path.exists() {
            return Err(WorkflowError::new(
                io::ErrorKind::AlreadyExists,
                "workflow ledger already exists",
            ));
        }
        let plan_digest = plan.digest()?;
        if !approval.valid_for(&plan_digest, now_ms()) {
            return Err(WorkflowError::new(
                io::ErrorKind::PermissionDenied,
                "workflow approval is missing, mismatched, or expired",
            ));
        }
        let timestamp = now_ms();
        let document = WorkflowDocument {
            schema: SCHEMA.to_owned(),
            run: WorkflowRun {
                schema: SCHEMA.to_owned(),
                run_id: plan.workflow_id.clone(),
                plan: plan.clone(),
                plan_digest,
                approval_id: approval.approval_id,
                state: WorkflowState::Planned,
                current_stage: None,
                attempts: Vec::new(),
                budget: plan.budget.clone(),
                created_at_ms: timestamp,
                updated_at_ms: timestamp,
            },
            evaluations: Vec::new(),
        };
        let ledger = Self { path, document };
        ledger.persist()?;
        Ok(ledger)
    }

    pub fn open(path: impl Into<PathBuf>) -> Result<Self> {
        let path = path.into();
        validate_store_path(&path)?;
        let bytes = fs::read(&path)?;
        let document: WorkflowDocument = serde_json::from_slice(&bytes)?;
        if document.schema != SCHEMA || document.run.schema != SCHEMA {
            return Err(WorkflowError::new(
                io::ErrorKind::InvalidData,
                "unsupported workflow ledger schema",
            ));
        }
        document.run.plan.validate()?;
        Ok(Self { path, document })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn run(&self) -> &WorkflowRun {
        &self.document.run
    }

    pub fn evaluations(&self) -> &[EvaluationLedgerEntry] {
        &self.document.evaluations
    }

    pub fn start(&mut self) -> Result<()> {
        if !matches!(self.document.run.state, WorkflowState::Planned) {
            return Err(WorkflowError::new(
                io::ErrorKind::AlreadyExists,
                "workflow is already started or terminal",
            ));
        }
        self.document.run.state = WorkflowState::Running;
        self.document.run.current_stage = Some(StageKind::Planner);
        self.touch();
        self.persist()
    }

    pub fn begin_stage(&mut self, stage: StageKind) -> Result<StageAttempt> {
        if !matches!(self.document.run.state, WorkflowState::Running) {
            return Err(WorkflowError::new(
                io::ErrorKind::WouldBlock,
                "workflow is not running",
            ));
        }
        if self.document.run.current_stage.as_ref() != Some(&stage) {
            return Err(WorkflowError::new(
                io::ErrorKind::InvalidInput,
                "stage is not the next authorized workflow stage",
            ));
        }
        if self
            .document
            .run
            .attempts
            .iter()
            .any(|attempt| attempt.stage == stage && matches!(attempt.state, StageState::Running))
        {
            return Err(WorkflowError::new(
                io::ErrorKind::AlreadyExists,
                "workflow stage already has a running attempt",
            ));
        }
        let profile = self.document.run.plan.role(&stage).clone();
        let reservation = profile.max_turn_tokens;
        self.document.run.budget.reserve(reservation)?;
        let attempt_number = self
            .document
            .run
            .attempts
            .iter()
            .filter(|attempt| attempt.stage == stage)
            .count() as u32
            + 1;
        let retry_of = self
            .document
            .run
            .attempts
            .iter()
            .rev()
            .find(|attempt| attempt.stage == stage)
            .map(|attempt| attempt.attempt_id.clone());
        let handoff_in = self
            .document
            .run
            .attempts
            .iter()
            .rev()
            .find(|attempt| matches!(attempt.state, StageState::Completed))
            .and_then(|attempt| attempt.handoff_out.clone())
            .unwrap_or_else(|| DurableHandoff::initial(&self.document.run.plan));
        let attempt_id = short_hash(&format!(
            "{}:{}:{}:{}",
            self.document.run.run_id,
            stage.index(),
            attempt_number,
            self.document.run.attempts.len()
        ));
        let attempt = StageAttempt {
            attempt_id,
            stage,
            attempt_number,
            retry_of,
            profile,
            state: StageState::Running,
            handoff_in,
            handoff_out: None,
            artifacts: Vec::new(),
            evidence: Vec::new(),
            usage_tokens: None,
            verification_passed: false,
            error: None,
            started_at_ms: now_ms(),
            ended_at_ms: None,
        };
        self.document.run.attempts.push(attempt.clone());
        self.touch();
        self.persist()?;
        Ok(attempt)
    }

    pub fn complete_stage(
        &mut self,
        attempt_id: &str,
        outcome: StageOutcome,
    ) -> Result<StageAttempt> {
        validate_id(attempt_id, "stage attempt")?;
        let index = self
            .document
            .run
            .attempts
            .iter()
            .position(|attempt| attempt.attempt_id == attempt_id)
            .ok_or_else(|| {
                WorkflowError::new(io::ErrorKind::NotFound, "stage attempt not found")
            })?;
        let attempt = &self.document.run.attempts[index];
        if !matches!(attempt.state, StageState::Running) {
            return Err(WorkflowError::new(
                io::ErrorKind::AlreadyExists,
                "stage attempt is already terminal",
            ));
        }
        outcome
            .handoff
            .validate_against(&self.document.run.plan.objective)?;
        if outcome.artifacts.len() > MAX_ITEMS || outcome.evidence.len() > MAX_ITEMS {
            return Err(WorkflowError::invalid("stage output limit exceeded"));
        }
        if outcome
            .usage_tokens
            .is_some_and(|usage| usage > attempt.profile.max_turn_tokens)
        {
            return Err(WorkflowError::new(
                io::ErrorKind::WouldBlock,
                "stage usage exceeds the role profile budget",
            ));
        }
        if matches!(attempt.stage, StageKind::Reviewer)
            && matches!(outcome.state, StageState::Completed)
            && !outcome.verification_passed
        {
            return Err(WorkflowError::new(
                io::ErrorKind::PermissionDenied,
                "reviewer cannot complete without objective verification",
            ));
        }
        if !matches!(
            outcome.state,
            StageState::Completed | StageState::Failed | StageState::Cancelled
        ) {
            return Err(WorkflowError::invalid(
                "stage outcome must be completed, failed, or cancelled",
            ));
        }
        let reserved = attempt.profile.max_turn_tokens;
        self.document
            .run
            .budget
            .settle(reserved, outcome.usage_tokens)?;
        let state = outcome.state.clone();
        let stage = attempt.stage.clone();
        let updated = &mut self.document.run.attempts[index];
        updated.state = state.clone();
        updated.handoff_out = Some(outcome.handoff);
        updated.artifacts = outcome.artifacts;
        updated.evidence = outcome.evidence;
        updated.usage_tokens = outcome.usage_tokens;
        updated.verification_passed = outcome.verification_passed;
        updated.error = outcome.error;
        updated.ended_at_ms = Some(now_ms());
        match state {
            StageState::Completed => {
                if let Some(next) = stage.next() {
                    self.document.run.current_stage = Some(next);
                    self.document.run.state = WorkflowState::Running;
                } else {
                    self.document.run.current_stage = None;
                    self.document.run.state = WorkflowState::Completed;
                }
            }
            StageState::Failed => {
                self.document.run.current_stage = Some(stage);
                self.document.run.state = WorkflowState::Failed;
            }
            StageState::Cancelled => {
                self.document.run.current_stage = Some(stage);
                self.document.run.state = WorkflowState::Cancelled;
            }
            StageState::Pending | StageState::Running => unreachable!("validated above"),
        }
        self.touch();
        self.persist()?;
        Ok(self.document.run.attempts[index].clone())
    }

    pub fn retry_stage(&mut self, stage: StageKind) -> Result<StageAttempt> {
        if !matches!(
            self.document.run.state,
            WorkflowState::Failed | WorkflowState::Cancelled
        ) {
            return Err(WorkflowError::new(
                io::ErrorKind::WouldBlock,
                "only a failed or cancelled workflow can be retried",
            ));
        }
        if self.document.run.current_stage.as_ref() != Some(&stage) {
            return Err(WorkflowError::invalid("retry stage is not current"));
        }
        self.document.run.state = WorkflowState::Running;
        self.begin_stage(stage)
    }

    pub fn record_evaluation(&mut self, entry: EvaluationLedgerEntry) -> Result<()> {
        validate_id(&entry.evaluation_id, "evaluation")?;
        validate_id(&entry.attempt_id, "stage attempt")?;
        validate_text(&entry.provider, "evaluation provider")?;
        validate_text(&entry.model, "evaluation model")?;
        validate_text(&entry.effort, "evaluation effort")?;
        if entry.workflow_id != self.document.run.run_id {
            return Err(WorkflowError::invalid(
                "evaluation belongs to another workflow",
            ));
        }
        if self
            .document
            .evaluations
            .iter()
            .any(|candidate| candidate.evaluation_id == entry.evaluation_id)
        {
            return Err(WorkflowError::new(
                io::ErrorKind::AlreadyExists,
                "evaluation already recorded",
            ));
        }
        self.document.evaluations.push(entry);
        self.touch();
        self.persist()
    }

    pub fn receipt(&self) -> WorkflowReceipt {
        WorkflowReceipt {
            schema: SCHEMA.to_owned(),
            workflow_id: self.document.run.run_id.clone(),
            plan_digest: self.document.run.plan_digest.clone(),
            approval_id: self.document.run.approval_id.clone(),
            state: self.document.run.state.clone(),
            attempts: self.document.run.attempts.clone(),
            budget: self.document.run.budget.clone(),
            evaluations: self.document.evaluations.clone(),
        }
    }

    fn touch(&mut self) {
        self.document.run.updated_at_ms = now_ms();
    }

    fn persist(&self) -> Result<()> {
        let parent = self
            .path
            .parent()
            .ok_or_else(|| WorkflowError::invalid("workflow ledger has no parent"))?;
        ensure_directory(parent)?;
        let bytes = serde_json::to_vec_pretty(&self.document)?;
        let temp = parent.join(format!(
            ".codinal-workflow-{}.tmp",
            self.document.run.run_id
        ));
        if let Ok(metadata) = fs::symlink_metadata(&temp) {
            if metadata.file_type().is_symlink() || !metadata.is_file() {
                return Err(WorkflowError::invalid("workflow temporary path is unsafe"));
            }
            fs::remove_file(&temp)?;
        }
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temp)?;
        file.write_all(&bytes)?;
        file.sync_all()?;
        drop(file);
        fs::rename(&temp, &self.path)?;
        File::open(parent)?.sync_all()?;
        Ok(())
    }
}

fn required_stages() -> [StageKind; 3] {
    [
        StageKind::Planner,
        StageKind::Implementer,
        StageKind::Reviewer,
    ]
}

fn validate_store_path(path: &Path) -> Result<()> {
    if !path.is_absolute() {
        return Err(WorkflowError::invalid(
            "workflow ledger path must be absolute",
        ));
    }
    if path.to_string_lossy().contains('\0') {
        return Err(WorkflowError::invalid("workflow ledger path contains NUL"));
    }
    if path
        .components()
        .any(|component| matches!(component, Component::ParentDir | Component::CurDir))
    {
        return Err(WorkflowError::invalid(
            "workflow ledger path contains an unsafe component",
        ));
    }
    if let Ok(metadata) = fs::symlink_metadata(path) {
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(WorkflowError::invalid(
                "workflow ledger must be a regular file",
            ));
        }
    }
    Ok(())
}

fn ensure_directory(path: &Path) -> Result<()> {
    if let Ok(metadata) = fs::symlink_metadata(path) {
        if metadata.file_type().is_symlink() || !metadata.is_dir() {
            return Err(WorkflowError::invalid(
                "workflow parent must be a directory",
            ));
        }
        return Ok(());
    }
    validate_creation_ancestors(path)?;
    fs::create_dir_all(path)?;
    Ok(())
}

fn validate_creation_ancestors(path: &Path) -> Result<()> {
    let mut current = path.to_path_buf();
    loop {
        match fs::symlink_metadata(&current) {
            Ok(metadata) => {
                if metadata.file_type().is_symlink() || !metadata.is_dir() {
                    return Err(WorkflowError::invalid(
                        "workflow directory path contains a symlink or non-directory",
                    ));
                }
                return Ok(());
            }
            Err(error) if error.kind() == io::ErrorKind::NotFound => {
                current = current
                    .parent()
                    .ok_or_else(|| WorkflowError::invalid("workflow directory parent is missing"))?
                    .to_path_buf();
            }
            Err(error) => return Err(error.into()),
        }
    }
}

fn validate_text(value: &str, name: &str) -> Result<()> {
    if value.is_empty() || value.len() > MAX_TEXT || value.contains(['\r', '\n']) {
        return Err(WorkflowError::invalid(format!("invalid {name}")));
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
        return Err(WorkflowError::invalid(format!("invalid {name} id")));
    }
    Ok(())
}

fn hash_json<T: Serialize>(value: &T) -> Result<String> {
    let bytes = serde_json::to_vec(value)?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
}

fn short_hash(value: &str) -> String {
    format!("{:x}", Sha256::digest(value.as_bytes()))[..32].to_owned()
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

    fn temp_path(name: &str) -> PathBuf {
        let path = std::env::temp_dir().join(format!("codinal-workflow-{name}-{}", now_ms()));
        fs::create_dir_all(&path).expect("temp");
        path.join("workflow.json")
    }

    fn plan(max_tokens: u64) -> WorkflowPlan {
        WorkflowPlan::new(
            "workflow-1",
            "implement the requested change",
            vec!["preserve user-owned paths".to_owned()],
            vec![
                RoleProfile::new(
                    StageKind::Planner,
                    "opencode-go",
                    "kimi-k2.7-code",
                    "medium",
                    None,
                    100,
                )
                .expect("planner"),
                RoleProfile::new(
                    StageKind::Implementer,
                    "deepseek",
                    "deepseek-v4-pro",
                    "high",
                    None,
                    100,
                )
                .expect("implementer"),
                RoleProfile::new(
                    StageKind::Reviewer,
                    "opencode-go",
                    "kimi-k2.7-code",
                    "medium",
                    None,
                    100,
                )
                .expect("reviewer"),
            ],
            WorkflowBudget::new(max_tokens).expect("budget"),
        )
        .expect("plan")
    }

    fn approval(plan: &WorkflowPlan) -> WorkflowApproval {
        WorkflowApproval::new(
            "workflow-approval-1",
            plan.digest().expect("digest"),
            now_ms().saturating_sub(1),
            now_ms() + 60_000,
        )
        .expect("approval")
    }

    fn outcome(plan: &WorkflowPlan, passed: bool) -> StageOutcome {
        StageOutcome {
            state: StageState::Completed,
            handoff: DurableHandoff {
                objective: plan.objective.clone(),
                constraints: plan.constraints.clone(),
                plan: vec!["verify the result".to_owned()],
                changed_artifacts: Vec::new(),
                evidence: vec![EvidenceRef {
                    kind: "test".to_owned(),
                    command: "cargo test".to_owned(),
                    result: "passed".to_owned(),
                    artifact: None,
                }],
                unresolved_risks: Vec::new(),
            },
            artifacts: Vec::new(),
            evidence: Vec::new(),
            usage_tokens: Some(10),
            verification_passed: passed,
            error: None,
        }
    }

    #[test]
    fn durable_sequential_workflow_reloads_all_stage_attempts() {
        let path = temp_path("sequential");
        let plan = plan(500);
        let mut ledger =
            WorkflowLedger::create(&path, plan.clone(), approval(&plan)).expect("create");
        ledger.start().expect("start");
        for stage in [
            StageKind::Planner,
            StageKind::Implementer,
            StageKind::Reviewer,
        ] {
            let attempt = ledger.begin_stage(stage).expect("begin");
            ledger
                .complete_stage(&attempt.attempt_id, outcome(&plan, true))
                .expect("complete");
        }
        assert_eq!(ledger.run().state, WorkflowState::Completed);
        assert_eq!(ledger.run().budget.used_tokens, 30);
        let reloaded = WorkflowLedger::open(path).expect("reload");
        assert_eq!(reloaded.run().attempts.len(), 3);
        assert!(reloaded
            .run()
            .attempts
            .iter()
            .all(|attempt| matches!(attempt.state, StageState::Completed)));
    }

    #[test]
    fn retry_keeps_failed_attempt_immutable_and_respects_budget() {
        let path = temp_path("retry");
        let plan = plan(250);
        let mut ledger =
            WorkflowLedger::create(&path, plan.clone(), approval(&plan)).expect("create");
        ledger.start().expect("start");
        let attempt = ledger.begin_stage(StageKind::Planner).expect("begin");
        let mut failed = outcome(&plan, false);
        failed.state = StageState::Failed;
        failed.error = Some("verification failed".to_owned());
        ledger
            .complete_stage(&attempt.attempt_id, failed)
            .expect("fail");
        let retry = ledger.retry_stage(StageKind::Planner).expect("retry");
        assert_eq!(retry.retry_of.as_deref(), Some(attempt.attempt_id.as_str()));
        assert_eq!(
            ledger.run().attempts[0].error.as_deref(),
            Some("verification failed")
        );
        assert!(ledger.begin_stage(StageKind::Planner).is_err());
    }

    #[test]
    fn reviewer_cannot_complete_without_verification() {
        let path = temp_path("review");
        let plan = plan(500);
        let mut ledger =
            WorkflowLedger::create(&path, plan.clone(), approval(&plan)).expect("create");
        ledger.start().expect("start");
        let planner = ledger.begin_stage(StageKind::Planner).expect("planner");
        ledger
            .complete_stage(&planner.attempt_id, outcome(&plan, true))
            .expect("planner complete");
        let implementer = ledger
            .begin_stage(StageKind::Implementer)
            .expect("implementer");
        ledger
            .complete_stage(&implementer.attempt_id, outcome(&plan, true))
            .expect("implementer complete");
        let reviewer = ledger.begin_stage(StageKind::Reviewer).expect("reviewer");
        assert!(ledger
            .complete_stage(&reviewer.attempt_id, outcome(&plan, false))
            .is_err());
        assert!(matches!(
            ledger.run().attempts[2].state,
            StageState::Running
        ));
    }

    #[test]
    fn handoff_rejects_unknown_reasoning_field() {
        let value = serde_json::json!({
            "objective": "objective",
            "constraints": [],
            "plan": [],
            "changed_artifacts": [],
            "evidence": [],
            "unresolved_risks": [],
            "reasoning": "must not be stored"
        });
        assert!(serde_json::from_value::<DurableHandoff>(value).is_err());
    }

    #[test]
    fn evaluation_ledger_is_local_and_durable() {
        let path = temp_path("evaluation");
        let plan = plan(500);
        let mut ledger =
            WorkflowLedger::create(&path, plan.clone(), approval(&plan)).expect("create");
        ledger.start().expect("start");
        let attempt = ledger.begin_stage(StageKind::Planner).expect("begin");
        ledger
            .record_evaluation(EvaluationLedgerEntry {
                evaluation_id: "evaluation-1".to_owned(),
                workflow_id: plan.workflow_id.clone(),
                stage: StageKind::Planner,
                attempt_id: attempt.attempt_id,
                provider: "opencode-go".to_owned(),
                model: "kimi-k2.7-code".to_owned(),
                effort: "medium".to_owned(),
                usage_tokens: Some(10),
                latency_ms: Some(42),
                policy_failures: 0,
                rolled_back: false,
                verification_passed: true,
                created_at_ms: now_ms(),
            })
            .expect("evaluation");
        assert_eq!(
            WorkflowLedger::open(path)
                .expect("reload")
                .evaluations()
                .len(),
            1
        );
    }
}
