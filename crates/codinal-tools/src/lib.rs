//! Deny-by-default Rust tool execution for the C5 expansion stages.
//!
//! Shell, Git/worktree, and MCP calls share one boundary: validated paths,
//! explicit program/server allowlists, one-shot policy approval, bounded
//! interruptible execution, and an atomic receipt. Receipts contain metadata
//! and digests only; tool output stays in the caller's transient result.

use codinal_policy::{ApprovalChokepoint, Risk};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Component, Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

pub mod operation;

pub use operation::{
    OperationAck, OperationEnvelope, OperationLedger, OperationProgress, OperationReceipt,
    OperationResume, OperationState, OperationWork, OPERATION_SCHEMA,
};

const SCHEMA: &str = "codinal.tools.v1";
const MAX_ID_BYTES: usize = 128;
const MAX_TEXT_BYTES: usize = 8 * 1024;
const MAX_ARGUMENT_BYTES: usize = 32 * 1024;
const MAX_OUTPUT_BYTES: usize = 1024 * 1024;
const DEFAULT_TIMEOUT_MS: u64 = 30_000;
const MAX_TIMEOUT_MS: u64 = 300_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ToolClass {
    Shell,
    Git,
    Mcp,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ToolStatus {
    Pending,
    Succeeded,
    Failed,
    Interrupted,
    Rejected,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ToolRisk {
    Exec,
    WriteLocal,
    External,
}

impl ToolRisk {
    fn as_policy_risk(self) -> Risk {
        match self {
            Self::Exec => Risk::Exec,
            Self::WriteLocal => Risk::WriteLocal,
            Self::External => Risk::External,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ToolReceipt {
    pub schema: String,
    pub receipt_id: String,
    pub operation_id: String,
    pub tool: String,
    pub class: ToolClass,
    pub risk: ToolRisk,
    pub status: ToolStatus,
    pub started_at_ms: u128,
    pub finished_at_ms: Option<u128>,
    pub approval_required: bool,
    pub approval_consumed: bool,
    pub exit_code: Option<i32>,
    pub stdout_bytes: usize,
    pub stderr_bytes: usize,
    pub stdout_sha256: String,
    pub stderr_sha256: String,
    pub changed_paths: Vec<String>,
    pub output_truncated: bool,
    pub error_code: Option<String>,
}

impl ToolReceipt {
    pub fn pending(operation_id: &str, tool: &str, class: ToolClass, risk: ToolRisk) -> Self {
        Self {
            schema: SCHEMA.to_owned(),
            receipt_id: receipt_id_for(operation_id),
            operation_id: operation_id.to_owned(),
            tool: tool.to_owned(),
            class,
            risk,
            status: ToolStatus::Pending,
            started_at_ms: now_ms(),
            finished_at_ms: None,
            approval_required: true,
            approval_consumed: false,
            exit_code: None,
            stdout_bytes: 0,
            stderr_bytes: 0,
            stdout_sha256: digest_bytes(&[]),
            stderr_sha256: digest_bytes(&[]),
            changed_paths: Vec::new(),
            output_truncated: false,
            error_code: None,
        }
    }

    fn finish(
        mut self,
        status: ToolStatus,
        output: &ProcessOutput,
        changed_paths: Vec<String>,
        error_code: Option<String>,
    ) -> Self {
        self.status = status;
        self.finished_at_ms = Some(now_ms());
        self.exit_code = output.exit_code;
        self.stdout_bytes = output.stdout.len();
        self.stderr_bytes = output.stderr.len();
        self.stdout_sha256 = digest_bytes(&output.stdout);
        self.stderr_sha256 = digest_bytes(&output.stderr);
        self.changed_paths = changed_paths;
        self.output_truncated = output.stdout_truncated || output.stderr_truncated;
        self.error_code = error_code;
        self
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ToolExecution {
    pub receipt: ToolReceipt,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
    pub response: Option<serde_json::Value>,
}

#[derive(Debug, Clone)]
pub struct ToolConfig {
    pub workspace_root: PathBuf,
    pub state_dir: PathBuf,
    pub shell_programs: BTreeSet<String>,
    pub mcp_programs: BTreeSet<String>,
    pub max_output_bytes: usize,
}

impl ToolConfig {
    pub fn for_workspace(
        workspace_root: impl Into<PathBuf>,
        state_dir: impl Into<PathBuf>,
    ) -> Self {
        Self {
            workspace_root: workspace_root.into(),
            state_dir: state_dir.into(),
            shell_programs: ["pwd", "ls", "cat", "rg", "sleep"]
                .into_iter()
                .map(str::to_owned)
                .collect(),
            mcp_programs: BTreeSet::new(),
            max_output_bytes: MAX_OUTPUT_BYTES,
        }
    }

    pub fn with_shell_programs(
        mut self,
        programs: impl IntoIterator<Item = impl Into<String>>,
    ) -> Self {
        self.shell_programs = programs.into_iter().map(Into::into).collect();
        self
    }

    pub fn with_mcp_programs(
        mut self,
        programs: impl IntoIterator<Item = impl Into<String>>,
    ) -> Self {
        self.mcp_programs = programs.into_iter().map(Into::into).collect();
        self
    }
}

#[derive(Debug, Clone)]
pub struct ShellRequest {
    pub operation_id: String,
    pub cwd: PathBuf,
    pub program: String,
    pub args: Vec<String>,
    pub approval_id: Option<String>,
    pub timeout_ms: u64,
}

impl ShellRequest {
    pub fn new(operation_id: impl Into<String>, program: impl Into<String>) -> Self {
        Self {
            operation_id: operation_id.into(),
            cwd: PathBuf::new(),
            program: program.into(),
            args: Vec::new(),
            approval_id: None,
            timeout_ms: DEFAULT_TIMEOUT_MS,
        }
    }
}

#[derive(Debug, Clone)]
pub struct GitRequest {
    pub operation_id: String,
    pub repo: PathBuf,
    pub operation: GitOperation,
    pub approval_id: Option<String>,
    pub timeout_ms: u64,
}

#[derive(Debug, Clone)]
pub enum GitOperation {
    Status,
    Diff { path: Option<PathBuf> },
    CreateWorktree { path: PathBuf, revision: String },
    RemoveWorktree { path: PathBuf, force: bool },
}

#[derive(Debug, Clone)]
pub struct McpRequest {
    pub operation_id: String,
    pub server_id: String,
    pub program: String,
    pub args: Vec<String>,
    pub method: String,
    pub params: serde_json::Value,
    pub approval_id: Option<String>,
    pub timeout_ms: u64,
}

#[derive(Debug, Clone)]
struct ProcessOutput {
    stdout: Vec<u8>,
    stderr: Vec<u8>,
    stdout_truncated: bool,
    stderr_truncated: bool,
    exit_code: Option<i32>,
    interrupted: bool,
    timed_out: bool,
}

#[derive(Debug)]
struct CapturedOutput {
    bytes: Vec<u8>,
    truncated: bool,
}

struct ProcessInvocation {
    operation_id: String,
    approval_id: Option<String>,
    tool: String,
    class: ToolClass,
    risk: ToolRisk,
    timeout_ms: u64,
    cwd: PathBuf,
    program: String,
    args: Vec<String>,
    changed_paths: Vec<String>,
    cleanup_worktree: Option<PathBuf>,
}

struct ProcessSpec {
    cwd: PathBuf,
    program: String,
    args: Vec<String>,
    timeout_ms: u64,
    cancelled: Arc<AtomicBool>,
    max_output_bytes: usize,
}

struct McpProcessSpec {
    process: ProcessSpec,
    method: String,
    params: serde_json::Value,
}

#[derive(Clone)]
pub struct ToolGateway {
    config: Arc<ToolConfig>,
    receipts: Arc<ReceiptStore>,
    approvals: Arc<Mutex<ApprovalChokepoint>>,
    running: Arc<Mutex<BTreeMap<String, Arc<AtomicBool>>>>,
}

impl ToolGateway {
    pub fn new(config: ToolConfig) -> io::Result<Self> {
        validate_workspace_root(&config.workspace_root)?;
        if config.max_output_bytes == 0 || config.max_output_bytes > MAX_OUTPUT_BYTES {
            return Err(invalid("invalid tool output limit"));
        }
        let receipts = Arc::new(ReceiptStore::open(
            &config.state_dir,
            config.max_output_bytes,
        )?);
        receipts.recover_pending()?;
        Ok(Self {
            config: Arc::new(config),
            receipts,
            approvals: Arc::new(Mutex::new(ApprovalChokepoint::default())),
            running: Arc::new(Mutex::new(BTreeMap::new())),
        })
    }

    pub fn approve_once(&self, approval_id: &str) -> bool {
        self.approvals
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .approve_once(approval_id)
    }

    pub fn interrupt(&self, operation_id: &str) -> bool {
        self.running
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .get(operation_id)
            .is_some_and(|cancelled| {
                cancelled.store(true, Ordering::Release);
                true
            })
    }

    pub fn receipt(&self, operation_id: &str) -> io::Result<Option<ToolReceipt>> {
        self.receipts.find_by_operation(operation_id)
    }

    pub fn recover_pending(&self) -> io::Result<usize> {
        self.receipts.recover_pending()
    }

    pub fn execute_shell(&self, request: ShellRequest) -> io::Result<ToolExecution> {
        validate_operation_id(&request.operation_id)?;
        validate_timeout(request.timeout_ms)?;
        validate_program(&request.program, &self.config.shell_programs)?;
        let cwd = validate_workspace_path(&self.config.workspace_root, &request.cwd, false)?;
        validate_shell_arguments(&request.program, &request.args, &self.config.workspace_root)?;
        self.execute_process_tool(ProcessInvocation {
            operation_id: request.operation_id,
            approval_id: request.approval_id,
            tool: "shell".to_owned(),
            class: ToolClass::Shell,
            risk: ToolRisk::Exec,
            timeout_ms: request.timeout_ms,
            cwd,
            program: request.program,
            args: request.args,
            changed_paths: Vec::new(),
            cleanup_worktree: None,
        })
    }

    pub fn execute_git(&self, request: GitRequest) -> io::Result<ToolExecution> {
        validate_operation_id(&request.operation_id)?;
        validate_timeout(request.timeout_ms)?;
        let repo = validate_workspace_path(&self.config.workspace_root, &request.repo, false)?;
        if !repo.is_dir() {
            return Err(invalid("git repository path must be a directory"));
        }
        let (args, risk, changed_paths, cleanup_worktree) = match request.operation {
            GitOperation::Status => (
                vec!["status".to_owned(), "--short".to_owned()],
                ToolRisk::Exec,
                Vec::new(),
                None,
            ),
            GitOperation::Diff { path } => {
                let mut args = vec!["diff".to_owned(), "--".to_owned()];
                if let Some(path) = path {
                    validate_workspace_path(
                        &self.config.workspace_root,
                        &request.repo.join(&path),
                        true,
                    )?;
                    validate_relative_path(&path)?;
                    args.push(path_to_arg(&path)?);
                }
                (args, ToolRisk::Exec, Vec::new(), None)
            }
            GitOperation::CreateWorktree { path, revision } => {
                validate_revision(&revision)?;
                let target = validate_workspace_path(&self.config.workspace_root, &path, true)?;
                if target.exists() {
                    return Err(invalid("git worktree target already exists"));
                }
                let parent = target
                    .parent()
                    .ok_or_else(|| invalid("git worktree target has no parent"))?;
                validate_existing_directory(parent)?;
                (
                    vec![
                        "worktree".to_owned(),
                        "add".to_owned(),
                        "--detach".to_owned(),
                        target.to_string_lossy().into_owned(),
                        revision,
                    ],
                    ToolRisk::WriteLocal,
                    vec![relative_display(&self.config.workspace_root, &target)?],
                    Some(target),
                )
            }
            GitOperation::RemoveWorktree { path, force } => {
                let target = validate_workspace_path(&self.config.workspace_root, &path, false)?;
                if target == repo {
                    return Err(invalid("cannot remove the active git repository"));
                }
                let mut args = vec!["worktree".to_owned(), "remove".to_owned()];
                if force {
                    args.push("--force".to_owned());
                }
                args.push(target.to_string_lossy().into_owned());
                (
                    args,
                    ToolRisk::WriteLocal,
                    vec![relative_display(&self.config.workspace_root, &target)?],
                    None,
                )
            }
        };
        self.execute_process_tool(ProcessInvocation {
            operation_id: request.operation_id,
            approval_id: request.approval_id,
            tool: "git".to_owned(),
            class: ToolClass::Git,
            risk,
            timeout_ms: request.timeout_ms,
            cwd: repo,
            program: "git".to_owned(),
            args,
            changed_paths,
            cleanup_worktree,
        })
    }

    pub fn execute_mcp(&self, request: McpRequest) -> io::Result<ToolExecution> {
        validate_operation_id(&request.operation_id)?;
        validate_timeout(request.timeout_ms)?;
        validate_id(&request.server_id, "MCP server")?;
        validate_text(&request.method, "MCP method")?;
        validate_program(&request.program, &self.config.mcp_programs)?;
        validate_process_arguments(&request.args)?;
        let encoded_params = serde_json::to_vec(&request.params)?;
        if encoded_params.len() > MAX_ARGUMENT_BYTES {
            return Err(invalid("MCP parameters exceed limit"));
        }
        let cwd = self.config.workspace_root.clone();
        if !cwd.is_dir() {
            return Err(invalid("MCP workspace is not a directory"));
        }
        if let Some(existing) = self.receipts.find_by_operation(&request.operation_id)? {
            return Ok(ToolExecution {
                receipt: existing,
                stdout: Vec::new(),
                stderr: Vec::new(),
                response: None,
            });
        }
        let (mut receipt, approved) = self.begin_operation(
            &request.operation_id,
            &request.approval_id,
            "mcp",
            ToolClass::Mcp,
            ToolRisk::External,
        )?;
        if !approved {
            receipt.status = ToolStatus::Rejected;
            receipt.finished_at_ms = Some(now_ms());
            receipt.error_code = Some("approval_required".to_owned());
            self.receipts.write(&receipt)?;
            return Ok(ToolExecution {
                receipt,
                stdout: Vec::new(),
                stderr: Vec::new(),
                response: None,
            });
        }
        let cancelled = self.register_running(&request.operation_id)?;
        let result = run_mcp_process(McpProcessSpec {
            process: ProcessSpec {
                cwd,
                program: request.program,
                args: request.args,
                timeout_ms: request.timeout_ms,
                cancelled: Arc::clone(&cancelled),
                max_output_bytes: self.config.max_output_bytes,
            },
            method: request.method,
            params: request.params,
        });
        self.unregister_running(&request.operation_id);
        let output = match result {
            Ok(output) => output,
            Err(error) => {
                let process = ProcessOutput::empty();
                receipt = receipt.finish(
                    ToolStatus::Failed,
                    &process,
                    Vec::new(),
                    Some(error_code(&error)),
                );
                self.receipts.write(&receipt)?;
                return Ok(ToolExecution {
                    receipt,
                    stdout: Vec::new(),
                    stderr: Vec::new(),
                    response: None,
                });
            }
        };
        let response = parse_mcp_response(&output.stdout);
        let status = if output.interrupted || output.timed_out {
            ToolStatus::Interrupted
        } else if output.exit_code == Some(0) && response.is_ok() {
            ToolStatus::Succeeded
        } else {
            ToolStatus::Failed
        };
        let error_code = if output.interrupted {
            Some("interrupted".to_owned())
        } else if output.timed_out {
            Some("timeout".to_owned())
        } else if output.stdout_truncated || output.stderr_truncated {
            Some("output_limit_exceeded".to_owned())
        } else if response.is_err() {
            Some("invalid_mcp_response".to_owned())
        } else if output.exit_code != Some(0) {
            Some("process_failed".to_owned())
        } else {
            None
        };
        receipt = receipt.finish(status, &output, Vec::new(), error_code);
        self.receipts.write(&receipt)?;
        Ok(ToolExecution {
            receipt,
            stdout: output.stdout,
            stderr: output.stderr,
            response: response.ok(),
        })
    }

    fn execute_process_tool(&self, invocation: ProcessInvocation) -> io::Result<ToolExecution> {
        if let Some(existing) = self.receipts.find_by_operation(&invocation.operation_id)? {
            return Ok(ToolExecution {
                receipt: existing,
                stdout: Vec::new(),
                stderr: Vec::new(),
                response: None,
            });
        }
        let (mut receipt, approved) = self.begin_operation(
            &invocation.operation_id,
            &invocation.approval_id,
            &invocation.tool,
            invocation.class,
            invocation.risk,
        )?;
        if !approved {
            receipt.status = ToolStatus::Rejected;
            receipt.finished_at_ms = Some(now_ms());
            receipt.error_code = Some("approval_required".to_owned());
            self.receipts.write(&receipt)?;
            return Ok(ToolExecution {
                receipt,
                stdout: Vec::new(),
                stderr: Vec::new(),
                response: None,
            });
        }
        let cancelled = self.register_running(&invocation.operation_id)?;
        let result = run_process(ProcessSpec {
            cwd: invocation.cwd.clone(),
            program: invocation.program,
            args: invocation.args,
            timeout_ms: invocation.timeout_ms,
            cancelled: Arc::clone(&cancelled),
            max_output_bytes: self.config.max_output_bytes,
        });
        self.unregister_running(&invocation.operation_id);
        let output = match result {
            Ok(output) => output,
            Err(error) => {
                let process = ProcessOutput::empty();
                let recovered = invocation.cleanup_worktree.as_deref().is_none_or(|target| {
                    recover_failed_worktree(&invocation.cwd, target, self.config.max_output_bytes)
                });
                receipt = receipt.finish(
                    ToolStatus::Failed,
                    &process,
                    invocation.changed_paths,
                    Some(if recovered {
                        error_code(&error)
                    } else {
                        "partial_mutation_unrecovered".to_owned()
                    }),
                );
                self.receipts.write(&receipt)?;
                return Ok(ToolExecution {
                    receipt,
                    stdout: Vec::new(),
                    stderr: Vec::new(),
                    response: None,
                });
            }
        };
        let status = if output.interrupted || output.timed_out {
            ToolStatus::Interrupted
        } else if output.exit_code == Some(0)
            && !output.stdout_truncated
            && !output.stderr_truncated
        {
            ToolStatus::Succeeded
        } else {
            ToolStatus::Failed
        };
        let error_code = if output.interrupted {
            Some("interrupted".to_owned())
        } else if output.timed_out {
            Some("timeout".to_owned())
        } else if output.stdout_truncated || output.stderr_truncated {
            Some("output_limit_exceeded".to_owned())
        } else if output.exit_code != Some(0) {
            Some("process_failed".to_owned())
        } else {
            None
        };
        let error_code = if status != ToolStatus::Succeeded
            && invocation
                .cleanup_worktree
                .as_deref()
                .is_some_and(|target| {
                    !recover_failed_worktree(&invocation.cwd, target, self.config.max_output_bytes)
                }) {
            Some("partial_mutation_unrecovered".to_owned())
        } else {
            error_code
        };
        receipt = receipt.finish(status, &output, invocation.changed_paths, error_code);
        self.receipts.write(&receipt)?;
        Ok(ToolExecution {
            receipt,
            stdout: output.stdout,
            stderr: output.stderr,
            response: None,
        })
    }

    fn begin_operation(
        &self,
        operation_id: &str,
        approval_id: &Option<String>,
        tool: &str,
        class: ToolClass,
        risk: ToolRisk,
    ) -> io::Result<(ToolReceipt, bool)> {
        let receipt = ToolReceipt::pending(operation_id, tool, class, risk);
        self.receipts.write(&receipt)?;
        let approved = self
            .approvals
            .lock()
            .map_err(|_| io::Error::other("tool approval lock poisoned"))?
            .authorize(risk.as_policy_risk(), approval_id.as_deref());
        let mut receipt = receipt;
        receipt.approval_consumed = approved;
        self.receipts.write(&receipt)?;
        Ok((receipt, approved))
    }

    fn register_running(&self, operation_id: &str) -> io::Result<Arc<AtomicBool>> {
        let mut running = self
            .running
            .lock()
            .map_err(|_| io::Error::other("tool running lock poisoned"))?;
        if running.contains_key(operation_id) {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "tool operation is already running",
            ));
        }
        let cancelled = Arc::new(AtomicBool::new(false));
        running.insert(operation_id.to_owned(), Arc::clone(&cancelled));
        Ok(cancelled)
    }

    fn unregister_running(&self, operation_id: &str) {
        self.running
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .remove(operation_id);
    }
}

pub struct ReceiptStore {
    receipts_dir: PathBuf,
    max_output_bytes: usize,
}

impl ReceiptStore {
    pub fn open(state_dir: &Path, max_output_bytes: usize) -> io::Result<Self> {
        if !state_dir.is_absolute() {
            return Err(invalid("tool state directory must be absolute"));
        }
        ensure_directory(state_dir)?;
        let receipts_dir = state_dir.join("receipts");
        ensure_directory(&receipts_dir)?;
        Ok(Self {
            receipts_dir,
            max_output_bytes,
        })
    }

    pub fn find_by_operation(&self, operation_id: &str) -> io::Result<Option<ToolReceipt>> {
        validate_operation_id(operation_id)?;
        let path = self.path_for(operation_id)?;
        match self.read_path(&path) {
            Ok(receipt) if receipt.operation_id == operation_id => Ok(Some(receipt)),
            Ok(_) => Err(invalid("tool receipt operation identity mismatch")),
            Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(None),
            Err(error) => Err(error),
        }
    }

    pub fn write(&self, receipt: &ToolReceipt) -> io::Result<()> {
        validate_receipt(receipt)?;
        if receipt.stdout_bytes > self.max_output_bytes
            || receipt.stderr_bytes > self.max_output_bytes
        {
            return Err(invalid("tool receipt output exceeds configured limit"));
        }
        let path = self.path_for(&receipt.operation_id)?;
        if let Ok(existing) = self.read_path(&path) {
            if existing.operation_id != receipt.operation_id
                || existing.receipt_id != receipt.receipt_id
            {
                return Err(invalid("tool receipt identity collision"));
            }
            if existing.status != ToolStatus::Pending {
                return Ok(());
            }
        }
        let bytes = serde_json::to_vec_pretty(receipt)?;
        write_atomic(&path, &bytes, "tool receipt")
    }

    pub fn recover_pending(&self) -> io::Result<usize> {
        let mut recovered = 0;
        for entry in fs::read_dir(&self.receipts_dir)? {
            let entry = entry?;
            let path = entry.path();
            let metadata = fs::symlink_metadata(&path)?;
            if metadata.file_type().is_symlink() || !metadata.is_file() {
                return Err(invalid("tool receipt directory contains a non-file"));
            }
            if path.extension().and_then(|value| value.to_str()) != Some("json") {
                continue;
            }
            let mut receipt = self.read_path(&path)?;
            if receipt.status == ToolStatus::Pending {
                receipt.status = ToolStatus::Interrupted;
                receipt.finished_at_ms = Some(now_ms());
                receipt.error_code = Some("process_restarted".to_owned());
                self.write(&receipt)?;
                recovered += 1;
            }
        }
        Ok(recovered)
    }

    fn path_for(&self, operation_id: &str) -> io::Result<PathBuf> {
        Ok(self
            .receipts_dir
            .join(format!("{}.json", receipt_id_for(operation_id))))
    }

    fn read_path(&self, path: &Path) -> io::Result<ToolReceipt> {
        let metadata = fs::symlink_metadata(path)?;
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(invalid("tool receipt must be a regular file"));
        }
        let bytes = fs::read(path)?;
        let receipt: ToolReceipt = serde_json::from_slice(&bytes).map_err(|error| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                format!("invalid tool receipt: {error}"),
            )
        })?;
        validate_receipt(&receipt)?;
        Ok(receipt)
    }
}

fn validate_receipt(receipt: &ToolReceipt) -> io::Result<()> {
    if receipt.schema != SCHEMA
        || receipt.receipt_id != receipt_id_for(&receipt.operation_id)
        || receipt.operation_id.is_empty()
        || receipt.tool.is_empty()
    {
        return Err(invalid("invalid tool receipt identity"));
    }
    validate_operation_id(&receipt.operation_id)
}

fn run_process(spec: ProcessSpec) -> io::Result<ProcessOutput> {
    let mut command = base_command(&spec.cwd, &spec.program, &spec.args)?;
    let mut child = command.spawn()?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| invalid("missing stdout pipe"))?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| invalid("missing stderr pipe"))?;
    let stdout_thread = spawn_capture(stdout, spec.max_output_bytes);
    let stderr_thread = spawn_capture(stderr, spec.max_output_bytes);
    let (status, interrupted, timed_out) = wait_child(&mut child, spec.timeout_ms, spec.cancelled)?;
    let stdout = join_capture(stdout_thread)?;
    let stderr = join_capture(stderr_thread)?;
    Ok(ProcessOutput {
        stdout: stdout.bytes,
        stderr: stderr.bytes,
        stdout_truncated: stdout.truncated,
        stderr_truncated: stderr.truncated,
        exit_code: status.and_then(|status| status.code()),
        interrupted,
        timed_out,
    })
}

