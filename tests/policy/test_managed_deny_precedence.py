"""Managed policy deny-precedence tests.

Proves that managed deny is absolute — the user cannot override it via
session grants, AUTO mode, or provider config.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.policy import Mode, PermissionEngine
from runtime.policy.managed import ManagedPolicy
from runtime.secrets import ProviderSecretService


def test_managed_deny_overrides_auto_mode(tmp_path):
    """run_shell denied by managed policy even in AUTO mode."""
    policy = ManagedPolicy(denied_tools=frozenset(["run_shell"]))
    engine = PermissionEngine(
        tmp_path,
        mode=Mode.AUTO,
        managed_policy=policy,
    )
    decision = engine.evaluate("run_shell", {"command": "ls"})
    assert decision.allowed is False
    assert "managed policy" in decision.reason


def test_managed_command_deny_overrides_session_allow(tmp_path):
    policy = ManagedPolicy(denied_commands=frozenset(["curl"]))
    engine = PermissionEngine(
        tmp_path,
        mode=Mode.AUTO,
        session_allow_commands={"curl"},
        managed_policy=policy,
    )
    decision = engine.evaluate("run_shell", {"command": "curl http://evil"})
    assert decision.allowed is False
    assert "managed policy" in decision.reason


def test_managed_provider_deny_rejects_set_api_key():
    policy = ManagedPolicy(allowed_providers=frozenset(["anthropic"]))
    secrets = ProviderSecretService(managed_policy=policy)
    with pytest.raises(ValueError, match="denied by managed policy"):
        secrets.set_api_key("gemini", "fake-key-1234567890")


def test_managed_provider_allow_accepts_set_api_key():
    policy = ManagedPolicy(allowed_providers=frozenset(["openai"]))
    secrets = ProviderSecretService(managed_policy=policy)
    secrets.set_api_key("openai", "sk-test-1234567890")
    assert secrets.get("provider:openai") is not None


def test_no_managed_policy_means_unrestricted(tmp_path):
    engine = PermissionEngine(tmp_path, mode=Mode.AUTO)
    decision = engine.evaluate("run_shell", {"command": "ls"})
    assert decision.allowed is True


def test_read_tools_not_affected_by_managed_policy(tmp_path):
    """read_file is READ-risk; managed deny only applies to denied_tools."""
    policy = ManagedPolicy(denied_tools=frozenset(["run_shell"]))
    engine = PermissionEngine(tmp_path, mode=Mode.INTERACTIVE, managed_policy=policy)
    # read_file is not in denied_tools, so it's evaluated normally.
    decision = engine.evaluate("read_file", {"path": "x"})
    assert decision.allowed is True
