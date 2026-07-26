"""Adapter from the runtime provider contract to the conformance runner."""

from __future__ import annotations

import asyncio
from typing import Any

from runtime.conformance import ConformanceRequest, ProviderResponse

from .base import ProviderClient


class ProviderConformanceAdapter:
    def __init__(
        self,
        client: ProviderClient,
        *,
        provider_name: str,
        model: str,
    ) -> None:
        self._client = client
        self.provider = provider_name
        self.model = model

    @property
    def informational_capabilities(self) -> dict[str, bool | None]:
        try:
            capabilities = self._client.capabilities(self.model)
        except Exception:
            return {"streaming": None, "json_mode": None}
        return {
            "streaming": capabilities.streaming,
            "json_mode": None,
        }

    async def complete(
        self, request: ConformanceRequest
    ) -> ProviderResponse:
        tools = [_convert_tool(tool) for tool in request.tools]
        turn = await asyncio.to_thread(
            self._client.complete,
            model=self.model,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            tools=tools or None,
            temperature=request.temperature,
        )
        return ProviderResponse(
            text=turn.text or "",
            tool_calls=[
                {
                    "id": call.id,
                    "name": call.name,
                    "arguments": call.arguments,
                }
                for call in turn.tool_calls
            ],
        )


def _convert_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        },
    }
