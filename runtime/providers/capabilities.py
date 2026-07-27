# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Adapted from andrewyng/openworker:
# coworker/providers/capabilities.py @
# 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Conservative model capabilities before live conformance results exist."""

from .base import ModelCapabilities


def capabilities_for(model: str) -> ModelCapabilities:
    provider = model.split(":", 1)[0].lower() if ":" in model else ""
    name = model.split(":", 1)[-1].lower()
    if provider == "ollama":
        return ModelCapabilities(
            parallel_tool_calls=False,
            streaming=True,
        )
    if provider in ("anthropic", "gemini"):
        return ModelCapabilities(
            vision=True,
            pdf=True,
            streaming=True,
        )
    if provider == "zai":
        # Z.ai GLM-4.6 / GLM-4V: streaming + vision on multimodal models.
        return ModelCapabilities(
            vision=True,
            streaming=True,
        )
    if provider == "deepseek":
        # DeepSeek-chat / DeepSeek-reasoner: streaming; reasoning_content is
        # already surfaced as thinking text (openai_provider._delta_reasoning).
        return ModelCapabilities(
            streaming=True,
        )
    if name.startswith(("gpt-5", "gpt-4")):
        return ModelCapabilities(
            vision=True,
            streaming=True,
        )
    if name.startswith(("o1", "o3", "o4")):
        return ModelCapabilities(
            parallel_tool_calls=False,
            streaming=True,
        )
    return ModelCapabilities(
        parallel_tool_calls=False,
        streaming=True,
    )
