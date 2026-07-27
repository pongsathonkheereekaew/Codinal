"""Helper process for real SIGKILL turn-recovery tests."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

import runtime.control_plane.server as server_module
from runtime.control_plane.server import ServerConfig, build_services
from runtime.policy import ApprovalOutcome, ToolManifest
from runtime.providers import (
    AssistantTurn,
    ModelCapabilities,
    ProviderClient,
    StreamChunk,
    ToolCall,
)
from runtime.sessions import TurnStatus
from runtime.storage import ConversationStore
from runtime.tools import ToolRegistry


class AwaitingWriteProvider(ProviderClient):
    def complete(self, **_kwargs):
        return AssistantTurn(
            tool_calls=[
                ToolCall(
                    "provider/crash-window",
                    "write_file",
                    {
                        "path": "recovered-after-kill.txt",
                        "content": "executed once after restart\n",
                    },
                )
            ]
        )

    def capabilities(self, _model):
        return ModelCapabilities()


class ParallelReadProvider(ProviderClient):
    def complete(self, **_kwargs):
        return AssistantTurn(
            tool_calls=[
                ToolCall(call_id, "read_file", {"path": call_id})
                for call_id in ("call-1", "call-2")
            ]
        )

    def capabilities(self, _model):
        return ModelCapabilities()


class StreamingCrashProvider(ProviderClient):
    def __init__(self, marker: Path):
        self.marker = marker

    def complete(self, **_kwargs):
        raise AssertionError("stream path required")

    def stream(self, **_kwargs):
        yield StreamChunk(text_delta="partial before crash")
        self.marker.write_text("stream blocked\n", encoding="utf-8")
        while True:
            time.sleep(0.05)

    def capabilities(self, _model):
        return ModelCapabilities()


class PlanProposalProvider(ProviderClient):
    """Emits propose_plan; the turn parks in AWAITING_APPROVAL until decided."""

    def complete(self, **_kwargs):
        return AssistantTurn(
            tool_calls=[
                ToolCall(
                    "provider/plan-crash-window",
                    "propose_plan",
                    {"plan": "1. Inspect\n2. Implement"},
                )
            ]
        )

    def capabilities(self, _model):
        return ModelCapabilities()


class ShellExecProvider(ProviderClient):
    """Emits a run_shell call that blocks (so it is EXECUTING at crash time)."""

    def complete(self, **_kwargs):
        return AssistantTurn(
            tool_calls=[
                ToolCall(
                    "provider/shell-crash-window",
                    "run_shell",
                    {"command": "sleep 30"},
                )
            ]
        )

    def capabilities(self, _model):
        return ModelCapabilities()


def blocking_registry(roots) -> ToolRegistry:
    registry = ToolRegistry(ToolManifest())

    def read_file(path: str):
        marker = roots[0].path / f"{path}.started"
        marker.write_text("started\n", encoding="utf-8")
        while True:
            time.sleep(0.05)

    registry.register(
        read_file,
        schema={
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "blocking crash-test read",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
    )
    return registry


async def run(
    mode: str,
    data_dir: Path,
    workspace: Path,
    ready: Path,
) -> None:
    provider: ProviderClient
    agent = "code"
    turn_mode = None
    user_input = "run two reads"
    if mode == "approval":
        provider = AwaitingWriteProvider()
        user_input = "create recovered-after-kill.txt"
    elif mode == "parallel":
        provider = ParallelReadProvider()
        server_module.build_core_registry = blocking_registry
    elif mode == "streaming":
        provider = StreamingCrashProvider(
            workspace / "stream.started"
        )
    elif mode == "plan":
        provider = PlanProposalProvider()
        agent = "plan"
        turn_mode = "plan"
        user_input = "plan the change"
    elif mode == "shell":
        provider = ShellExecProvider()
        user_input = "run a long shell command"
    else:
        raise ValueError("unsupported crash worker mode")

    async def _auto_approve(_request):
        return ApprovalOutcome.ONCE

    build_kwargs = {"provider": provider}
    if mode == "shell":
        # run_shell is EXEC-risk; auto-approve so it actually starts executing
        # (we want it in-flight at crash time, not awaiting approval).
        build_kwargs["approver"] = _auto_approve
    services = build_services(
        ServerConfig(
            token="worker-session-token-with-at-least-32-characters",
            port=43123,
            data_dir=data_dir,
            default_model="openai:gpt-test",
        ),
        **build_kwargs,
    )
    start_kwargs = {
        "user_input": user_input,
        "workspace": workspace,
        "agent": agent,
    }
    if turn_mode is not None:
        start_kwargs["mode"] = turn_mode
    await services.turns.start("session-kill", **start_kwargs)
    if mode == "parallel":
        while True:
            observer = ConversationStore(data_dir)
            record = observer.load("session-kill")
            observer.close()
            if (
                record is not None
                and record.turn_checkpoint.status
                is TurnStatus.EXECUTING
                and set(
                    record.turn_checkpoint.active_tool_call_ids
                )
                == {"call-1", "call-2"}
                and all(
                    (workspace / f"{call_id}.started").exists()
                    for call_id in ("call-1", "call-2")
                )
            ):
                break
            await asyncio.sleep(0.01)
        ready.write_text("parallel checkpoint durable\n", encoding="utf-8")
        os.kill(os.getpid(), signal.SIGSTOP)
        return
    if mode == "streaming":
        while True:
            observer = ConversationStore(data_dir)
            record = observer.load("session-kill")
            observer.close()
            if (
                record is not None
                and record.turn_checkpoint.status
                is TurnStatus.RUNNING
                and (workspace / "stream.started").exists()
            ):
                break
            await asyncio.sleep(0.01)
        ready.write_text("stream checkpoint durable\n", encoding="utf-8")
        os.kill(os.getpid(), signal.SIGSTOP)
        return
    if mode == "plan":
        # Wait until the plan proposal is pending (AWAITING_APPROVAL).
        interactions = getattr(services, "interactions", None)
        while True:
            observer = ConversationStore(data_dir)
            record = observer.load("session-kill")
            observer.close()
            pending = (
                interactions.pending("session-kill")
                if interactions is not None and hasattr(
                    interactions, "pending"
                )
                else []
            )
            if (
                record is not None
                and record.turn_checkpoint.status
                is TurnStatus.AWAITING_APPROVAL
                and any(
                    item.get("kind") == "plan" for item in pending
                )
            ):
                break
            await asyncio.sleep(0.01)
        ready.write_text(
            json.dumps(
                {
                    "interaction_id": next(
                        item["interaction_id"]
                        for item in pending
                        if item.get("kind") == "plan"
                    )
                }
            ),
            encoding="utf-8",
        )
        os.kill(os.getpid(), signal.SIGSTOP)
        return
    if mode == "shell":
        # Wait until the run_shell call is EXECUTING (in flight at crash).
        while True:
            observer = ConversationStore(data_dir)
            record = observer.load("session-kill")
            observer.close()
            if (
                record is not None
                and record.turn_checkpoint.status
                is TurnStatus.EXECUTING
                and "provider/shell-crash-window"
                in set(
                    record.turn_checkpoint.active_tool_call_ids
                )
            ):
                break
            await asyncio.sleep(0.01)
        ready.write_text(
            "shell executing\n", encoding="utf-8"
        )
        os.kill(os.getpid(), signal.SIGSTOP)
        return
    approval = None
    while approval is None:
        pending = services.approvals.pending("session-kill")
        if pending:
            approval = pending[0]
        else:
            await asyncio.sleep(0.01)
    while True:
        observer = ConversationStore(data_dir)
        record = observer.load("session-kill")
        observer.close()
        if (
            record is not None
            and record.turn_checkpoint.status
            is TurnStatus.AWAITING_APPROVAL
        ):
            break
        await asyncio.sleep(0.01)
    if not services.approvals.resolve(
        "session-kill",
        approval["approval_id"],
        ApprovalOutcome.ONCE,
    ):
        raise RuntimeError("approval resolution failed")
    ready.write_text(
        json.dumps({"approval_id": approval["approval_id"]}),
        encoding="utf-8",
    )
    os.kill(os.getpid(), signal.SIGSTOP)


if __name__ == "__main__":
    asyncio.run(
        run(
            sys.argv[1],
            Path(sys.argv[2]),
            Path(sys.argv[3]),
            Path(sys.argv[4]),
        )
    )
