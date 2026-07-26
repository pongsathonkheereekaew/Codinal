import pytest

from runtime.routing import ModelRoutingService
from runtime.secrets import ProviderSecretService


MODELS = (
    "openai:gpt-5.6-sol",
    "anthropic:claude-sonnet-4-6",
    "gemini:gemini-2.5-flash",
)


def _secrets(*providers):
    return ProviderSecretService(
        {
            f"provider:{provider}": {"api_key": f"{provider}-secret"}
            for provider in providers
        }
    )


def test_routing_view_is_transparent_and_never_contains_credentials():
    service = ModelRoutingService(lambda: list(MODELS), _secrets("openai"))

    view = service.view("balanced")

    assert [profile["id"] for profile in view["profiles"]] == [
        "manual",
        "quality",
        "balanced",
        "economy",
    ]
    assert view["profile"] == "balanced"
    assert view["models"][0] == {
        "id": "openai:gpt-5.6-sol",
        "provider": "openai",
        "cost_class": "premium",
        "configured": True,
        "auto_eligible": True,
        "capabilities": {
            "tools": True,
            "vision": True,
            "pdf": False,
            "parallel_tool_calls": True,
            "streaming": True,
        },
    }
    assert view["models"][1]["configured"] is False
    assert "secret" not in repr(view).lower()


def test_quality_profile_prefers_native_attachment_support_over_rank():
    service = ModelRoutingService(
        lambda: list(MODELS),
        _secrets("openai", "gemini"),
    )
    pdf_input = [
        {"type": "text", "text": "Review this"},
        {
            "type": "file",
            "file": {
                "filename": "design.pdf",
                "file_data": "data:application/pdf;base64,AA==",
            },
        },
    ]

    resolution = service.resolve(
        "quality",
        preferred_model=MODELS[0],
        user_input=pdf_input,
    )

    assert resolution["selected_model"] == MODELS[2]
    assert resolution["provider"] == "gemini"
    assert resolution["cost_class"] == "economy"
    assert resolution["required_capabilities"] == ["pdf", "tools"]
    assert resolution["degradations"] == []
    assert resolution["configured"] is True


def test_profile_reports_fallback_degradation_when_no_native_model_exists():
    service = ModelRoutingService(lambda: list(MODELS), _secrets("openai"))
    pdf_input = [
        {
            "type": "file",
            "file": {
                "filename": "scan.pdf",
                "file_data": "data:application/pdf;base64,AA==",
            },
        }
    ]

    resolution = service.resolve(
        "balanced",
        preferred_model=MODELS[0],
        user_input=pdf_input,
    )

    assert resolution["selected_model"] == MODELS[0]
    assert resolution["degradations"] == [
        "PDF uses bounded local extraction because the model lacks native PDF support"
    ]
    assert "openai" in resolution["reason"]


def test_manual_profile_keeps_exact_model_and_exposes_unknown_cost():
    service = ModelRoutingService(
        lambda: list(MODELS),
        _secrets(),
    )

    resolution = service.resolve(
        "manual",
        preferred_model="ollama:qwen3-coder",
        user_input="Fix the tests",
    )

    assert resolution["selected_model"] == "ollama:qwen3-coder"
    assert resolution["provider"] == "ollama"
    assert resolution["cost_class"] == "local"
    assert resolution["configured"] is True
    assert resolution["degradations"] == []


def test_auto_profile_fails_closed_without_configured_candidates():
    service = ModelRoutingService(lambda: list(MODELS), _secrets())

    with pytest.raises(ValueError, match="no configured model"):
        service.resolve(
            "economy",
            preferred_model=MODELS[0],
            user_input="Implement this",
        )

    with pytest.raises(ValueError, match="invalid routing profile"):
        service.resolve(
            "hidden",
            preferred_model=MODELS[0],
            user_input="Implement this",
        )


@pytest.mark.parametrize("preferred_model", ["", "stale:model"])
def test_auto_profile_does_not_require_a_preferred_model(preferred_model):
    service = ModelRoutingService(
        lambda: list(MODELS),
        _secrets("gemini"),
    )

    resolution = service.resolve(
        "economy",
        preferred_model=preferred_model,
        user_input="Implement this",
    )

    assert resolution["selected_model"] == MODELS[2]


def test_history_capabilities_remain_required_for_later_text_turns():
    service = ModelRoutingService(lambda: list(MODELS), _secrets("openai"))

    resolution = service.resolve(
        "balanced",
        preferred_model="",
        user_input="Continue the review",
        required_capabilities=["vision", "pdf"],
    )

    assert resolution["required_capabilities"] == ["pdf", "tools", "vision"]
    assert resolution["degradations"] == [
        "PDF uses bounded local extraction because the model lacks native PDF support"
    ]
