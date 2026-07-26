"""Provider-neutral execution of harness-owned conformance cases."""

from __future__ import annotations

import asyncio
import json
import re
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from runtime.policy import ToolCallValidationError, parse_tool_calls

_NONCE = re.compile(r"^[-_A-Za-z0-9]{16,128}$")
_CASE_ID = re.compile(r"^[a-z0-9-]{1,128}$")
_REQUIRED_AXES = {"tool_call_schema", "system_prompt_fidelity"}


class ConformanceTier(str, Enum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True)
class ConformanceRequest:
    case_id: str
    system: str
    user: str
    tools: tuple[dict[str, Any], ...] = ()
    temperature: float = 0.0


@dataclass(frozen=True)
class ProviderResponse:
    text: str = ""
    tool_calls: object = ()


class ConformanceProvider(Protocol):
    provider: str
    model: str
    informational_capabilities: Mapping[str, bool | None]

    async def complete(
        self, request: ConformanceRequest
    ) -> ProviderResponse: ...


@dataclass(frozen=True)
class AxisResult:
    case_id: str
    axis: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ConformanceReport:
    provider: str
    model: str
    results: tuple[AxisResult, ...]
    informational: dict[str, bool | None]

    @property
    def tier(self) -> ConformanceTier:
        passed = {
            axis
            for axis in _REQUIRED_AXES
            if any(result.axis == axis for result in self.results)
            and all(
                result.passed
                for result in self.results
                if result.axis == axis
            )
        }
        if _REQUIRED_AXES <= passed:
            return ConformanceTier.TIER_1
        if "tool_call_schema" in passed:
            return ConformanceTier.TIER_2
        return ConformanceTier.INCOMPATIBLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "tier": self.tier.value,
            "results": [
                {
                    "case_id": result.case_id,
                    "axis": result.axis,
                    "passed": result.passed,
                    "detail": result.detail,
                }
                for result in self.results
            ],
            "informational": dict(self.informational),
        }


@dataclass(frozen=True)
class _Case:
    case_id: str
    axis: str
    system: str
    user: str
    tool: dict[str, Any] | None
    expected: dict[str, Any]


async def run_conformance(
    provider: ConformanceProvider,
    *,
    cases_path: str | Path,
    timeout_seconds: float = 60.0,
    nonce_factory: Callable[[], str] | None = None,
) -> ConformanceReport:
    if not 0 < timeout_seconds <= 120:
        raise ValueError("timeout_seconds must be between 0 and 120")
    provider_name = _identity(provider, "provider")
    model = _identity(provider, "model")
    cases = _load_cases(Path(cases_path))
    mint_nonce = nonce_factory or (lambda: secrets.token_urlsafe(24))
    results = []
    for case in cases:
        nonce = mint_nonce()
        if not isinstance(nonce, str) or _NONCE.fullmatch(nonce) is None:
            raise ValueError("invalid conformance nonce")
        rendered = _render_case(case, nonce)
        results.append(
            await _execute_case(provider, rendered, timeout_seconds)
        )
    return ConformanceReport(
        provider=provider_name,
        model=model,
        results=tuple(results),
        informational=_informational(provider),
    )


async def _execute_case(
    provider: ConformanceProvider,
    case: _Case,
    timeout_seconds: float,
) -> AxisResult:
    request = ConformanceRequest(
        case_id=case.case_id,
        system=case.system,
        user=case.user,
        tools=(case.tool,) if case.tool is not None else (),
    )
    try:
        response = await asyncio.wait_for(
            provider.complete(request),
            timeout=timeout_seconds,
        )
    except Exception:
        return AxisResult(
            case.case_id,
            case.axis,
            False,
            "provider request failed",
        )
    if not isinstance(response, ProviderResponse):
        return AxisResult(
            case.case_id,
            case.axis,
            False,
            "provider response contract failed",
        )
    if case.axis == "tool_call_schema":
        return _check_tool_call(case, response)
    return _check_system_prompt(case, response)


def _check_tool_call(
    case: _Case, response: ProviderResponse
) -> AxisResult:
    try:
        calls = parse_tool_calls(response.tool_calls)
    except ToolCallValidationError:
        return AxisResult(
            case.case_id,
            case.axis,
            False,
            "tool-call contract failed",
        )
    expected = case.expected
    passed = (
        len(calls) == 1
        and calls[0].name == expected["tool_name"]
        and calls[0].arguments == expected["arguments"]
    )
    return AxisResult(
        case.case_id,
        case.axis,
        passed,
        "passed" if passed else "tool-call expectation failed",
    )


