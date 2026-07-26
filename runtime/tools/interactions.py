"""Manifest-bound interactive tools handled out-of-band by TurnEngine."""

from __future__ import annotations

from typing import Any

from runtime.plans import plan_tasks_schema
from runtime.policy import RiskClass
from runtime.policy.manifest import ToolSpec as ManifestToolSpec

from .registry import ToolRegistry


def register_interaction_tools(registry: ToolRegistry) -> None:
    for name, risk, description in (
        (
            "ask_user",
            RiskClass.READ,
            "Ask the user a blocking question.",
        ),
        (
            "propose_plan",
            RiskClass.EXTERNAL,
            "Propose a plan for explicit user approval.",
        ),
        (
            "request_directory",
            RiskClass.EXTERNAL,
            "Request explicit access to an additional directory.",
        ),
    ):
        registry.manifest.add(
            ManifestToolSpec(
                name,
                risk,
                category="interactive",
                description=description,
            )
        )

    def ask_user(
        question: str,
        options: list[str] | None = None,
    ) -> dict[str, Any]:
        return {"error": "interactive tool was not intercepted"}

    def propose_plan(
        plan: str,
        tasks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {"error": "interactive tool was not intercepted"}

    def request_directory(
        reason: str,
        path: str = "",
        writable: bool = False,
    ) -> dict[str, Any]:
        return {"error": "interactive tool was not intercepted"}

    registry.register(
        ask_user,
        schema=_schema(
            "ask_user",
            "Ask one question and wait for the user's answer.",
            {
                "question": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 10,
                },
            },
            ["question"],
        ),
    )
    registry.register(
        propose_plan,
        schema=_schema(
            "propose_plan",
            (
                "Present an editable plan for explicit approval. Include "
                "independently selectable tasks with concrete verification "
                "criteria."
            ),
            {
                "plan": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 32768,
                },
                "tasks": plan_tasks_schema(),
            },
            ["plan", "tasks"],
        ),
    )
    registry.register(
        request_directory,
        schema=_schema(
            "request_directory",
            "Request access to an additional local directory.",
            {
                "reason": {"type": "string"},
                "path": {"type": "string"},
                "writable": {"type": "boolean"},
            },
            ["reason"],
        ),
    )


def _schema(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }
