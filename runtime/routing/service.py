"""Capability-aware model selection with explicit user-visible decisions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from runtime.providers.capabilities import capabilities_for

_PROFILES = (
    {
        "id": "manual",
        "label": "Manual",
        "description": "Use the exact model selected in the composer.",
    },
    {
        "id": "quality",
        "label": "Quality",
        "description": (
            "Prefer the strongest configured model with native attachment "
            "support."
        ),
    },
    {
        "id": "balanced",
        "label": "Balanced",
        "description": (
            "Prefer configured standard-cost models while preserving native "
            "attachment support."
        ),
    },
    {
        "id": "economy",
        "label": "Economy",
        "description": (
            "Prefer configured economy models while preserving native "
            "attachment support."
        ),
    },
)
_PROFILE_IDS = frozenset(profile["id"] for profile in _PROFILES)
_MODEL_COSTS = {
    "openai:gpt-5.6-sol": "premium",
    "anthropic:claude-sonnet-4-6": "standard",
    "gemini:gemini-2.5-flash": "economy",
}
_PROFILE_ORDER = {
    "quality": (
        "openai:gpt-5.6-sol",
        "anthropic:claude-sonnet-4-6",
        "gemini:gemini-2.5-flash",
    ),
    "balanced": (
        "anthropic:claude-sonnet-4-6",
        "openai:gpt-5.6-sol",
        "gemini:gemini-2.5-flash",
    ),
    "economy": (
        "gemini:gemini-2.5-flash",
        "anthropic:claude-sonnet-4-6",
        "openai:gpt-5.6-sol",
    ),
}


class ModelRoutingService:
    """Resolve a routing profile without hiding its concrete model choice."""

    def __init__(
        self,
        model_source: Callable[[], list[str]],
        secrets: Any,
    ) -> None:
        self._model_source = model_source
        self._secrets = secrets

    def view(self, profile: str) -> dict[str, Any]:
        selected = profile if profile in _PROFILE_IDS else "manual"
        return {
            "profile": selected,
            "profiles": [dict(item) for item in _PROFILES],
            "models": [
                self._metadata(model)
                for model in self._models()
            ],
        }

    def resolve(
        self,
        profile: str,
        *,
        preferred_model: str,
        user_input: str | list[dict[str, Any]],
        required_capabilities: list[str] | tuple[str, ...] = (),
    ) -> dict[str, Any]:
        if profile not in _PROFILE_IDS:
            raise ValueError("invalid routing profile")
        models = self._models()
        preferred = (preferred_model or "").strip()
        required = _required_capabilities(user_input)
        required.update(
            capability
            for capability in required_capabilities
            if capability in {"tools", "vision", "pdf"}
        )
        if profile == "manual":
            if (
                not preferred
                or len(preferred.encode("utf-8")) > 256
                or any(ord(character) < 32 for character in preferred)
            ):
                raise ValueError("preferred model is unavailable")
            selected = self._metadata(preferred)
        else:
            candidates = [
                self._metadata(model)
                for model in models
                if model in _MODEL_COSTS
                and self._configured(_provider(model))
            ]
            if not candidates:
                raise ValueError(
                    "no configured model satisfies routing profile"
                )
            order = {
                model: index
                for index, model in enumerate(_PROFILE_ORDER[profile])
            }
            selected = min(
                candidates,
                key=lambda candidate: (
                    len(_degradations(candidate["capabilities"], required)),
                    order.get(candidate["id"], len(order)),
                    candidate["id"],
                ),
            )
        degradations = _degradations(
            selected["capabilities"],
            required,
        )
        return {
            "profile": profile,
            "selected_model": selected["id"],
            "provider": selected["provider"],
            "cost_class": selected["cost_class"],
            "configured": selected["configured"],
            "required_capabilities": sorted(required),
            "degradations": degradations,
            "reason": _reason(profile, selected, degradations),
        }

    def _models(self) -> list[str]:
        try:
            candidates = self._model_source()
        except Exception:
            candidates = []
        models = []
        for candidate in candidates[:128]:
            if (
                isinstance(candidate, str)
                and candidate
                and len(candidate.encode("utf-8")) <= 256
                and candidate == candidate.strip()
                and all(ord(character) >= 32 for character in candidate)
                and candidate not in models
            ):
                models.append(candidate)
        return models

    def _metadata(self, model: str) -> dict[str, Any]:
        provider = _provider(model)
        capabilities = capabilities_for(model)
        return {
            "id": model,
            "provider": provider,
            "cost_class": (
                "local"
                if provider == "ollama"
                else _MODEL_COSTS.get(model, "unknown")
            ),
            "configured": self._configured(provider),
            "auto_eligible": model in _MODEL_COSTS,
            "capabilities": {
                "tools": capabilities.tools,
                "vision": capabilities.vision,
                "pdf": capabilities.pdf,
                "parallel_tool_calls": capabilities.parallel_tool_calls,
                "streaming": capabilities.streaming,
            },
        }

    def _configured(self, provider: str) -> bool:
        if provider == "ollama":
            return True
        try:
            return any(
                item.get("provider") == provider
                and item.get("configured") is True
                for item in self._secrets.status()
                if isinstance(item, dict)
            )
        except Exception:
            return False


def _provider(model: str) -> str:
    return model.split(":", 1)[0].lower() if ":" in model else "openai"


def _required_capabilities(
    user_input: str | list[dict[str, Any]],
) -> set[str]:
    required = {"tools"}
    if not isinstance(user_input, list):
        return required
    for part in user_input:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "image_url":
            required.add("vision")
        if (
            part.get("type") == "file"
            and isinstance(part.get("file"), dict)
            and str(part["file"].get("file_data", "")).startswith(
                "data:application/pdf;base64,"
            )
        ):
            required.add("pdf")
    return required


def _degradations(
    capabilities: dict[str, bool],
    required: set[str],
) -> list[str]:
    degradations = []
    if "vision" in required and not capabilities["vision"]:
        degradations.append(
            "Images become visible placeholders because the model lacks vision"
        )
    if "pdf" in required and not capabilities["pdf"]:
        degradations.append(
            "PDF uses bounded local extraction because the model lacks native PDF support"
        )
    if "tools" in required and not capabilities["tools"]:
        degradations.append(
            "Coding tools are unavailable for the selected model"
        )
    return degradations


def _reason(
    profile: str,
    selected: dict[str, Any],
    degradations: list[str],
) -> str:
    if profile == "manual":
        return (
            f"manual uses exact model {selected['id']} from "
            f"{selected['provider']} ({selected['cost_class']})"
        )
    suffix = (
        f"; {len(degradations)} explicit degradation"
        f"{'' if len(degradations) == 1 else 's'}"
        if degradations
        else "; native required capabilities"
    )
    return (
        f"{profile} selected configured {selected['provider']} model "
        f"{selected['id']} ({selected['cost_class']}){suffix}"
    )
