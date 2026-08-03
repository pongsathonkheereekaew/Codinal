---
stage: C5
owner: codinal-runtime/tools
status: passed
fixture: isolated temporary workspace, receipt store, and local stdio fixtures
---

# C5 per-tool adversarial and recovery matrix

The matrix is the checked-in index for the required order: shell sandbox,
Git/worktrees, then MCP. Every local row uses the same policy/approval,
workspace boundary, interrupt, audit/receipt, and restart-recovery paths.

| Tool class | Adversarial/recovery condition | Fresh local evidence | Result |
|---|---|---|---|
| Shell | approval required; duplicate operation is idempotent | `shell_requires_approval_and_receipt_is_idempotent` | passed |
| Shell | `..`, absolute, and symlink escape attempts | `shell_rejects_escape_paths_and_symlink_boundaries` | passed |
| Shell | interrupt a running process | `shell_interrupt_writes_terminal_receipt` | passed |
| Shell | output cap and timeout | `shell_output_limit_and_timeout_are_terminal_and_bounded` | passed |
| Git | status is policy-bound; worktree add requires approval | `git_status_and_worktree_writes_share_approval_boundary` | passed |
| Git | approved worktree add/remove lifecycle and changed-path receipts | `git_worktree_add_and_remove_are_approved_and_receipted` | passed |
| Git | active-repository removal and workspace escape | same Git fixture plus path validators | passed |
| Git | failed worktree revision leaves no partial target and recovers on retry | `git_worktree_add_and_remove_are_approved_and_receipted`; operation receipt/restart tests | passed |
| Git | partial target cleanup is bounded to the operation-owned path | `failed_worktree_recovery_removes_only_the_operation_owned_target`; `real_git_worktree_interrupt_recovers_partial_target_and_preserves_sibling` | passed |
| MCP | external approval, server allow-list, malformed JSON-RPC | `mcp_stdio_requires_external_approval_and_validates_jsonrpc` | passed |
| MCP | checked-in stdio server validates request and returns JSON-RPC result | `checked_in_mcp_stdio_fixture_validates_request_and_returns_receipt` | passed locally |
| MCP | invalid JSON-RPC response is failed and receipted | `mcp_invalid_jsonrpc_is_failed_and_receipted` | passed |
| MCP | timeout/interrupt and child cleanup | `mcp_interrupt_and_timeout_leave_terminal_receipts`; checked-in stdio fixture | passed |
| All | pending receipt recovery after process restart | `pending_receipts_recover_as_interrupted_after_restart` | passed |
| All | operation idempotency/payload binding | `operation::duplicate_same_payload_replays_original_operation`, `operation::duplicate_different_payload_fails_closed` | passed |
| All | queue bound and deadline | `operation::queue_overflow_is_deterministic_and_does_not_persist_rejected_work`, `operation::deadline_is_enforced_before_running_progress`, `operation::deadline_is_enforced_when_running_work_finishes` | passed |
| All | cancellation before execution and restart | `operation::execution_boundary_rejects_expired_or_cancelled_work`, `operation::cancellation_wins_and_restart_recovers_running_work`, `operation::queued_cancellation_never_reaches_worker` | passed |

## Fresh command set

```text
cargo test --manifest-path crates/codinal-tools/Cargo.toml -- --nocapture
cargo clippy --manifest-path crates/codinal-tools/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path crates/codinal-runtime/Cargo.toml operation_route_runs_approved_git_status_with_progress_and_receipt -- --nocapture
cargo test --manifest-path crates/codinal-runtime/Cargo.toml operation_protocol_route_accepts_resumes_and_cancels -- --nocapture
```

The real-Git interruption row runs against an isolated temporary repository and
records process cleanup, policy decision, boundary result, receipt status, and
recovery outcome. External user repositories, home directories, network
servers, and credentialed MCP endpoints are not in scope for the deterministic
run.

Stop condition: any tool reaches a host process or mutation without its
approval/policy path, escapes the workspace/symlink boundary, loses its
terminal receipt, or leaves a partial mutation unreconciled.
