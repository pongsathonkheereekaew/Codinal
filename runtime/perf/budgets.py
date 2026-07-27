"""Performance-budget registry — index of every enforced runtime limit.

Each entry references the real constant by import (not a copy), so changing a
constant at its source flows through here automatically. The registry is the
single place to see "what does Codinal cap, and where".

Groups:
  tool_io      — read/write/grep/list tool limits
  sandbox      — seatbelt shell limits
  turn_engine  — agentic loop, attachments, streaming
  search       — repository text/symbol search
  index        — local semantic index
  git          — diff/status/log/checkpoint limits
  mcp          — remote tool boundary
  http         — control-plane request body limits
  store        — conversation/session persistence limits
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.control_plane import input_validation
from runtime.git import service as _git_service
from runtime.indexing import semantic as _semantic
from runtime.mcp import tools as _mcp_tools
from runtime.policy import tool_calls as _tool_calls
from runtime.sandbox import shell as _shell
from runtime.search import service as _search
from runtime.storage import conversations as _conv
from runtime.tools import core as _core
from runtime.tools import mutations as _mutations
from runtime.turn_engine import engine as _engine


@dataclass(frozen=True)
class Budget:
    name: str
    limit: Any
    unit: str
    source: str  # module.path:CONSTANT
    bounds: str


# fmt: off
BUDGETS: dict[str, Budget] = {
    # --- tool I/O ---
    "tool.read.max_file_bytes":      Budget("tool.read.max_file_bytes",      _core._MAX_FILE_BYTES,        "bytes",   "runtime.tools.core:_MAX_FILE_BYTES",        "read_file body cap"),
    "tool.read.max_lines":           Budget("tool.read.max_lines",           _core._MAX_LINES,             "lines",   "runtime.tools.core:_MAX_LINES",             "read_file line cap"),
    "tool.read.max_line_chars":      Budget("tool.read.max_line_chars",      _core._MAX_LINE_CHARS,        "chars",   "runtime.tools.core:_MAX_LINE_CHARS",        "per-line truncation"),
    "tool.grep.seconds":             Budget("tool.grep.seconds",             _core._MAX_GREP_SECONDS,      "seconds", "runtime.tools.core:_MAX_GREP_SECONDS",      "grep wall-clock deadline"),
    "tool.grep.max_results":         Budget("tool.grep.max_results",         _core._MAX_GREP_RESULTS,      "count",   "runtime.tools.core:_MAX_GREP_RESULTS",      "grep match cap"),
    "tool.grep.max_files":           Budget("tool.grep.max_files",           _core._MAX_GREP_FILES,        "count",   "runtime.tools.core:_MAX_GREP_FILES",        "files grep walks"),
    "tool.list.max_results":         Budget("tool.list.max_results",         _core._MAX_LIST_RESULTS,      "count",   "runtime.tools.core:_MAX_LIST_RESULTS",      "list tool results"),
    "tool.write.max_bytes":          Budget("tool.write.max_bytes",          _mutations._MAX_WRITE_BYTES,  "bytes",   "runtime.tools.mutations:_MAX_WRITE_BYTES",  "write_file/edit body cap"),
    "tool.write.max_replacements":   Budget("tool.write.max_replacements",   _mutations._MAX_REPLACEMENTS, "count",   "runtime.tools.mutations:_MAX_REPLACEMENTS", "edits per call"),
    "tool.command.max_seconds":      Budget("tool.command.max_seconds",      _mutations._MAX_COMMAND_SECONDS, "seconds", "runtime.tools.mutations:_MAX_COMMAND_SECONDS", "user-run shell timeout"),

    # --- tool-call contract ---
    "contract.max_tool_calls":       Budget("contract.max_tool_calls",       _tool_calls._MAX_TOOL_CALLS,      "count", "runtime.policy.tool_calls:_MAX_TOOL_CALLS",      "tool calls per turn"),
    "contract.max_argument_bytes":   Budget("contract.max_argument_bytes",   _tool_calls._MAX_ARGUMENT_BYTES,  "bytes", "runtime.policy.tool_calls:_MAX_ARGUMENT_BYTES",  "per-call args size"),

    # --- sandbox ---
    "sandbox.timeout_seconds":       Budget("sandbox.timeout_seconds",       _shell._DEFAULT_TIMEOUT_SECONDS,   "seconds", "runtime.sandbox.shell:_DEFAULT_TIMEOUT_SECONDS",   "seatbelt command timeout"),
    "sandbox.max_output_bytes":      Budget("sandbox.max_output_bytes",      _shell._DEFAULT_MAX_OUTPUT_BYTES, "bytes",   "runtime.sandbox.shell:_DEFAULT_MAX_OUTPUT_BYTES", "captured stdout/stderr"),
    "sandbox.max_roots":             Budget("sandbox.max_roots",             _shell._MAX_DECLARED_ROOTS,       "count",   "runtime.sandbox.shell:_MAX_DECLARED_ROOTS",       "declared read/write roots"),

    # --- search ---
    "search.max_seconds":            Budget("search.max_seconds",            _search._MAX_SECONDS,            "seconds", "runtime.search.service:_MAX_SECONDS",            "query deadline"),
    "search.max_files":              Budget("search.max_files",              _search._MAX_FILES,              "count",   "runtime.search.service:_MAX_FILES",              "files walked"),
    "search.max_total_bytes":        Budget("search.max_total_bytes",        _search._MAX_TOTAL_BYTES,        "bytes",   "runtime.search.service:_MAX_TOTAL_BYTES",        "bytes scanned"),
    "search.max_results":            Budget("search.max_results",            _search._MAX_RESULTS,            "count",   "runtime.search.service:_MAX_RESULTS",            "returned matches"),

    # --- semantic index ---
    "index.build_seconds":           Budget("index.build_seconds",           _semantic._INDEX_SECONDS,        "seconds", "runtime.indexing.semantic:_INDEX_SECONDS",        "build deadline"),
    "index.query_seconds":           Budget("index.query_seconds",           _semantic._QUERY_SECONDS,        "seconds", "runtime.indexing.semantic:_QUERY_SECONDS",        "query deadline"),
    "index.max_chunks":              Budget("index.max_chunks",              _semantic._MAX_CHUNKS,           "count",   "runtime.indexing.semantic:_MAX_CHUNKS",           "chunks per scope"),
    "index.max_global_chunks":       Budget("index.max_global_chunks",       _semantic._MAX_GLOBAL_CHUNKS,    "count",   "runtime.indexing.semantic:_MAX_GLOBAL_CHUNKS",    "chunks across all scopes"),
    "index.max_database_bytes":      Budget("index.max_database_bytes",      _semantic._MAX_DATABASE_BYTES,   "bytes",   "runtime.indexing.semantic:_MAX_DATABASE_BYTES",   "index DB size before eviction"),

    # --- git ---
    "git.probe_timeout_seconds":     Budget("git.probe_timeout_seconds",     _git_service._PROBE_TIMEOUT_SECONDS, "seconds", "runtime.git.service:_PROBE_TIMEOUT_SECONDS", "git probe deadline"),
    "git.probe_output_bytes":        Budget("git.probe_output_bytes",        _git_service._PROBE_OUTPUT_LIMIT,    "bytes",   "runtime.git.service:_PROBE_OUTPUT_LIMIT",    "diff/status stdout cap"),
    "git.log_max_limit":             Budget("git.log_max_limit",             _git_service._LOG_MAX_LIMIT,        "count",   "runtime.git.service:_LOG_MAX_LIMIT",        "log entries returned"),

    # --- mcp ---
    "mcp.max_schema_bytes":          Budget("mcp.max_schema_bytes",          _mcp_tools._MAX_SCHEMA_BYTES,       "bytes",   "runtime.mcp.tools:_MAX_SCHEMA_BYTES",       "remote tool schema size"),
    "mcp.call_timeout_seconds":      Budget("mcp.call_timeout_seconds",      _mcp_tools._DEFAULT_CALL_TIMEOUT_SECONDS, "seconds", "runtime.mcp.tools:_DEFAULT_CALL_TIMEOUT_SECONDS", "per MCP tool call"),

    # --- http bodies ---
    "http.max_turn_body_bytes":      Budget("http.max_turn_body_bytes",      input_validation.MAX_TURN_BODY_BYTES,        "bytes", "runtime.control_plane.input_validation:MAX_TURN_BODY_BYTES",        "POST /turns body"),
    "http.max_attachment_bytes":     Budget("http.max_attachment_bytes",     input_validation.MAX_ATTACHMENT_BYTES,       "bytes", "runtime.control_plane.input_validation:MAX_ATTACHMENT_BYTES",       "single attachment"),
    "http.max_attachments":          Budget("http.max_attachments",          input_validation.MAX_ATTACHMENTS,            "count", "runtime.control_plane.input_validation:MAX_ATTACHMENTS",            "attachments per turn"),
    "http.max_terminal_timeout_s":   Budget("http.max_terminal_timeout_s",   600.0,                                       "seconds", "runtime.control_plane.app:MAX_TERMINAL_TIMEOUT_SECONDS", "terminal run timeout"),

    # --- store ---
    "store.max_export_bytes":        Budget("store.max_export_bytes",        _conv.MAX_EXPORT_STORED_BYTES,   "bytes", "runtime.storage.conversations:MAX_EXPORT_STORED_BYTES",   "export payload cap"),
    "store.max_plan_response_bytes": Budget("store.max_plan_response_bytes", _conv.MAX_PLAN_RESPONSE_BYTES,   "bytes", "runtime.storage.conversations:MAX_PLAN_RESPONSE_BYTES",   "plan artifact body"),

    # --- turn engine / outbound ---
    "engine.max_outbound_messages":  Budget("engine.max_outbound_messages",  _engine._MAX_OUTBOUND_MESSAGES,    "count",  "runtime.turn_engine.engine:_MAX_OUTBOUND_MESSAGES",    "outbound history soft cap"),
    "engine.attachment_timeout_s":   Budget("engine.attachment_timeout_s",   _engine._ATTACHMENT_TIMEOUT_SECONDS, "seconds", "runtime.turn_engine.engine:_ATTACHMENT_TIMEOUT_SECONDS", "PDF/attachment rebuild deadline"),
}
# fmt: on


def assert_within_budget(name: str, measured: float) -> None:
    """Raise AssertionError if ``measured`` exceeds the named budget's limit.

    For budgets expressed in seconds, allows a 2x headroom (CI runners are
    slower than the in-prod deadline). For other units, exact comparison.
    """
    if name not in BUDGETS:
        raise KeyError(f"unknown budget: {name}")
    budget = BUDGETS[name]
    limit = float(budget.limit)
    allowed = limit * 2 if budget.unit == "seconds" else limit
    if measured > allowed:
        raise AssertionError(
            f"{name} exceeded budget: {measured} {budget.unit} > "
            f"{allowed} (limit {limit}, headroom x{allowed / limit:.1f})"
        )