fn recover_failed_worktree(cwd: &Path, target: &Path, max_output_bytes: usize) -> bool {
    let Ok(metadata) = fs::symlink_metadata(target) else {
        return true;
    };
    if metadata.file_type().is_symlink() {
        return false;
    }
    let cleanup = run_process(ProcessSpec {
        cwd: cwd.to_owned(),
        program: "git".to_owned(),
        args: vec![
            "worktree".to_owned(),
            "remove".to_owned(),
            "--force".to_owned(),
            target.to_string_lossy().into_owned(),
        ],
        timeout_ms: 5_000,
        cancelled: Arc::new(AtomicBool::new(false)),
        max_output_bytes,
    });
    if cleanup
        .as_ref()
        .is_ok_and(|output| output.exit_code == Some(0) && !output.interrupted && !output.timed_out)
        && fs::symlink_metadata(target).is_err()
    {
        return true;
    }
    let removed = if metadata.is_dir() {
        fs::remove_dir_all(target)
    } else if metadata.is_file() {
        fs::remove_file(target)
    } else {
        return false;
    };
    removed.is_ok() && fs::symlink_metadata(target).is_err()
}

fn run_mcp_process(spec: McpProcessSpec) -> io::Result<ProcessOutput> {
    let mut command = base_command(&spec.process.cwd, &spec.process.program, &spec.process.args)?;
    let mut child = command.spawn()?;
    let mut stdin = child
        .stdin
        .take()
        .ok_or_else(|| invalid("missing MCP stdin pipe"))?;
    let request = serde_json::json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": spec.method,
        "params": spec.params,
    });
    let encoded = serde_json::to_vec(&request)?;
    stdin.write_all(&encoded)?;
    stdin.write_all(b"\n")?;
    stdin.flush()?;
    drop(stdin);
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| invalid("missing stdout pipe"))?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| invalid("missing stderr pipe"))?;
    let stdout_thread = spawn_capture(stdout, spec.process.max_output_bytes);
    let stderr_thread = spawn_capture(stderr, spec.process.max_output_bytes);
    let (status, interrupted, timed_out) =
        wait_child(&mut child, spec.process.timeout_ms, spec.process.cancelled)?;
    let stdout = join_capture(stdout_thread)?;
    let stderr = join_capture(stderr_thread)?;
    Ok(ProcessOutput {
        stdout: stdout.bytes,
        stderr: stderr.bytes,
        stdout_truncated: stdout.truncated,
        stderr_truncated: stderr.truncated,
        exit_code: status.and_then(|status| status.code()),
        interrupted,
        timed_out,
    })
}

