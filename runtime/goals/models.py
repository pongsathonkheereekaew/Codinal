"""Validated durable goal records."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

_PUBLIC_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_REQUIREMENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


class GoalState(str, Enum):
    ACTIVE = "active"
    EXHAUSTED = "exhausted"
    COMPLETED = "completed"
    BLOCKED = "blocked"


TERMINAL_GOAL_STATES = frozenset(
    {GoalState.COMPLETED, GoalState.BLOCKED}
)


@dataclass(frozen=True)
class GoalRequirement:
    requirement_id: str
    text: str

    def __post_init__(self) -> None:
        if (
            _REQUIREMENT_ID.fullmatch(self.requirement_id) is None
            or not _valid_text(self.text, 1, 8192)
        ):
            raise ValueError("invalid goal requirement")


@dataclass(frozen=True)
class GoalEvidence:
    evidence_id: str
    requirement_id: str
    kind: str
    summary: str
    result: str
    passed: bool
    turn_index: int
    observed_at: str

    def __post_init__(self) -> None:
        if (
            not _valid_id(self.evidence_id, "evidence-")
            or (
                self.requirement_id
                and _REQUIREMENT_ID.fullmatch(self.requirement_id) is None
            )
            or self.kind not in {"turn", "verification", "blocker"}
            or self.kind == "verification"
            and not self.passed
            or self.kind == "blocker"
            and self.passed
            or not _valid_text(self.summary, 1, 8192)
            or not _valid_text(self.result, 0, 32 * 1024)
            or not isinstance(self.passed, bool)
            or isinstance(self.turn_index, bool)
            or not 0 <= self.turn_index <= 1_000_000
            or not _valid_text(self.observed_at, 1, 64)
        ):
            raise ValueError("invalid goal evidence")


@dataclass(frozen=True)
class GoalRecord:
    goal_id: str
    session_id: str
    objective: str
    requirements: tuple[GoalRequirement, ...]
    continuation_prompt: str
    token_budget: int | None = None
    time_budget_seconds: int | None = None
    state: GoalState = GoalState.ACTIVE
    tokens_used: int = 0
    continuation_count: int = 0
    continuation_running: bool = False
    baseline_message_count: int = 0
    continuation_turn_id: str = ""
    turn_started_at: str = ""
    evidence: tuple[GoalEvidence, ...] = ()
    audit_summary: str = ""
    requirement_evidence: tuple[tuple[str, tuple[str, ...]], ...] = ()
    created_at: str | None = field(default=None, compare=False)
    updated_at: str | None = field(default=None, compare=False)
    version: int = field(default=0, compare=False)

    def __post_init__(self) -> None:
        requirement_ids = [
            requirement.requirement_id for requirement in self.requirements
        ]
        evidence_ids = [item.evidence_id for item in self.evidence]
        if (
            not _valid_id(self.goal_id, "goal-")
            or not _valid_id(self.session_id)
            or not _valid_text(self.objective, 1, 64 * 1024)
            or not 1 <= len(self.requirements) <= 20
            or len(requirement_ids) != len(set(requirement_ids))
            or not _valid_text(
                self.continuation_prompt,
                1,
                32 * 1024,
            )
            or not _valid_budget(self.token_budget, 100_000_000)
            or not _valid_budget(
                self.time_budget_seconds,
                31 * 24 * 60 * 60,
            )
            or not isinstance(self.state, GoalState)
            or isinstance(self.tokens_used, bool)
            or not 0 <= self.tokens_used <= 1_000_000_000
            or isinstance(self.continuation_count, bool)
            or not 0 <= self.continuation_count <= 1_000_000
            or not isinstance(self.continuation_running, bool)
            or isinstance(self.baseline_message_count, bool)
            or not 0 <= self.baseline_message_count <= 10_000_000
            or (
                self.continuation_turn_id
                and not _valid_id(self.continuation_turn_id, "turn-")
            )
            or not _valid_text(self.turn_started_at, 0, 64)
            or len(self.evidence) > 1000
            or len(evidence_ids) != len(set(evidence_ids))
            or not _valid_text(self.audit_summary, 0, 32 * 1024)
            or isinstance(self.version, bool)
            or self.version < 0
        ):
            raise ValueError("invalid goal")
        requirement_set = set(requirement_ids)
        if any(
            item.requirement_id
            and item.requirement_id not in requirement_set
            or item.turn_index > self.continuation_count
            for item in self.evidence
        ):
            raise ValueError("invalid goal evidence mapping")
        mapped_requirements = [item[0] for item in self.requirement_evidence]
        if (
            len(mapped_requirements) != len(set(mapped_requirements))
            or any(
                requirement_id not in requirement_set
                or not evidence
                or len(evidence) > 100
                or len(evidence) != len(set(evidence))
                or any(item not in set(evidence_ids) for item in evidence)
                for requirement_id, evidence in self.requirement_evidence
            )
        ):
            raise ValueError("invalid goal audit mapping")


def _valid_id(value: object, prefix: str = "") -> bool:
    return (
        isinstance(value, str)
        and _PUBLIC_ID.fullmatch(value) is not None
        and (not prefix or value.startswith(prefix))
        and not value.startswith("__")
    )


def _valid_text(value: object, minimum: int, maximum: int) -> bool:
    if not isinstance(value, str):
        return False
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        return False
    return minimum <= size <= maximum


def _valid_budget(value: object, maximum: int) -> bool:
    return (
        value is None
        or not isinstance(value, bool)
        and isinstance(value, int)
        and 1 <= value <= maximum
    )
