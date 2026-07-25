from __future__ import annotations

import json

import pytest

from runtime.settings import JsonPreferenceStore, SettingsService
from runtime.storage import UnsupportedSchemaVersionError


def test_legacy_preferences_are_versioned_and_backed_up(tmp_path):
    path = tmp_path / "prefs.json"
    legacy = {"default_model": "openai:gpt-legacy", "future_flag": True}
    path.write_text(json.dumps(legacy), encoding="utf-8")

    preferences = JsonPreferenceStore(path).load()

    assert preferences == {**legacy, "schema_version": 1}
    assert json.loads(path.read_text(encoding="utf-8")) == preferences
    backups = list(
        (tmp_path / "backups").glob("prefs.json.pre-v0-to-v1-*.bak")
    )
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8")) == legacy


def test_corrupt_preferences_are_preserved_before_empty_recovery(tmp_path):
    path = tmp_path / "prefs.json"
    corrupt = b'{"default_model": "private-model", broken'
    path.write_bytes(corrupt)

    preferences = JsonPreferenceStore(path).load()

    assert preferences == {"schema_version": 1}
    preserved = list(
        (tmp_path / "recovery").glob(
            "prefs.json.corrupt-*.preserved"
        )
    )
    assert len(preserved) == 1
    assert preserved[0].read_bytes() == corrupt
    assert json.loads(path.read_text(encoding="utf-8")) == preferences


def test_corrupt_preferences_restore_latest_valid_backup(tmp_path):
    path = tmp_path / "prefs.json"
    legacy = {"default_model": "anthropic:restored"}
    path.write_text(json.dumps(legacy), encoding="utf-8")
    store = JsonPreferenceStore(path)
    assert store.load()["default_model"] == "anthropic:restored"
    corrupt = b'{"default_model": broken'
    path.write_bytes(corrupt)

    recovered = store.load()

    assert recovered["default_model"] == "anthropic:restored"
    assert recovered["schema_version"] == 1
    assert next(
        (tmp_path / "recovery").glob(
            "prefs.json.corrupt-*.preserved"
        )
    ).read_bytes() == corrupt
    events = [
        json.loads(line)
        for line in (
            tmp_path / "recovery" / "events.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert [event["action"] for event in events] == [
        "preserved_corrupt_state",
        "restored_from_backup",
    ]


def test_newer_preferences_are_refused_without_downgrade(tmp_path):
    path = tmp_path / "prefs.json"
    future = {"schema_version": 99, "future_secret": "preserve"}
    path.write_text(json.dumps(future), encoding="utf-8")
    store = JsonPreferenceStore(path)

    with pytest.raises(UnsupportedSchemaVersionError):
        store.load()
    assert json.loads(path.read_text(encoding="utf-8")) == future

    with pytest.raises(UnsupportedSchemaVersionError):
        store.save(future)
    assert json.loads(path.read_text(encoding="utf-8")) == future


def test_negative_preferences_schema_is_refused_without_modification(
    tmp_path,
):
    path = tmp_path / "prefs.json"
    invalid = {"schema_version": -1, "retain": "this"}
    path.write_text(json.dumps(invalid), encoding="utf-8")

    with pytest.raises(UnsupportedSchemaVersionError):
        JsonPreferenceStore(path).load()

    assert json.loads(path.read_text(encoding="utf-8")) == invalid
    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "recovery").exists()


def test_preference_read_permission_error_fails_closed(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "prefs.json"
    path.write_text('{"schema_version": 1}', encoding="utf-8")
    original_read_text = type(path).read_text

    def deny_target(candidate, *args, **kwargs):
        if candidate == path:
            raise PermissionError("denied")
        return original_read_text(candidate, *args, **kwargs)

    monkeypatch.setattr(type(path), "read_text", deny_target)

    with pytest.raises(PermissionError, match="denied"):
        JsonPreferenceStore(path).load()

    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "recovery").exists()


