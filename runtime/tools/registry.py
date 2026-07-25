"""Manifest-bound runtime tool implementation registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

from runtime.policy import ToolManifest, parse_tool_calls


@dataclass(frozen=True)
class ToolSpec:
    name: str
    schema: dict[str, Any]
    func: Callable[..., Any]
    metadata: Any


class ToolRegistry:
    def __init__(self, manifest: ToolManifest) -> None:
        self._manifest = manifest
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        func: Callable[..., Any],
        *,
        schema: dict[str, Any],
    ) -> ToolSpec:
        name = getattr(func, "__name__", "")
        if name not in self._manifest.tools:
            raise ValueError("tool is not declared in manifest")
        if name in self._tools:
            raise ValueError("tool already registered")
        normalized = _validate_schema(name, schema)
        spec = ToolSpec(
            name=name,
            schema=normalized,
            func=func,
            metadata=self._manifest.metadata_for(name),
        )
        self._tools[name] = spec
        return spec

    def names(self) -> list[str]:
        return list(self._tools)

    @property
    def manifest(self) -> ToolManifest:
        return self._manifest

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [spec.schema for spec in self._tools.values()]

    def execute(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> Any:
        spec = self._tools.get(name)
        if spec is None:
            raise KeyError(f"Tool not registered: {name}")
        call = parse_tool_calls(
            [
                {
                    "id": "runtime_tool_execution",
                    "name": name,
                    "arguments": arguments or {},
                }
            ]
        )[0]
        return spec.func(**call.arguments)


def _validate_schema(name: str, schema: object) -> dict[str, Any]:
    try:
        normalized = json.loads(
            json.dumps(schema, allow_nan=False, sort_keys=True)
        )
    except (TypeError, ValueError, OverflowError):
        raise ValueError("invalid tool schema") from None
    function = (
        normalized.get("function")
        if isinstance(normalized, dict)
        else None
    )
    parameters = (
        function.get("parameters")
        if isinstance(function, dict)
        else None
    )
    if (
        not isinstance(normalized, dict)
        or set(normalized) != {"type", "function"}
        or normalized["type"] != "function"
        or not isinstance(function, dict)
        or set(function)
        != {"name", "description", "parameters"}
        or function["name"] != name
        or not isinstance(function["description"], str)
        or not function["description"]
        or not isinstance(parameters, dict)
        or parameters.get("type") != "object"
        or not isinstance(parameters.get("properties", {}), dict)
        or parameters.get("additionalProperties") is not False
        or not isinstance(parameters.get("required", []), list)
    ):
        raise ValueError("invalid tool schema")
    return normalized