fn base_command(cwd: &Path, program: &str, args: &[String]) -> io::Result<Command> {
    validate_process_arguments(args)?;
    let mut command = Command::new(program);
    command
        .args(args)
        .current_dir(cwd)
        .env_clear()
        .env("PATH", std::env::var_os("PATH").unwrap_or_default())
        .env("LC_ALL", "C")
        .env("GIT_TERMINAL_PROMPT", "0")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    Ok(command)
}

fn wait_child(
    child: &mut Child,
    timeout_ms: u64,
    cancelled: Arc<AtomicBool>,
) -> io::Result<(Option<std::process::ExitStatus>, bool, bool)> {
    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    let mut interrupted = false;
    let mut timed_out = false;
    loop {
        if let Some(status) = child.try_wait()? {
            return Ok((Some(status), interrupted, timed_out));
        }
        if cancelled.load(Ordering::Acquire) {
            interrupted = true;
            let _ = child.kill();
            return Ok((Some(child.wait()?), interrupted, timed_out));
        }
        if Instant::now() >= deadline {
            timed_out = true;
            let _ = child.kill();
            return Ok((Some(child.wait()?), interrupted, timed_out));
        }
        thread::sleep(Duration::from_millis(10));
    }
}

fn spawn_capture<R>(reader: R, max_output_bytes: usize) -> JoinHandle<io::Result<CapturedOutput>>
where
    R: Read + Send + 'static,
{
    thread::spawn(move || {
        let mut reader = reader;
        let mut bytes = Vec::new();
        let mut buffer = [0_u8; 8192];
        let mut truncated = false;
        loop {
            let read = reader.read(&mut buffer)?;
            if read == 0 {
                break;
            }
            if bytes.len() < max_output_bytes {
                let remaining = max_output_bytes - bytes.len();
                bytes.extend_from_slice(&buffer[..read.min(remaining)]);
            }
            if bytes.len() >= max_output_bytes
                && read > max_output_bytes.saturating_sub(bytes.len())
            {
                truncated = true;
            }
        }
        Ok(CapturedOutput { bytes, truncated })
    })
}