def test_default_model_and_onboarding_persist_without_losing_unknown_preferences(
    tmp_path,
):
    path = tmp_path / "prefs.json"
    path.write_text(json.dumps({"future_flag": {"enabled": True}}), encoding="utf-8")
    store = JsonPreferenceStore(path)
    service = SettingsService(store, default_model="openai:gpt-default")

    assert service.view()["model"] == "openai:gpt-default"
    assert service.view()["onboarded"] is False
    assert service.set_default_model("anthropic:claude-test")["ok"] is True
    assert service.set_onboarded(True) == {"ok": True, "onboarded": True}

    reborn = SettingsService(
        JsonPreferenceStore(path),
        default_model="openai:gpt-default",
    )
    assert reborn.view()["model"] == "anthropic:claude-test"
    assert reborn.view()["onboarded"] is True
    assert json.loads(path.read_text(encoding="utf-8"))["future_flag"] == {
        "enabled": True
    }


def test_model_picker_customization_is_idempotent_and_persists(tmp_path):
    path = tmp_path / "prefs.json"
    curated = ["openai:gpt-default", "anthropic:claude-curated"]
    service = SettingsService(
        JsonPreferenceStore(path),
        default_model="openai:gpt-default",
        curated_models=curated,
    )

    service.remove_model("anthropic:claude-curated")
    service.add_model("local:qwen")
    service.add_model("local:qwen")
    service.remove_model("openai:gpt-default")

    assert service.view()["models"] == ["openai:gpt-default", "local:qwen"]

    reborn = SettingsService(
        JsonPreferenceStore(path),
        default_model="openai:gpt-default",
        curated_models=curated,
    )
    assert reborn.view()["models"] == ["openai:gpt-default", "local:qwen"]
    assert reborn.add_model("anthropic:claude-curated")["models"] == [
        "openai:gpt-default",
        "anthropic:claude-curated",
        "local:qwen",
    ]
    assert reborn.add_model("   ") == {"ok": False, "error": "empty model"}


def test_sidebar_preferences_are_normalized_and_persisted(tmp_path):
    path = tmp_path / "prefs.json"
    service = SettingsService(
        JsonPreferenceStore(path),
        default_model="openai:gpt-default",
    )

    assert service.view()["nav_layout"] == "flat"
    assert service.view()["sessions_peek"] == 5
    assert service.set_nav_layout("grouped") == {
        "ok": True,
        "nav_layout": "grouped",
    }
    assert service.set_sessions_peek(100) == {
        "ok": True,
        "sessions_peek": 50,
    }
    assert service.set_sessions_peek("many") == {
        "ok": False,
        "error": "sessions_peek must be a number",
    }

    reborn = SettingsService(
        JsonPreferenceStore(path),
        default_model="openai:gpt-default",
    )
    assert reborn.view()["nav_layout"] == "grouped"
    assert reborn.view()["sessions_peek"] == 50


def test_pdf_attachment_preferences_validate_as_one_atomic_update(tmp_path):
    path = tmp_path / "prefs.json"
    service = SettingsService(
        JsonPreferenceStore(path),
        default_model="openai:gpt-default",
    )

    assert service.view()["pdf"] == {
        "fallback": "text",
        "max_pages": 20,
        "max_mb": 10,
    }
    assert service.set_pdf_preferences(
        fallback="images",
        max_pages=200,
        max_mb=0,
    ) == {
        "ok": True,
        "pdf": {
            "fallback": "images",
            "max_pages": 100,
            "max_mb": 1,
        },
    }
    assert service.set_pdf_preferences(fallback="unsupported") == {
        "ok": False,
        "error": "pdf fallback must be text or images",
    }
    assert service.set_pdf_preferences(max_pages="many") == {
        "ok": False,
        "error": "pdf max_pages must be a number",
    }

    reborn = SettingsService(
        JsonPreferenceStore(path),
        default_model="openai:gpt-default",
    )
    assert reborn.view()["pdf"] == {
        "fallback": "images",
        "max_pages": 100,
        "max_mb": 1,
    }


def test_default_model_is_required(tmp_path):
    with pytest.raises(ValueError, match="default_model"):
        SettingsService(
            JsonPreferenceStore(tmp_path / "prefs.json"),
            default_model="  ",
        )
