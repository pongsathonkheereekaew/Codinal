"""Validation and serialization for user-editable execution plans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_PLAN_STATUSES = {"draft", "approved", "revision_requested"}
LEGACY_VERIFICATION_PLACEHOLDER = (
    "Add a concrete verification criterion before approval"
)


@dataclass(frozen=True)
class PlanTask:
    task_id: str
    title: str
    verification: str
    description: str = ""

    @classmethod
    def parse(cls, value: Any) -> PlanTask:
        if not isinstance(value, Mapping) or not set(value) <= {
            "id",
            "title",
            "description",
            "verification",
        }:
            raise ValueError("invalid plan task")
        task_id = value.get("id")
        title = value.get("title")
        verification = value.get("verification")
        description = value.get("description", "")
        if (
            not isinstance(task_id, str)
            or _TASK_ID.fullmatch(task_id) is None
            or not isinstance(title, str)
            or not 1 <= len(title.strip()) <= 512
            or not isinstance(verification, str)
            or not 1 <= len(verification.strip()) <= 2048
            or not isinstance(description, str)
            or len(description.strip()) > 4096
        ):
            raise ValueError("invalid plan task")
        return cls(
            task_id=task_id,
            title=title.strip(),
            verification=verification.strip(),
            description=description.strip(),
        )

    def to_dict(self) -> dict[str, str]:
        task = {
            "id": self.task_id,
            "title": self.title,
            "verification": self.verification,
        }
        if self.description:
            task["description"] = self.description
        return task


@dataclass(frozen=True)
class PlanContent:
    plan: str
    tasks: tuple[PlanTask, ...]

    @classmethod
    def parse(cls, value: Any) -> PlanContent:
        if not isinstance(value, Mapping):
            raise ValueError("invalid plan")
        plan = value.get("plan")
        raw_tasks = value.get("tasks")
        if (
            not isinstance(plan, str)
            or not 1 <= len(plan.strip()) <= 32_768
            or not isinstance(raw_tasks, list)
            or not 1 <= len(raw_tasks) <= 20
        ):
            raise ValueError("invalid plan")
        tasks = tuple(PlanTask.parse(task) for task in raw_tasks)
        identifiers = [task.task_id for task in tasks]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate plan task")
        return cls(plan=plan.strip(), tasks=tasks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan,
            "tasks": [task.to_dict() for task in self.tasks],
        }


@dataclass(frozen=True)
class PlanApproval:
    content: PlanContent
    selected_task_ids: tuple[str, ...]
    mode: str

    @classmethod
    def parse(
        cls,
        value: Any,
        current: Mapping[str, Any],
    ) -> PlanApproval:
        if not isinstance(value, Mapping) or value.get("approved") is not True:
            raise ValueError("invalid plan approval")
        mode = value.get("mode", "interactive")
        if mode not in {"interactive", "auto"}:
            raise ValueError("invalid plan mode")
        content = PlanContent.parse(
            {
                "plan": value.get("plan", current.get("plan")),
                "tasks": value.get("tasks", current.get("tasks")),
            }
        )
        if any(
            task.verification == LEGACY_VERIFICATION_PLACEHOLDER
            for task in content.tasks
        ):
            raise ValueError("legacy plan verification must be edited")
        selected = value.get(
            "selected_task_ids",
            [task.task_id for task in content.tasks],
        )
        if (
            not isinstance(selected, list)
            or not selected
            or any(not isinstance(item, str) for item in selected)
            or len(selected) != len(set(selected))
        ):
            raise ValueError("invalid selected plan tasks")
        tasks_by_id = {task.task_id: task for task in content.tasks}
        if any(item not in tasks_by_id for item in selected):
            raise ValueError("invalid selected plan tasks")
        return cls(
            content=content,
            selected_task_ids=tuple(selected),
            mode=mode,
        )

    def to_response(self) -> dict[str, Any]:
        content = self.content.to_dict()
        tasks_by_id = {
            task.task_id: task.to_dict()
            for task in self.content.tasks
        }
        return {
            "approved": True,
            "mode": self.mode,
            **content,
            "selected_task_ids": list(self.selected_task_ids),
            "selected_tasks": [
                tasks_by_id[task_id]
                for task_id in self.selected_task_ids
            ],
        }


@dataclass(frozen=True)
class PlanArtifact:
    plan_id: str
    session_id: str
    tool_call_id: str
    content: PlanContent
    selected_task_ids: tuple[str, ...]
    status: str
    revision: int
    updated_at: str

    def __post_init__(self) -> None:
        if (
            re.fullmatch(r"[a-f0-9]{32}", self.plan_id) is None
            or self.status not in _PLAN_STATUSES
            or self.revision < 1
            or self.status == "approved"
            and not self.selected_task_ids
        ):
            raise ValueError("invalid plan artifact")
        known = {task.task_id for task in self.content.tasks}
        if any(task_id not in known for task_id in self.selected_task_ids):
            raise ValueError("invalid plan artifact selection")

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "session_id": self.session_id,
            "tool_call_id": self.tool_call_id,
            **self.content.to_dict(),
            "selected_task_ids": list(self.selected_task_ids),
            "status": self.status,
            "revision": self.revision,
            "updated_at": self.updated_at,
        }


def plan_tasks_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": 1,
        "maxItems": 20,
        "items": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$",
                },
                "title": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 512,
                },
                "description": {
                    "type": "string",
                    "maxLength": 4096,
                },
                "verification": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 2048,
                },
            },
            "required": ["id", "title", "verification"],
            "additionalProperties": False,
        },
    }