fn join_capture(handle: JoinHandle<io::Result<CapturedOutput>>) -> io::Result<CapturedOutput> {
    handle
        .join()
        .map_err(|_| io::Error::other("tool output reader panicked"))?
}

fn parse_mcp_response(bytes: &[u8]) -> io::Result<serde_json::Value> {
    let line = bytes
        .split(|byte| *byte == b'\n')
        .find(|line| !line.is_empty())
        .ok_or_else(|| invalid("MCP response is empty"))?;
    let value: serde_json::Value = serde_json::from_slice(line)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
    if value.get("jsonrpc") != Some(&serde_json::Value::String("2.0".to_owned()))
        || value.get("id") != Some(&serde_json::Value::from(1))
        || (value.get("result").is_none() && value.get("error").is_none())
    {
        return Err(invalid("invalid MCP JSON-RPC response"));
    }
    Ok(value)
}

fn validate_workspace_root(root: &Path) -> io::Result<()> {
    if !root.is_absolute() {
        return Err(invalid("workspace root must be absolute"));
    }
    validate_existing_directory(root)
}

fn validate_workspace_path(
    root: &Path,
    relative: &Path,
    allow_missing: bool,
) -> io::Result<PathBuf> {
    validate_relative_path(relative)?;
    let mut current = root.to_path_buf();
    let components = relative.components().collect::<Vec<_>>();
    for (index, component) in components.iter().enumerate() {
        let Component::Normal(name) = component else {
            return Err(invalid("workspace path contains an unsafe component"));
        };
        current.push(name);
        match fs::symlink_metadata(&current) {
            Ok(metadata) => {
                if metadata.file_type().is_symlink() {
                    return Err(invalid("workspace path crosses a symlink"));
                }
            }
            Err(error) if error.kind() == io::ErrorKind::NotFound => {
                if allow_missing && index + 1 == components.len() {
                    break;
                }
                return Err(error);
            }
            Err(error) => return Err(error),
        }
    }
    Ok(current)
}

