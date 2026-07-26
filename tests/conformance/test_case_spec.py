import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]


def test_conformance_cases_match_policy_schema_and_cover_tier_one_axes() -> None:
    schema = json.loads(
        (ROOT / "harness/conformance/cases.schema.json").read_text()
    )
    cases = json.loads(
        (ROOT / "harness/conformance/cases.json").read_text()
    )

    Draft202012Validator(schema).validate(cases)

    assert {case["axis"] for case in cases["cases"]} == {
        "tool_call_schema",
        "system_prompt_fidelity",
    }
    assert all("{nonce}" in json.dumps(case) for case in cases["cases"])
