"""Policy engine tests — pin the P0-critical behaviors:
- READ auto-allowed; WRITE_LOCAL path-scoped; EXEC shell-operator-rejected
- argv-token prefix (not string prefix); mode gating; session allow."""
from __future__ import annotations

from pathlib import Path

import pytest

from runtime.policy import (
    Decision,
    Mode,
    PermissionEngine,
    RiskClass,
    ToolManifest,
    classify,
)
from runtime.policy.permissions import _has_shell_operators


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    return tmp_path


@pytest.fixture()
def engine(workspace: Path) -> PermissionEngine:
    return PermissionEngine(workspace_root=workspace, mode=Mode.INTERACTIVE)


# -- risk classification -------------------------------------------------------
def test_read_tools_classify_read():
    assert classify("read_file") is RiskClass.READ
    assert classify("list_files") is RiskClass.READ


def test_write_tools_classify_write_local():
    for t in ("write_file", "replace_in_file", "apply_patch", "apply_unified_diff"):
        assert classify(t) is RiskClass.WRITE_LOCAL


def test_run_shell_classifies_exec():
    assert classify("run_shell") is RiskClass.EXEC


def test_unknown_without_metadata_is_read():
    assert classify("something_new") is RiskClass.READ


def test_metadata_requires_approval_is_external():
    class M:
        requires_approval = True
    assert classify("custom_tool", M()) is RiskClass.EXTERNAL


# -- READ always allowed ------------------------------------------------------
def test_read_allowed_any_mode(engine, workspace):
    engine.mode = Mode.PLAN
    d = engine.evaluate("read_file", {"path": str(workspace / "x")})
    assert d.allowed and not d.needs_user


# -- WRITE_LOCAL path scoping -------------------------------------------------
def test_write_inside_workspace_allowed_interactive(engine, workspace):
    d = engine.evaluate("write_file", {"path": str(workspace / "src" / "a.py")})
    assert d.needs_user and not d.allowed  # interactive asks


def test_write_outside_workspace_denied(engine, workspace, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    d = engine.evaluate("write_file", {"path": str(outside / "evil")})
    assert not d.allowed and not d.needs_user
    assert "writable" in d.reason


def test_write_relative_resolves_under_workspace(engine, workspace):
    d = engine.evaluate("write_file", {"path": "src/a.py"})
    assert d.needs_user  # inside workspace -> asks (not hard-denied)


# -- EXEC shell-operator rejection (the P0 from the handoff) ------------------
def test_has_shell_operators_catches_chaining_redirection_substitution():
    assert _has_shell_operators("git status && rm -rf ~")
    assert _has_shell_operators("cat x | grep y")
    assert _has_shell_operators("echo hi > /etc/passwd")
    assert _has_shell_operators("echo $(whoami)")
    assert _has_shell_operators("echo `whoami`")
    assert _has_shell_operators("a; b")
    assert not _has_shell_operators("git status -s")


def test_allowed_command_argv_token_prefix_not_string_prefix(engine):
    engine.allowed_commands = ["git status"]
    # exact argv prefix match -> allowed
    assert engine._command_allowed("git status -s") is True
    # string-prefix trick: "git statusfoo" must NOT match
    assert engine._command_allowed("git statusfoo") is False
    # operator present -> never allowlisted
    assert engine._command_allowed("git status && rm -rf ~") is False


def test_exec_unallowlisted_command_asks(engine):
    d = engine.evaluate("run_shell", {"command": "rm -rf /"})
    assert d.needs_user and not d.allowed


def test_exec_allowlisted_command_runs(engine):
    engine.allowed_commands = ["pytest"]
    d = engine.evaluate("run_shell", {"command": "pytest -q"})
    assert d.allowed and not d.needs_user


def test_exec_command_with_operators_not_auto_allowed(engine):
    # Even if "pytest" is allowlisted, "pytest ; rm -rf ~" must ask.
    engine.allowed_commands = ["pytest"]
    d = engine.evaluate("run_shell", {"command": "pytest ; rm -rf ~"})
    assert d.needs_user and not d.allowed


# -- mode gating --------------------------------------------------------------
def test_plan_mode_blocks_write(workspace):
    eng = PermissionEngine(workspace_root=workspace, mode=Mode.PLAN)
    d = eng.evaluate("write_file", {"path": str(workspace / "x")})
    assert not d.allowed and not d.needs_user


def test_auto_mode_allows_write_inside_workspace(workspace):
    eng = PermissionEngine(workspace_root=workspace, mode=Mode.AUTO)
    d = eng.evaluate("write_file", {"path": str(workspace / "x")})
    assert d.allowed and not d.needs_user


def test_auto_mode_still_scopes_writes(workspace, tmp_path_factory):
    outside = tmp_path_factory.mktemp("out")
    eng = PermissionEngine(workspace_root=workspace, mode=Mode.AUTO)
    d = eng.evaluate("write_file", {"path": str(outside / "x")})
    assert not d.allowed  # path scope holds even in AUTO


# -- session memory -----------------------------------------------------------
def test_allow_tool_for_session_then_allowed(engine):
    engine.allow_tool_for_session("write_file")
    d = engine.evaluate("write_file", {"path": str(engine.workspace_root / "x")})
    assert d.allowed and not d.needs_user


def test_allow_command_for_session_then_allowed(engine):
    engine.allow_command_for_session("make build")
    d = engine.evaluate("run_shell", {"command": "make build"})
    assert d.allowed


# -- ToolManifest integration -------------------------------------------------
def test_manifest_metadata_drives_external_classification():
    man = ToolManifest()
    man.add(__import__("runtime.policy.manifest", fromlist=["ToolSpec"]).ToolSpec(
        name="slack_post", risk=RiskClass.EXTERNAL, category="connector",
        requires_approval=True, target_arg="channel",
    ))
    meta = man.metadata_for("slack_post")
    assert meta is not None and meta.category == "connector"
    assert classify("slack_post", meta) is RiskClass.EXTERNAL


def test_manifest_metadata_preserves_declared_risk():
    man = ToolManifest()

    assert classify("git_stage", man.metadata_for("git_stage")) is RiskClass.WRITE_LOCAL
    assert classify("git_commit", man.metadata_for("git_commit")) is RiskClass.WRITE_LOCAL