fn validate_relative_path(path: &Path) -> io::Result<()> {
    if path.is_absolute() || path.to_string_lossy().contains('\0') {
        return Err(invalid("path must be relative and NUL-free"));
    }
    for component in path.components() {
        if !matches!(component, Component::Normal(_)) {
            return Err(invalid("path contains an unsafe component"));
        }
    }
    Ok(())
}

fn validate_existing_directory(path: &Path) -> io::Result<()> {
    let metadata = fs::symlink_metadata(path)?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(invalid("path must be a regular directory"));
    }
    Ok(())
}

fn validate_program(program: &str, allowlist: &BTreeSet<String>) -> io::Result<()> {
    validate_text(program, "program")?;
    if program.contains('/') || !allowlist.contains(program) {
        return Err(invalid("program is not in the explicit tool allowlist"));
    }
    Ok(())
}

fn validate_shell_arguments(program: &str, args: &[String], root: &Path) -> io::Result<()> {
    validate_process_arguments(args)?;
    match program {
        "pwd" => {
            if !args.is_empty() {
                return Err(invalid("pwd does not accept arguments"));
            }
        }
        "sleep" => {
            if args.len() != 1 || !args[0].chars().all(|character| character.is_ascii_digit()) {
                return Err(invalid("sleep requires one bounded numeric argument"));
            }
        }
        "cat" | "ls" => {
            if args.is_empty() {
                return Err(invalid("file command requires a path"));
            }
            for arg in args {
                if arg.starts_with('-') {
                    if arg.contains('=') {
                        return Err(invalid("file command flag values are not allowed"));
                    }
                    continue;
                }
                validate_workspace_path(root, Path::new(arg), true)?;
            }
        }
        "rg" => {
            if args.is_empty() {
                return Err(invalid("search command requires a pattern"));
            }
            for (index, arg) in args.iter().enumerate() {
                if arg.starts_with('-') {
                    if arg.contains('=') {
                        return Err(invalid("search flag values are not allowed"));
                    }
                } else if index > 0 {
                    validate_workspace_path(root, Path::new(arg), true)?;
                }
            }
        }
        _ => {
            for arg in args {
                if arg.contains('/') || arg.contains('\\') || arg.contains("..") {
                    return Err(invalid("arbitrary shell path argument is not allowed"));
                }
            }
        }
    }
    Ok(())
}

fn validate_process_arguments(args: &[String]) -> io::Result<()> {
    let total = args.iter().try_fold(0_usize, |total, arg| {
        validate_text(arg, "process argument")?;
        total
            .checked_add(arg.len() + 1)
            .ok_or_else(|| invalid("process argument size overflow"))
    })?;
    if total > MAX_ARGUMENT_BYTES {
        return Err(invalid("process arguments exceed limit"));
    }
    Ok(())
}

fn validate_revision(revision: &str) -> io::Result<()> {
    validate_text(revision, "git revision")?;
    if revision.starts_with('-') || revision.contains(['\r', '\n', '\0']) {
        return Err(invalid("git revision is unsafe"));
    }
    Ok(())
}

fn path_to_arg(path: &Path) -> io::Result<String> {
    validate_relative_path(path)?;
    Ok(path.to_string_lossy().into_owned())
}

fn relative_display(root: &Path, path: &Path) -> io::Result<String> {
    path.strip_prefix(root)
        .map(|path| path.to_string_lossy().into_owned())
        .map_err(|_| invalid("changed path escaped workspace root"))
}

fn ensure_directory(path: &Path) -> io::Result<()> {
    if !path.is_absolute() {
        return Err(invalid("owned directory must be absolute"));
    }
    if let Ok(metadata) = fs::symlink_metadata(path) {
        if metadata.file_type().is_symlink() || !metadata.is_dir() {
            return Err(invalid("owned directory is not a regular directory"));
        }
        return Ok(());
    }
    let mut current = path.to_path_buf();
    loop {
        match fs::symlink_metadata(&current) {
            Ok(metadata) => {
                if metadata.file_type().is_symlink() || !metadata.is_dir() {
                    return Err(invalid("owned directory parent is unsafe"));
                }
                break;
            }
            Err(error) if error.kind() == io::ErrorKind::NotFound => {
                current = current
                    .parent()
                    .ok_or_else(|| invalid("owned directory has no parent"))?
                    .to_path_buf();
            }
            Err(error) => return Err(error),
        }
    }
    fs::create_dir_all(path)?;
    Ok(())
}

fn write_atomic(path: &Path, bytes: &[u8], label: &str) -> io::Result<()> {
    let parent = path
        .parent()
        .ok_or_else(|| invalid("atomic file has no parent"))?;
    ensure_directory(parent)?;
    if let Ok(metadata) = fs::symlink_metadata(path) {
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(invalid(format!("{label} target is not a regular file")));
        }
    }
    let temp = parent.join(format!(".codinal-tool-{}.tmp", unique_suffix()));
    let mut file = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&temp)?;
    file.write_all(bytes)?;
    file.sync_all()?;
    drop(file);
    fs::rename(&temp, path)?;
    File::open(parent)?.sync_all()?;
    Ok(())
}

fn unique_suffix() -> String {
    format!("{}-{}", now_ms(), std::process::id())
}

fn validate_operation_id(value: &str) -> io::Result<()> {
    operation::validate_operation_id(value)
}