def _check_system_prompt(
    case: _Case, response: ProviderResponse
) -> AxisResult:
    try:
        calls = parse_tool_calls(response.tool_calls)
    except ToolCallValidationError:
        calls = ()
        valid_calls = False
    else:
        valid_calls = True
    passed = (
        valid_calls
        and not calls
        and response.text == case.expected["text"]
    )
    return AxisResult(
        case.case_id,
        case.axis,
        passed,
        "passed" if passed else "system-prompt fidelity failed",
    )


def _load_cases(path: Path) -> tuple[_Case, ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("invalid conformance case spec") from None
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "cases"}
        or document["version"] != 1
        or not isinstance(document["cases"], list)
        or not 2 <= len(document["cases"]) <= 16
    ):
        raise ValueError("invalid conformance case spec")
    parsed = tuple(_parse_case(value) for value in document["cases"])
    if (
        {case.axis for case in parsed} != _REQUIRED_AXES
        or len({case.case_id for case in parsed}) != len(parsed)
    ):
        raise ValueError("invalid conformance case spec")
    return parsed


def _parse_case(value: object) -> _Case:
    if (
        not isinstance(value, dict)
        or "{nonce}" not in json.dumps(value, sort_keys=True)
    ):
        raise ValueError("invalid conformance case spec")
    axis = value.get("axis")
    required = {"id", "axis", "system", "user", "expected"}
    if axis == "tool_call_schema":
        required.add("tool")
    if axis not in _REQUIRED_AXES or set(value) != required:
        raise ValueError("invalid conformance case spec")
    case_id = value["id"]
    system = value["system"]
    user = value["user"]
    expected = value["expected"]
    tool = value.get("tool")
    if (
        not isinstance(case_id, str)
        or _CASE_ID.fullmatch(case_id) is None
        or not _bounded_text(system, 8192)
        or not _bounded_text(user, 8192)
        or not isinstance(expected, dict)
        or (tool is not None and not isinstance(tool, dict))
    ):
        raise ValueError("invalid conformance case spec")
    if axis == "tool_call_schema":
        if (
            set(expected) != {"tool_name", "arguments"}
            or not _bounded_text(expected["tool_name"], 128)
            or not isinstance(expected["arguments"], dict)
            or not isinstance(tool, dict)
            or set(tool) != {"name", "description", "input_schema"}
            or not _bounded_text(tool["name"], 128)
            or expected["tool_name"] != tool["name"]
            or not _bounded_text(tool["description"], 1024)
            or not isinstance(tool["input_schema"], dict)
        ):
            raise ValueError("invalid conformance case spec")
    elif (
        set(expected) != {"text"}
        or not _bounded_text(expected["text"], 8192)
    ):
        raise ValueError("invalid conformance case spec")
    return _Case(case_id, axis, system, user, tool, expected)


def _render_case(case: _Case, nonce: str) -> _Case:
    return _Case(
        case.case_id,
        case.axis,
        case.system.replace("{nonce}", nonce),
        case.user.replace("{nonce}", nonce),
        _replace_nonce(case.tool, nonce),
        _replace_nonce(case.expected, nonce),
    )


def _replace_nonce(value: Any, nonce: str) -> Any:
    if isinstance(value, str):
        return value.replace("{nonce}", nonce)
    if isinstance(value, list):
        return [_replace_nonce(item, nonce) for item in value]
    if isinstance(value, dict):
        return {
            key: _replace_nonce(item, nonce)
            for key, item in value.items()
        }
    return value


def _identity(provider: object, field: str) -> str:
    value = getattr(provider, field, None)
    if not _bounded_text(value, 128):
        raise ValueError(f"invalid provider {field}")
    return value


def _informational(
    provider: object,
) -> dict[str, bool | None]:
    capabilities = getattr(provider, "informational_capabilities", {})
    if not isinstance(capabilities, Mapping):
        return {"streaming": None, "json_mode": None}
    return {
        name: value if isinstance(value, bool) or value is None else None
        for name in ("streaming", "json_mode")
        for value in (capabilities.get(name),)
    }


def _bounded_text(value: object, maximum: int) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= maximum
