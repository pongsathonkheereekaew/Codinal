"""ManagedPolicy tests — loading + allow/deny checks."""

import json

from runtime.policy.managed import ManagedPolicy


def test_from_file_loads_all_fields(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({
        "allowed_providers": ["anthropic", "openai"],
        "allowed_models": ["anthropic:claude-sonnet-4-6"],
        "denied_tools": ["run_shell"],
        "denied_commands": ["curl", "wget"],
    }), encoding="utf-8")

    policy = ManagedPolicy.from_file(path)

    assert policy is not None
    assert policy.provider_allowed("anthropic") is True
    assert policy.provider_allowed("gemini") is False
    assert policy.model_allowed("anthropic:claude-sonnet-4-6") is True
    assert policy.model_allowed("openai:gpt-test") is False
    assert policy.tool_allowed("write_file") is True
    assert policy.tool_allowed("run_shell") is False
    assert policy.command_allowed("curl http://evil") is False
    assert policy.command_allowed("ls") is True


def test_from_file_none_path():
    assert ManagedPolicy.from_file(None) is None


def test_from_file_missing_file(tmp_path):
    assert ManagedPolicy.from_file(tmp_path / "nope.json") is None


def test_from_file_empty_json_means_unrestricted(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text("{}", encoding="utf-8")

    policy = ManagedPolicy.from_file(path)

    assert policy is not None
    assert policy.provider_allowed("anything") is True
    assert policy.model_allowed("anything") is True
    assert policy.tool_allowed("anything") is True
    assert policy.command_allowed("anything") is True


def test_from_file_invalid_json_returns_none(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text("not json", encoding="utf-8")

    assert ManagedPolicy.from_file(path) is None


def test_to_dict_round_trips():
    policy = ManagedPolicy(
        allowed_providers=frozenset(["anthropic"]),
        denied_tools=frozenset(["run_shell"]),
    )
    d = policy.to_dict()
    assert d["active"] is True
    assert d["allowed_providers"] == ["anthropic"]
    assert d["denied_tools"] == ["run_shell"]
    assert d["allowed_models"] is None