fn validate_id(value: &str, label: &str) -> io::Result<()> {
    if value.is_empty()
        || value.len() > MAX_ID_BYTES
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.'))
    {
        return Err(invalid(format!("invalid {label} id")));
    }
    Ok(())
}

fn validate_text(value: &str, label: &str) -> io::Result<()> {
    if value.is_empty() || value.len() > MAX_TEXT_BYTES || value.contains(['\r', '\n', '\0']) {
        return Err(invalid(format!("invalid {label}")));
    }
    Ok(())
}

fn validate_timeout(timeout_ms: u64) -> io::Result<()> {
    if timeout_ms == 0 || timeout_ms > MAX_TIMEOUT_MS {
        return Err(invalid("tool timeout is outside the bounded range"));
    }
    Ok(())
}

fn error_code(error: &io::Error) -> String {
    match error.kind() {
        io::ErrorKind::PermissionDenied => "permission_denied",
        io::ErrorKind::InvalidInput => "invalid_input",
        io::ErrorKind::InvalidData => "invalid_data",
        io::ErrorKind::NotFound => "not_found",
        io::ErrorKind::TimedOut => "timeout",
        _ => "execution_error",
    }
    .to_owned()
}

fn receipt_id_for(operation_id: &str) -> String {
    let mut digest = Sha256::new();
    digest.update(operation_id.as_bytes());
    format!("{:x}", digest.finalize())[..32].to_owned()
}

fn digest_bytes(bytes: &[u8]) -> String {
    let mut digest = Sha256::new();
    digest.update(bytes);
    format!("{:x}", digest.finalize())
}

fn now_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |duration| duration.as_millis())
}

fn invalid(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, message.into())
}

