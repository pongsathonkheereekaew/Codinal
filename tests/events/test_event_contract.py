from runtime.events import Event, EventType


def test_turn_events_are_provider_neutral_serializable_values() -> None:
    event = Event(
        EventType.TOOL_PROPOSED,
        {"tool": "read_file", "arguments": {"path": "README.md"}},
    )

    assert event.type.value == "tool_proposed"
    assert event.data["tool"] == "read_file"
