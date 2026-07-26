import asyncio
import hashlib
import json

import pytest

from runtime.interactions import (
    InteractionBroker,
    InteractionPersistenceError,
)


class Decisions:
    def __init__(self):
        self.values = {}

    def load_interaction_decision(
        self,
        session_id,
        tool_call_id,
        kind,
        fingerprint,
    ):
        return self.values.get(
            (session_id, tool_call_id, kind, fingerprint)
        )

    def save_interaction_decision(
        self,
        session_id,
        tool_call_id,
        kind,
        fingerprint,
        response,
    ):
        self.values[
            (session_id, tool_call_id, kind, fingerprint)
        ] = response

    def ensure_plan_artifact(
        self,
        session_id,
        plan_id,
        tool_call_id,
        arguments,
    ):
        return {
            "plan_id": plan_id,
            "session_id": session_id,
            "tool_call_id": tool_call_id,
            "plan": arguments["plan"],
            "tasks": arguments["tasks"],
            "revision": 1,
        }

    def save_plan_interaction_decision(
        self,
        session_id,
        tool_call_id,
        fingerprint,
        response,
        _plan_id,
    ):
        self.save_interaction_decision(
            session_id,
            tool_call_id,
            "plan",
            fingerprint,
            response,
        )


def test_resolved_question_is_durable_and_reused_after_restart():
    async def scenario():
        decisions = Decisions()
        first = InteractionBroker(decisions)
        requester = first.requester("session-1", "question")
        awaitable = requester({"question": "Database?"}, "call-1")
        interaction_id = first.interaction_id(
            "session-1",
            "call-1",
            "question",
        )
        assert first.pending("session-1") == [
            {
                "interaction_id": interaction_id,
                "kind": "question",
                "arguments": {"question": "Database?"},
            }
        ]
        assert first.resolve(
            "session-1",
            interaction_id,
            {"answer": "PostgreSQL"},
        )
        assert await awaitable == {"answer": "PostgreSQL"}

        reopened = InteractionBroker(decisions)
        replay = reopened.requester(
            "session-1",
            "question",
        )({"question": "Database?"}, "call-1")
        assert await replay == {"answer": "PostgreSQL"}
        assert reopened.pending("session-1") == []

    asyncio.run(scenario())


def test_response_validation_and_persistence_failure_do_not_resolve():
    class Failing(Decisions):
        def save_interaction_decision(self, *_args):
            raise OSError("private disk detail")

    async def scenario():
        broker = InteractionBroker(Failing())
        awaitable = broker.requester(
            "session-1",
            "plan",
        )(
            {
                "plan": "Build",
                "tasks": [
                    {
                        "id": "build",
                        "title": "Build",
                        "verification": "Focused test passes",
                    }
                ],
            },
            "call-1",
        )
        interaction_id = broker.interaction_id(
            "session-1",
            "call-1",
            "plan",
        )
        with pytest.raises(ValueError):
            broker.resolve(
                "session-1",
                interaction_id,
                {"approved": True, "mode": "unsafe"},
            )
        with pytest.raises(InteractionPersistenceError):
            broker.resolve(
                "session-1",
                interaction_id,
                {"approved": True, "mode": "interactive"},
            )
        broker.close()
        assert await awaitable == {
            "approved": False,
            "error": "runtime stopped",
        }

    asyncio.run(scenario())


def test_legacy_plan_decision_fingerprint_replays_after_upgrade():
    async def scenario():
        decisions = Decisions()
        payload = json.dumps(
            {
                "arguments": {"plan": "Legacy plan"},
                "kind": "plan",
            },
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        decisions.values[
            ("session-1", "call-legacy", "plan", fingerprint)
        ] = {"approved": True, "mode": "interactive"}

        broker = InteractionBroker(decisions)
        result = await broker.requester(
            "session-1",
            "plan",
        )({"plan": "Legacy plan"}, "call-legacy")

        assert result == {"approved": True, "mode": "interactive"}
        assert broker.pending("session-1") == []

    asyncio.run(scenario())
