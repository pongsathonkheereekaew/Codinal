"""Strict normalized tool-call contract shared by engines and conformance."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_MAX_TOOL_CALLS = 64
_MAX_ARGUMENT_BYTES = 1_048_576


class ToolCallValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


def parse_tool_calls(payload: object) -> tuple[ToolCall, ...]:
    """Parse provider-normalized calls without accepting shape extensions."""
    if not isinstance(payload, list | tuple) or len(payload) > _MAX_TOOL_CALLS:
        raise _invalid()

    parsed = []
    seen_ids = set()
    for item in payload:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "name",
            "arguments",
        }:
            raise _invalid()
        call_id = item["id"]
        name = item["name"]
        arguments = item["arguments"]
        if (
            not isinstance(call_id, str)
            or not 1 <= len(call_id) <= 256
            or any(ord(character) < 32 for character in call_id)
            or call_id in seen_ids
            or not isinstance(name, str)
            or _TOOL_NAME.fullmatch(name) is None
            or not isinstance(arguments, dict)
        ):
            raise _invalid()
        try:
            _validate_json(arguments, depth=0, budget=[10_000])
            canonical = json.dumps(
                arguments,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            if len(canonical.encode("utf-8")) > _MAX_ARGUMENT_BYTES:
                raise _invalid()
            normalized = json.loads(canonical)
        except (
            TypeError,
            ValueError,
            OverflowError,
            UnicodeEncodeError,
        ):
            raise _invalid() from None
        seen_ids.add(call_id)
        parsed.append(
            ToolCall(
                id=call_id,
                name=name,
                arguments=normalized,
            )
        )
    return tuple(parsed)


def _invalid() -> ToolCallValidationError:
    return ToolCallValidationError("invalid tool-call payload")


def _validate_json(value: Any, *, depth: int, budget: list[int]) -> None:
    if depth > 32 or budget[0] <= 0:
        raise _invalid()
    budget[0] -= 1
    if value is None or isinstance(value, bool | int | str):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _invalid()
        return
    if isinstance(value, list):
        if len(value) > 4096:
            raise _invalid()
        for item in value:
            _validate_json(item, depth=depth + 1, budget=budget)
        return
    if isinstance(value, dict):
        if len(value) > 4096 or not all(
            isinstance(key, str) and len(key) <= 256 for key in value
        ):
            raise _invalid()
        for item in value.values():
            _validate_json(item, depth=depth + 1, budget=budget)
        return
    raise _invalid()
