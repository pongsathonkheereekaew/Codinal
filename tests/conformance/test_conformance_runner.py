import asyncio
import json
import re
from pathlib import Path

from runtime.conformance import (
    AxisResult,
    ConformanceReport,
    ConformanceRequest,
    ConformanceTier,
    ProviderResponse,
    run_conformance,
)


CASES = (
    Path(__file__).resolve().parents[2]
    / "harness/conformance/cases.json"
)


class PassingAdapter:
    provider = "fixture"
    model = "fixture-tier-one"
    informational_capabilities = {
        "streaming": True,
        "json_mode": False,
    }

    async def complete(
        self, request: ConformanceRequest
    ) -> ProviderResponse:
        nonce = re.search(
            r"(?:nonce \"|CODINAL_SYSTEM_)([-_A-Za-z0-9]+)",
            request.user + request.system,
        ).group(1)
        if request.case_id == "tool-call-schema":
            return ProviderResponse(
                tool_calls=[
                    {
                        "id": "call_fixture",
                        "name": "codinal_conformance_probe",
                        "arguments": {
                            "nonce": nonce,
                            "approved": True,
                        },
                    }
                ]
            )
        return ProviderResponse(text=f"CODINAL_SYSTEM_{nonce}")


def test_both_required_axes_are_needed_for_tier_one() -> None:
    report = asyncio.run(
        run_conformance(
            PassingAdapter(),
            cases_path=CASES,
            nonce_factory=lambda: "fresh_nonce_0123456789abcdef",
        )
    )

    assert report.tier is ConformanceTier.TIER_1
    assert [result.passed for result in report.results] == [True, True]
    assert report.informational == {
        "streaming": True,
        "json_mode": False,
    }
    assert report.to_dict()["tier"] == "tier_1"


def test_tool_schema_only_is_tier_two_and_informational_flags_do_not_promote() -> None:
    class ToolOnlyAdapter(PassingAdapter):
        informational_capabilities = {
            "streaming": True,
            "json_mode": True,
        }

        async def complete(
            self, request: ConformanceRequest
        ) -> ProviderResponse:
            response = await super().complete(request)
            if request.case_id == "system-prompt-fidelity":
                return ProviderResponse(text="USER_OVERRIDE")
            return response

    report = asyncio.run(
        run_conformance(
            ToolOnlyAdapter(),
            cases_path=CASES,
            nonce_factory=lambda: "fresh_nonce_0123456789abcdef",
        )
    )

    assert report.tier is ConformanceTier.TIER_2


def test_malformed_tool_call_and_provider_errors_fail_closed_without_leaking() -> None:
    marker = "provider-secret-must-not-echo"

    class BrokenAdapter(PassingAdapter):
        async def complete(
            self, request: ConformanceRequest
        ) -> ProviderResponse:
            if request.case_id == "tool-call-schema":
                return ProviderResponse(
                    tool_calls=[
                        {
                            "id": "call_fixture",
                            "name": "codinal_conformance_probe",
                            "arguments": marker,
                        }
                    ]
                )
            raise RuntimeError(marker)

    report = asyncio.run(
        run_conformance(
            BrokenAdapter(),
            cases_path=CASES,
            nonce_factory=lambda: "fresh_nonce_0123456789abcdef",
        )
    )

    assert report.tier is ConformanceTier.INCOMPATIBLE
    serialized = str(report.to_dict())
    assert marker not in serialized
    assert [result.detail for result in report.results] == [
        "tool-call contract failed",
        "provider request failed",
    ]


def test_every_case_on_an_axis_must_pass() -> None:
    report = ConformanceReport(
        provider="fixture",
        model="fixture",
        informational={},
        results=(
            AxisResult("tool", "tool_call_schema", True, "passed"),
            AxisResult("system-1", "system_prompt_fidelity", True, "passed"),
            AxisResult(
                "system-2",
                "system_prompt_fidelity",
                False,
                "system-prompt fidelity failed",
            ),
        ),
    )

    assert report.tier is ConformanceTier.TIER_2


def test_case_specs_without_fresh_nonce_placeholder_fail_closed(
    tmp_path,
) -> None:
    document = json.loads(CASES.read_text())
    serialized = json.dumps(document).replace("{nonce}", "static-value")
    cases = tmp_path / "cases.json"
    cases.write_text(serialized)

    try:
        asyncio.run(
            run_conformance(
                PassingAdapter(),
                cases_path=cases,
                nonce_factory=lambda: "fresh_nonce_0123456789abcdef",
            )
        )
    except ValueError as error:
        assert str(error) == "invalid conformance case spec"
    else:
        raise AssertionError("static conformance cases must be rejected")
