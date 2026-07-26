import pytest

from runtime.policy import ToolCallValidationError, parse_tool_calls


def test_policy_parser_accepts_strict_normalized_tool_calls() -> None:
    calls = parse_tool_calls(
        [
            {
                "id": "call_01",
                "name": "workspace.read_file",
                "arguments": {
                    "path": "README.md",
                    "line": 1,
                    "options": ["safe"],
                },
            }
        ]
    )

    assert len(calls) == 1
    assert calls[0].id == "call_01"
    assert calls[0].name == "workspace.read_file"
    assert calls[0].arguments == {
        "path": "README.md",
        "line": 1,
        "options": ["safe"],
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "call_01", "name": "tool", "arguments": {}},
        [{"id": "call_01", "name": "tool", "arguments": "{}"}],
        [
            {
                "id": "call_01",
                "name": "tool",
                "arguments": "must-not-echo",
            }
        ],
        [{"id": "call_01", "name": "bad/name", "arguments": {}}],
        [{"id": "call_01", "name": "tool", "arguments": {}, "extra": True}],
        [
            {"id": "duplicate", "name": "tool", "arguments": {}},
            {"id": "duplicate", "name": "tool", "arguments": {}},
        ],
        [{"id": "call_01", "name": "tool", "arguments": {"x": float("nan")}}],
    ],
)
def test_policy_parser_rejects_non_contract_payloads_without_echo(
    payload,
) -> None:
    marker = "must-not-echo"

    with pytest.raises(ToolCallValidationError) as caught:
        parse_tool_calls(payload)

    assert str(caught.value) == "invalid tool-call payload"
    assert marker not in str(caught.value)


def test_policy_parser_rejects_recursion_bombs_as_validation_errors() -> None:
    arguments = {}
    cursor = arguments
    for _ in range(1200):
        cursor["nested"] = {}
        cursor = cursor["nested"]

    with pytest.raises(
        ToolCallValidationError,
        match="^invalid tool-call payload$",
    ):
        parse_tool_calls(
            [{"id": "call_01", "name": "tool", "arguments": arguments}]
        )
