from __future__ import annotations

import json

import pytest

from runtime.settings import JsonPreferenceStore, SettingsService


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
