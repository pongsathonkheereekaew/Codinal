import asyncio
import re
from pathlib import Path

from runtime.conformance import ConformanceTier, run_conformance
from runtime.policy import ToolCall
from runtime.providers import (
    AssistantTurn,
    ModelCapabilities,
    ProviderClient,
    ProviderConformanceAdapter,
)


CASES = (
    Path(__file__).resolve().parents[2]
    / "harness/conformance/cases.json"
)


class ConformantProvider(ProviderClient):
    def __init__(self):
        self.requests = []

    def complete(self, *, model, messages, tools=None, **settings):
        self.requests.append((model, messages, tools, settings))
        system = messages[0]["content"]
        user = messages[1]["content"]
        if tools:
            nonce = re.search(r'nonce "([-_A-Za-z0-9]+)"', user).group(1)
            return AssistantTurn(
                tool_calls=[
                    ToolCall(
                        id="call_fixture",
                        name="codinal_conformance_probe",
                        arguments={"nonce": nonce, "approved": True},
                    )
                ]
            )
        nonce = re.search(r"CODINAL_SYSTEM_([-_A-Za-z0-9]+)", system).group(1)
        return AssistantTurn(text=f"CODINAL_SYSTEM_{nonce}")

    def capabilities(self, model):
        return ModelCapabilities(streaming=True)


def test_provider_bridge_preserves_system_role_and_tool_schema() -> None:
    provider = ConformantProvider()
    adapter = ProviderConformanceAdapter(
        provider,
        provider_name="fixture",
        model="fixture-model",
    )

    report = asyncio.run(
        run_conformance(
            adapter,
            cases_path=CASES,
            nonce_factory=lambda: "fresh_nonce_0123456789abcdef",
        )
    )

    assert report.tier is ConformanceTier.TIER_1
    assert provider.requests[0][1][0]["role"] == "system"
    assert provider.requests[0][2] == [
        {
            "type": "function",
            "function": {
                "name": "codinal_conformance_probe",
                "description": "Returns a nonce to the Codinal policy boundary.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nonce": {"type": "string"},
                        "approved": {"type": "boolean"},
                    },
                    "required": ["nonce", "approved"],
                    "additionalProperties": False,
                },
            },
        }
    ]
    assert report.informational == {
        "streaming": True,
        "json_mode": None,
    }