impl ProcessOutput {
    fn empty() -> Self {
        Self {
            stdout: Vec::new(),
            stderr: Vec::new(),
            stdout_truncated: false,
            stderr_truncated: false,
            exit_code: None,
            interrupted: false,
            timed_out: false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::Duration;

    static NEXT_TEST_ID: AtomicU64 = AtomicU64::new(1);
    const APPROVAL: &str = "tool-approval-token-123456";

    fn temp_root(name: &str) -> PathBuf {
        let path = std::env::temp_dir().join(format!(
            "codinal-tools-{name}-{}-{}",
            std::process::id(),
            NEXT_TEST_ID.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&path).expect("temp root");
        path
    }

    fn gateway(name: &str) -> (ToolGateway, PathBuf) {
        let root = temp_root(name);
        let state = root.join("state");
        let config = ToolConfig::for_workspace(&root, state);
        (ToolGateway::new(config).expect("gateway"), root)
    }

    fn approved_shell(gateway: &ToolGateway, operation_id: &str, program: &str) -> ShellRequest {
        let mut request = ShellRequest::new(operation_id, program);
        request.approval_id = Some(APPROVAL.to_owned());
        assert!(gateway.approve_once(APPROVAL));
        request
    }

    #[test]
    fn shell_requires_approval_and_receipt_is_idempotent() {
        let (gateway, root) = gateway("shell");
        fs::write(root.join("hello.txt"), b"hello\\n").expect("file");
        let mut rejected = ShellRequest::new("shell-rejected", "cat");
        rejected.args = vec!["hello.txt".to_owned()];
        let rejected = gateway.execute_shell(rejected).expect("receipt");
        assert_eq!(rejected.receipt.status, ToolStatus::Rejected);
        assert!(rejected.stdout.is_empty());

        let mut request = approved_shell(&gateway, "shell-approved", "cat");
        request.args = vec!["hello.txt".to_owned()];
        let first = gateway.execute_shell(request.clone()).expect("execution");
        assert_eq!(first.receipt.status, ToolStatus::Succeeded);
        assert_eq!(first.stdout, b"hello\\n");
        let second = gateway.execute_shell(request).expect("replay");
        assert_eq!(second.receipt.receipt_id, first.receipt.receipt_id);
        assert!(second.stdout.is_empty());
    }

    #[test]
    fn shell_rejects_escape_paths_and_symlink_boundaries() {
        let (gateway, root) = gateway("boundary");
        let mut parent_escape = ShellRequest::new("shell-parent", "cat");
        parent_escape.args = vec!["../outside".to_owned()];
        assert_eq!(
            gateway
                .execute_shell(parent_escape)
                .expect_err("escape")
                .kind(),
            io::ErrorKind::InvalidInput
        );

        #[cfg(unix)]
        {
            let outside = temp_root("outside");
            fs::write(outside.join("secret.txt"), b"secret").expect("secret");
            std::os::unix::fs::symlink(&outside, root.join("link")).expect("symlink");
            let mut request = ShellRequest::new("shell-symlink", "cat");
            request.args = vec!["link/secret.txt".to_owned()];
            assert!(gateway.execute_shell(request).is_err());
        }
    }

    #[test]
    fn shell_interrupt_writes_terminal_receipt() {
        let (gateway, _root) = gateway("interrupt");
        let mut request = approved_shell(&gateway, "shell-interrupt", "sleep");
        request.args = vec!["10".to_owned()];
        request.timeout_ms = 20_000;
        let worker_gateway = gateway.clone();
        let worker = thread::spawn(move || worker_gateway.execute_shell(request));
        for _ in 0..100 {
            if gateway.interrupt("shell-interrupt") {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        let result = worker.join().expect("worker").expect("receipt");
        assert_eq!(result.receipt.status, ToolStatus::Interrupted);
        assert_eq!(result.receipt.error_code.as_deref(), Some("interrupted"));
    }

    #[test]
    fn shell_output_limit_and_timeout_are_terminal_and_bounded() {
        let root = temp_root("limits");
        let mut config = ToolConfig::for_workspace(&root, root.join("state"))
            .with_shell_programs(["printf", "sleep"]);
        config.max_output_bytes = 32;
        let gateway = ToolGateway::new(config).expect("gateway");

        let mut output_request = ShellRequest::new("shell-output-limit", "printf");
        output_request.args = vec!["%s".to_owned(), "A".repeat(128)];
        output_request.approval_id = Some("approval-output-limit".to_owned());
        assert!(gateway.approve_once("approval-output-limit"));
        let output = gateway
            .execute_shell(output_request)
            .expect("output receipt");
        assert_eq!(output.receipt.status, ToolStatus::Failed);
        assert_eq!(
            output.receipt.error_code.as_deref(),
            Some("output_limit_exceeded")
        );
        assert!(output.receipt.output_truncated);
        assert!(output.stdout.len() <= 32);

        let mut timeout_request = ShellRequest::new("shell-timeout", "sleep");
        timeout_request.args = vec!["1".to_owned()];
        timeout_request.timeout_ms = 20;
        timeout_request.approval_id = Some("approval-timeout".to_owned());
        assert!(gateway.approve_once("approval-timeout"));
        let timeout = gateway
            .execute_shell(timeout_request)
            .expect("timeout receipt");
        assert_eq!(timeout.receipt.status, ToolStatus::Interrupted);
        assert_eq!(timeout.receipt.error_code.as_deref(), Some("timeout"));
        assert!(timeout.receipt.finished_at_ms.is_some());
    }

    #[test]
    fn git_status_and_worktree_writes_share_approval_boundary() {
        let (gateway, root) = gateway("git");
        let mut request = GitRequest {
            operation_id: "git-status-rejected".to_owned(),
            repo: PathBuf::new(),
            operation: GitOperation::Status,
            approval_id: None,
            timeout_ms: DEFAULT_TIMEOUT_MS,
        };
        let rejected = gateway.execute_git(request.clone()).expect("receipt");
        assert_eq!(rejected.receipt.status, ToolStatus::Rejected);

        let init = Command::new("git")
            .args(["init", "--quiet", root.to_str().expect("root")])
            .output()
            .expect("git init");
        assert!(init.status.success(), "git init failed: {:?}", init);
        request.operation_id = "git-status-approved".to_owned();
        request.approval_id = Some(APPROVAL.to_owned());
        assert!(gateway.approve_once(APPROVAL));
        let status = gateway.execute_git(request).expect("status");
        assert_eq!(status.receipt.status, ToolStatus::Succeeded);

        let target = PathBuf::from("worktrees/one");
        fs::create_dir_all(root.join("worktrees")).expect("worktree parent");
        let mut write = GitRequest {
            operation_id: "git-worktree-rejected".to_owned(),
            repo: PathBuf::new(),
            operation: GitOperation::CreateWorktree {
                path: target,
                revision: "HEAD".to_owned(),
            },
            approval_id: None,
            timeout_ms: DEFAULT_TIMEOUT_MS,
        };
        let rejected = gateway.execute_git(write.clone()).expect("write receipt");
        assert_eq!(rejected.receipt.status, ToolStatus::Rejected);
        assert!(!root.join("worktrees/one").exists());
        write.operation_id = "git-worktree-escape".to_owned();
        if let GitOperation::CreateWorktree { path, .. } = &mut write.operation {
            *path = PathBuf::from("../escape");
        }
        assert!(gateway.execute_git(write).is_err());
    }

    #[test]
    fn git_worktree_add_and_remove_are_approved_and_receipted() {
        let (gateway, root) = gateway("git-worktree-lifecycle");
        let init = Command::new("git")
            .args(["init", "--quiet", root.to_str().expect("root")])
            .output()
            .expect("git init");
        assert!(init.status.success(), "git init failed: {:?}", init);
        fs::write(root.join("README.md"), b"fixture\n").expect("fixture");
        let add = Command::new("git")
            .args(["-C", root.to_str().expect("root"), "add", "README.md"])
            .output()
            .expect("git add");
        assert!(add.status.success(), "git add failed: {:?}", add);
        let commit = Command::new("git")
            .args([
                "-C",
                root.to_str().expect("root"),
                "-c",
                "user.name=Codinal Fixture",
                "-c",
                "user.email=codinal-fixture@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "fixture",
            ])
            .output()
            .expect("git commit");
        assert!(commit.status.success(), "git commit failed: {:?}", commit);

        let worktree_path = PathBuf::from("worktrees/lifecycle");
        fs::create_dir_all(root.join("worktrees")).expect("worktree parent");
        let mut create = GitRequest {
            operation_id: "git-worktree-create".to_owned(),
            repo: PathBuf::new(),
            operation: GitOperation::CreateWorktree {
                path: worktree_path.clone(),
                revision: "codinal-missing-revision".to_owned(),
            },
            approval_id: Some(APPROVAL.to_owned()),
            timeout_ms: DEFAULT_TIMEOUT_MS,
        };
        assert!(gateway.approve_once(APPROVAL));
        let failed = gateway
            .execute_git(create.clone())
            .expect("failure receipt");
        assert_eq!(failed.receipt.status, ToolStatus::Failed);
        assert_eq!(failed.receipt.error_code.as_deref(), Some("process_failed"));
        assert_eq!(
            failed.receipt.changed_paths,
            vec!["worktrees/lifecycle".to_owned()]
        );
        assert!(!root.join(&worktree_path).exists());

        create.operation_id = "git-worktree-create-retry".to_owned();
        if let GitOperation::CreateWorktree { revision, .. } = &mut create.operation {
            *revision = "HEAD".to_owned();
        }
        assert!(gateway.approve_once(APPROVAL));
        let created = gateway.execute_git(create.clone()).expect("create receipt");
        assert_eq!(created.receipt.status, ToolStatus::Succeeded);
        assert_eq!(created.receipt.changed_paths, vec!["worktrees/lifecycle"]);
        assert!(root.join(&worktree_path).is_dir());

        create.operation_id = "git-worktree-remove".to_owned();
        create.operation = GitOperation::RemoveWorktree {
            path: worktree_path,
            force: true,
        };
        assert!(gateway.approve_once(APPROVAL));
        let removed = gateway.execute_git(create).expect("remove receipt");
        assert_eq!(removed.receipt.status, ToolStatus::Succeeded);
        assert!(!root.join("worktrees/lifecycle").exists());
    }

    #[cfg(unix)]
    #[test]
    fn real_git_worktree_interrupt_recovers_partial_target_and_preserves_sibling() {
        use std::os::unix::fs::PermissionsExt;

        let (gateway, root) = gateway("git-worktree-interrupt");
        let init = Command::new("git")
            .args(["init", "--quiet", root.to_str().expect("root")])
            .output()
            .expect("git init");
        assert!(init.status.success(), "git init failed: {:?}", init);
        fs::write(root.join("README.md"), b"fixture\n").expect("fixture");
        let add = Command::new("git")
            .args(["-C", root.to_str().expect("root"), "add", "README.md"])
            .output()
            .expect("git add");
        assert!(add.status.success(), "git add failed: {:?}", add);
        let commit = Command::new("git")
            .args([
                "-C",
                root.to_str().expect("root"),
                "-c",
                "user.name=Codinal Fixture",
                "-c",
                "user.email=codinal-fixture@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "fixture",
            ])
            .output()
            .expect("git commit");
        assert!(commit.status.success(), "git commit failed: {:?}", commit);

        fs::create_dir_all(root.join("worktrees/keep")).expect("sibling");
        fs::write(root.join("worktrees/keep/keep-marker"), b"keep\n").expect("marker");
        let hook = root.join(".git/hooks/post-checkout");
        fs::write(
            &hook,
            "#!/bin/sh\nprintf '%s\\n' started > .codinal-hook-started\nsleep 1\n",
        )
        .expect("checkout hook");
        fs::set_permissions(&hook, fs::Permissions::from_mode(0o755)).expect("hook mode");

        let operation_id = "git-worktree-real-interrupt";
        let request = GitRequest {
            operation_id: operation_id.to_owned(),
            repo: PathBuf::new(),
            operation: GitOperation::CreateWorktree {
                path: PathBuf::from("worktrees/interrupted"),
                revision: "HEAD".to_owned(),
            },
            approval_id: Some(APPROVAL.to_owned()),
            timeout_ms: 20_000,
        };
        assert!(gateway.approve_once(APPROVAL));
        let worker_gateway = gateway.clone();
        let worker = thread::spawn(move || worker_gateway.execute_git(request));
        let hook_started = (0..200).any(|_| {
            if root
                .join("worktrees/interrupted/.codinal-hook-started")
                .is_file()
            {
                true
            } else {
                thread::sleep(Duration::from_millis(10));
                false
            }
        });
        assert!(
            hook_started,
            "git worktree hook never observed a materialized target"
        );
        for _ in 0..100 {
            if gateway.interrupt(operation_id) {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        let interrupted = worker.join().expect("worker").expect("receipt");
        assert_eq!(interrupted.receipt.status, ToolStatus::Interrupted);
        assert_eq!(
            interrupted.receipt.error_code.as_deref(),
            Some("interrupted")
        );
        assert_eq!(
            interrupted.receipt.changed_paths,
            vec!["worktrees/interrupted".to_owned()]
        );
        assert!(!root.join("worktrees/interrupted").exists());
        assert!(root.join("worktrees/keep/keep-marker").is_file());
    }

    #[test]
    fn failed_worktree_recovery_removes_only_the_operation_owned_target() {
        let root = temp_root("git-partial-recovery");
        let parent = root.join("worktrees");
        let target = parent.join("partial");
        let sibling = parent.join("keep");
        fs::create_dir_all(&target).expect("partial target");
        fs::create_dir_all(&sibling).expect("sibling");
        fs::write(target.join("partial-marker"), b"partial\n").expect("marker");
        fs::write(sibling.join("keep-marker"), b"keep\n").expect("sibling marker");

        assert!(recover_failed_worktree(&root, &target, 128));
        assert!(!target.exists());
        assert!(sibling.join("keep-marker").is_file());
    }

    #[test]
    fn mcp_stdio_requires_external_approval_and_validates_jsonrpc() {
        let root = temp_root("mcp");
        let config = ToolConfig::for_workspace(&root, root.join("state")).with_mcp_programs(["sh"]);
        let gateway = ToolGateway::new(config).expect("gateway");
        let args = vec![
            "-c".to_owned(),
            "printf '%s\\n' '{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"ok\":true}}'".to_owned(),
        ];
        let mut request = McpRequest {
            operation_id: "mcp-rejected".to_owned(),
            server_id: "fixture".to_owned(),
            program: "sh".to_owned(),
            args: args.clone(),
            method: "tools/list".to_owned(),
            params: serde_json::json!({}),
            approval_id: None,
            timeout_ms: DEFAULT_TIMEOUT_MS,
        };
        let rejected = gateway.execute_mcp(request.clone()).expect("receipt");
        assert_eq!(rejected.receipt.status, ToolStatus::Rejected);
        request.operation_id = "mcp-approved".to_owned();
        request.approval_id = Some(APPROVAL.to_owned());
        assert!(gateway.approve_once(APPROVAL));
        let result = gateway.execute_mcp(request).expect("MCP result");
        assert_eq!(result.receipt.status, ToolStatus::Succeeded);
        assert_eq!(result.response.expect("response")["result"]["ok"], true);
    }

    #[test]
    fn checked_in_mcp_stdio_fixture_validates_request_and_returns_receipt() {
        let root = temp_root("mcp-fixture");
        let config = ToolConfig::for_workspace(&root, root.join("state")).with_mcp_programs(["sh"]);
        let gateway = ToolGateway::new(config).expect("gateway");
        let fixture =
            PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/mcp-stdio-server.sh");
        let mut request = McpRequest {
            operation_id: "mcp-fixture".to_owned(),
            server_id: "checked-in-fixture".to_owned(),
            program: "sh".to_owned(),
            args: vec![fixture.to_string_lossy().into_owned()],
            method: "tools/list".to_owned(),
            params: serde_json::json!({}),
            approval_id: Some("approval-mcp-fixture".to_owned()),
            timeout_ms: DEFAULT_TIMEOUT_MS,
        };
        assert!(gateway.approve_once("approval-mcp-fixture"));
        let execution = gateway.execute_mcp(request.clone()).expect("MCP receipt");
        assert_eq!(execution.receipt.status, ToolStatus::Succeeded);
        assert_eq!(
            execution.response.expect("MCP response")["result"]["server"],
            "codinal-fixture"
        );
        request.operation_id = "mcp-fixture-replay".to_owned();
        request.approval_id = None;
        let rejected = gateway.execute_mcp(request).expect("rejected receipt");
        assert_eq!(rejected.receipt.status, ToolStatus::Rejected);
    }

    #[test]
    fn mcp_invalid_jsonrpc_is_failed_and_receipted() {
        let root = temp_root("mcp-invalid");
        let config = ToolConfig::for_workspace(&root, root.join("state")).with_mcp_programs(["sh"]);
        let gateway = ToolGateway::new(config).expect("gateway");
        let mut request = McpRequest {
            operation_id: "mcp-invalid".to_owned(),
            server_id: "fixture".to_owned(),
            program: "sh".to_owned(),
            args: vec![
                "-c".to_owned(),
                "printf '%s\\n' '{\"jsonrpc\":\"2.0\",\"id\":2,\"result\":{}}'".to_owned(),
            ],
            method: "tools/list".to_owned(),
            params: serde_json::json!({}),
            approval_id: Some("approval-mcp-invalid".to_owned()),
            timeout_ms: DEFAULT_TIMEOUT_MS,
        };
        assert!(gateway.approve_once("approval-mcp-invalid"));
        let result = gateway.execute_mcp(request.clone()).expect("receipt");
        assert_eq!(result.receipt.status, ToolStatus::Failed);
        assert_eq!(
            result.receipt.error_code.as_deref(),
            Some("invalid_mcp_response")
        );

        request.operation_id = "mcp-invalid-replay".to_owned();
        request.approval_id = None;
        let rejected = gateway.execute_mcp(request).expect("rejected receipt");
        assert_eq!(rejected.receipt.status, ToolStatus::Rejected);
    }

    #[test]
    fn mcp_interrupt_and_timeout_leave_terminal_receipts() {
        let root = temp_root("mcp-interrupt");
        let config = ToolConfig::for_workspace(&root, root.join("state")).with_mcp_programs(["sh"]);
        let gateway = ToolGateway::new(config).expect("gateway");
        let mut request = McpRequest {
            operation_id: "mcp-interrupt".to_owned(),
            server_id: "fixture".to_owned(),
            program: "sh".to_owned(),
            args: vec!["-c".to_owned(), "sleep 10".to_owned()],
            method: "tools/list".to_owned(),
            params: serde_json::json!({}),
            approval_id: Some("approval-mcp-interrupt".to_owned()),
            timeout_ms: 20_000,
        };
        assert!(gateway.approve_once("approval-mcp-interrupt"));
        let worker_gateway = gateway.clone();
        let worker_request = request.clone();
        let worker = thread::spawn(move || worker_gateway.execute_mcp(worker_request));
        for _ in 0..100 {
            if gateway.interrupt("mcp-interrupt") {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        let interrupted = worker.join().expect("worker").expect("receipt");
        assert_eq!(interrupted.receipt.status, ToolStatus::Interrupted);
        assert_eq!(
            interrupted.receipt.error_code.as_deref(),
            Some("interrupted")
        );

        request.operation_id = "mcp-timeout".to_owned();
        request.approval_id = Some("approval-mcp-timeout".to_owned());
        request.timeout_ms = 20;
        assert!(gateway.approve_once("approval-mcp-timeout"));
        let timed_out = gateway.execute_mcp(request).expect("timeout receipt");
        assert_eq!(timed_out.receipt.status, ToolStatus::Interrupted);
        assert_eq!(timed_out.receipt.error_code.as_deref(), Some("timeout"));
    }

    #[test]
    fn pending_receipts_recover_as_interrupted_after_restart() {
        let root = temp_root("recovery");
        let store = ReceiptStore::open(&root.join("state"), MAX_OUTPUT_BYTES).expect("store");
        let receipt = ToolReceipt::pending(
            "restart-operation",
            "shell",
            ToolClass::Shell,
            ToolRisk::Exec,
        );
        store.write(&receipt).expect("pending");
        drop(store);
        let restarted = ReceiptStore::open(&root.join("state"), MAX_OUTPUT_BYTES).expect("restart");
        assert_eq!(restarted.recover_pending().expect("recover"), 1);
        let recovered = restarted
            .find_by_operation("restart-operation")
            .expect("read")
            .expect("receipt");
        assert_eq!(recovered.status, ToolStatus::Interrupted);
        assert_eq!(recovered.error_code.as_deref(), Some("process_restarted"));
    }
}
