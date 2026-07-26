import asyncio
import io
import os
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from runtime.control_plane.server import (
    ServerConfig,
    build_services,
    load_runtime_secrets,
    load_server_config,
)
from runtime.control_plane import create_control_plane_app
from runtime.turns import SessionNotFoundError
from runtime.workers import WorkerRecord
from runtime.policy import ToolCall
from runtime.providers import (
    AssistantTurn,
    ModelCapabilities,
    ProviderClient,
)


TOKEN = "test-session-token-with-at-least-32-characters"
SECRET_SYNC_TOKEN = "test-secret-sync-token-with-at-least-32-chars"


def test_server_config_is_loopback_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CODINAL_SESSION_TOKEN", TOKEN)
    monkeypatch.setenv("CODINAL_PORT", "43123")
    monkeypatch.setenv("CODINAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CODINAL_DEFAULT_MODEL", "test/provider-model")

    config = load_server_config()

    assert config.host == "127.0.0.1"
    assert config.port == 43123
    assert config.token == TOKEN
    assert config.data_dir == tmp_path
    assert config.default_model == "test/provider-model"
    assert "CODINAL_SESSION_TOKEN" not in os.environ


def test_server_config_requires_session_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODINAL_SESSION_TOKEN", raising=False)

    with pytest.raises(ValueError, match="CODINAL_SESSION_TOKEN"):
        load_server_config()


def test_server_config_requires_host_selected_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODINAL_SESSION_TOKEN", TOKEN)
    monkeypatch.delenv("CODINAL_PORT", raising=False)

    with pytest.raises(ValueError, match="CODINAL_PORT is required"):
        load_server_config()


@pytest.mark.parametrize("value", ["0", "65536", "not-a-port"])
def test_server_config_rejects_invalid_port(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("CODINAL_SESSION_TOKEN", TOKEN)
    monkeypatch.setenv("CODINAL_PORT", value)

    with pytest.raises(ValueError, match="CODINAL_PORT"):
        load_server_config()


def test_runtime_secrets_load_only_from_marked_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODINAL_SECRET_BOOTSTRAP", "stdin-v1")
    stream = io.StringIO(
        '{"sync_token":"' + SECRET_SYNC_TOKEN + '",'
        '"profiles":{"provider:openai":{"api_key":"secret-value"}}}'
    )

    secrets = load_runtime_secrets(stream)

    assert secrets.get("provider:openai") == {"api_key": "secret-value"}
    assert secrets.authorize_sync(SECRET_SYNC_TOKEN)
    assert "CODINAL_SECRET_BOOTSTRAP" not in os.environ


def test_runtime_secrets_ignore_unmarked_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODINAL_SECRET_BOOTSTRAP", raising=False)

    secrets = load_runtime_secrets(io.StringIO("must-not-be-read"))

    assert secrets.status() == [
        {"provider": "anthropic", "configured": False},
        {"provider": "gemini", "configured": False},
        {"provider": "openai", "configured": False},
    ]


def test_runtime_secrets_reject_unknown_bootstrap_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODINAL_SECRET_BOOTSTRAP", "environment")

    with pytest.raises(ValueError, match="unsupported secret bootstrap"):
        load_runtime_secrets(
            io.StringIO(
                '{"sync_token":"' + SECRET_SYNC_TOKEN + '","profiles":{}}'
            )
        )


def test_standalone_turn_service_rejects_missing_session_without_workspace(
    tmp_path,
) -> None:
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=43123,
            data_dir=tmp_path,
            default_model="openai:gpt-test",
        )
    )

    assert services.turns.interrupt("missing") is False
    with pytest.raises(SessionNotFoundError):
        asyncio.run(
            services.turns.start(
                "missing",
                user_input="hello",
            )
        )


def test_worker_engine_exposes_no_authority_expansion_or_adoption_tools(
    tmp_path,
) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", workspace], check=True)
    (workspace / "runtime").mkdir()
    (workspace / "runtime" / "owned.py").write_text("old\n")
    subprocess.run(["git", "-C", workspace, "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            workspace,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.test",
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=43123,
            data_dir=tmp_path / "data",
            default_model="openai:gpt-test",
        )
    )
    parent = services.sessions.get_engine(
        "session-parent",
        workspace=workspace,
    )
    assert parent is not None
    assert services.sessions.persist("session-parent")
    services.workers.store.create(
        WorkerRecord(
            worker_id="worker-security",
            parent_session_id="session-parent",
            child_session_id="session-worker-security",
            task="Edit owned file",
            ownership=("runtime",),
            dependencies=(),
            model="openai:gpt-test",
        )
    )
    created = services.sessions.create_worker_session(
        "session-parent",
        worker_id="worker-security",
        child_session_id="session-worker-security",
        model="openai:gpt-test",
    )
    worker = services.sessions.get_engine("session-worker-security")

    assert created["ok"] is True
    assert worker is not None
    assert worker.permissions.write_scope == ("runtime",)
    assert "request_directory" not in worker.registry.names()
    assert "git_apply" not in worker.registry.names()
    assert "git_commit" not in worker.registry.names()
    assert worker.permissions.session_allow_tools == set()
    assert worker.permissions.session_allow_commands == set()

    result = worker.registry.execute(
        "run_shell",
        {
            "command": (
                "python3 -c \"from pathlib import Path; "
                "Path('runtime/owned.py').write_text('new\\\\n'); "
                "Path('README.md').write_text('escaped\\\\n')\""
            )
        },
    )

    assert result["exit_code"] != 0
    assert (worker.roots[0].path / "runtime" / "owned.py").read_text() == "old\n"
    assert not (worker.roots[0].path / "README.md").exists()


def test_worker_runs_in_child_worktree_and_adopts_into_parent_session(
    tmp_path,
) -> None:
    class WorkerProvider(ProviderClient):
        def __init__(self):
            self.observed = ""

        def complete(self, *, messages, **_kwargs):
            task = next(
                (
                    message.get("content", "")
                    for message in messages
                    if message.get("role") == "user"
                ),
                "",
            )
            used_tool = any(
                message.get("role") == "tool"
                for message in messages
            )
            if task == "Update the owned file" and not used_tool:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "worker-write",
                            "write_file",
                            {
                                "path": "runtime/owned.py",
                                "content": "worker\n",
                            },
                        )
                    ]
                )
            if task == "Read predecessor output" and not used_tool:
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "worker-read",
                            "read_file",
                            {"path": "runtime/owned.py"},
                        )
                    ]
                )
            if task == "Read predecessor output":
                self.observed = repr(messages)
            return AssistantTurn(text="worker complete")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "repo"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", workspace], check=True)
    (workspace / "runtime").mkdir()
    (workspace / "runtime" / "owned.py").write_text("base\n")
    subprocess.run(["git", "-C", workspace, "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            workspace,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.test",
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )
    provider = WorkerProvider()
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=43123,
            data_dir=tmp_path / "data",
            default_model="openai:gpt-test",
        ),
        provider=provider,
    )
    parent = services.sessions.get_engine(
        "session-parent",
        workspace=workspace,
    )
    assert parent is not None
    assert services.sessions.persist("session-parent")

    async def scenario():
        worker = await services.workers.create(
            "session-parent",
            task="Update the owned file",
            ownership=("runtime",),
            model="openai:gpt-test",
        )
        dependent = await services.workers.create(
            "session-parent",
            task="Read predecessor output",
            ownership=("tests",),
            dependencies=(worker.worker_id,),
            model="openai:gpt-test",
        )
        assert dependent.state.value == "blocked"
        await services.workers.wait_idle()
        finished = services.workers.load(worker.worker_id)
        adopted = await services.workers.adopt(worker.worker_id)
        await services.workers.wait_idle()
        return (
            finished,
            adopted,
            services.workers.load(dependent.worker_id),
        )

    finished, adopted, dependent = asyncio.run(scenario())

    assert finished.state.value == "succeeded"
    assert finished.commit
    assert adopted["ok"] is True
    assert dependent.state.value == "succeeded"
    assert "worker" in provider.observed
    assert (
        parent.roots[0].path / "runtime" / "owned.py"
    ).read_text() == "worker\n"
    assert (workspace / "runtime" / "owned.py").read_text() == "base\n"


def test_worker_http_lifecycle_survives_restart_before_adoption(
    tmp_path,
) -> None:
    class WriteProvider(ProviderClient):
        def complete(self, *, messages, **_kwargs):
            if not any(
                message.get("role") == "tool"
                for message in messages
            ):
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            "write-after-restart",
                            "write_file",
                            {
                                "path": "runtime/owned.py",
                                "content": "durable\n",
                            },
                        )
                    ]
                )
            return AssistantTurn(text="durable worker complete")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "repo"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", workspace], check=True)
    (workspace / "runtime").mkdir()
    (workspace / "runtime" / "owned.py").write_text("base\n")
    subprocess.run(["git", "-C", workspace, "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            workspace,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.test",
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    first = build_services(config, provider=WriteProvider())
    parent = first.sessions.get_engine(
        "session-parent",
        workspace=workspace,
    )
    assert parent is not None
    assert first.sessions.persist("session-parent")
    auth = {"Authorization": f"Bearer {TOKEN}"}
    with TestClient(
        create_control_plane_app(token=TOKEN, services=first)
    ) as client:
        created = client.post(
            "/v1/sessions/session-parent/workers",
            headers=auth,
            json={
                "task": "Write durable worker output",
                "ownership": ["runtime"],
                "dependencies": [],
                "model": "openai:gpt-test",
            },
        )
        assert created.status_code == 202
        worker_id = created.json()["worker_id"]
        for _attempt in range(100):
            workers = client.get(
                "/v1/sessions/session-parent/workers",
                headers=auth,
            ).json()
            state = next(
                worker["state"]
                for worker in workers
                if worker["worker_id"] == worker_id
            )
            if state == "succeeded":
                break
            time.sleep(0.02)
        assert state == "succeeded"

    restarted = build_services(config, provider=WriteProvider())
    with TestClient(
        create_control_plane_app(token=TOKEN, services=restarted)
    ) as client:
        workers = client.get(
            "/v1/sessions/session-parent/workers",
            headers=auth,
        )
        adopted = client.post(
            f"/v1/workers/{worker_id}/adopt",
            headers=auth,
        )

        assert workers.status_code == 200
        assert workers.json()[0]["state"] == "succeeded"
        assert adopted.status_code == 200
        assert adopted.json()["ok"] is True
        parent_record = restarted.git.load("session-parent")
        assert parent_record is not None
        parent_path = parent_record.worktree_path

    assert (
        parent_path / "runtime" / "owned.py"
    ).read_text() == "durable\n"
    assert (workspace / "runtime" / "owned.py").read_text() == "base\n"


def test_plan_build_compares_three_isolated_candidates_and_adopts_selection(
    tmp_path,
) -> None:
    class CandidateProvider(ProviderClient):
        def __init__(self):
            self.seen_content = []

        def complete(self, *, messages, model, **_kwargs):
            self.seen_content.extend(
                str(message.get("content", ""))
                for message in messages
            )
            if not any(
                message.get("role") == "tool"
                for message in messages
            ):
                return AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            f"write-{model.rsplit(':', 1)[-1]}",
                            "write_file",
                            {
                                "path": "runtime/owned.py",
                                "content": f"{model}\n",
                            },
                        )
                    ]
                )
            return AssistantTurn(text=f"{model} candidate complete")

        def capabilities(self, _model):
            return ModelCapabilities()

    workspace = tmp_path / "repo"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", workspace], check=True)
    (workspace / "runtime").mkdir()
    (workspace / "runtime" / "owned.py").write_text("base\n")
    subprocess.run(["git", "-C", workspace, "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            workspace,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.test",
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )
    config = ServerConfig(
        token=TOKEN,
        port=43123,
        data_dir=tmp_path / "data",
        default_model="openai:gpt-test",
    )
    provider = CandidateProvider()
    first = build_services(config, provider=provider)
    parent = first.sessions.get_engine(
        "session-parent",
        workspace=workspace,
    )
    assert parent is not None
    parent.permissions.allow_tool_for_session("write_file")
    parent.permissions.allow_command_for_session(
        "printf inherited-authority"
    )
    parent.messages.append(
        {"role": "user", "content": "parent-secret-marker"}
    )
    assert first.sessions.persist("session-parent")
    plan_id = "a" * 32
    first.plans.ensure_plan_artifact(
        "session-parent",
        plan_id,
        "provider/plan-build",
        {
            "plan": "Compare parser implementations",
            "tasks": [
                {
                    "id": "parser",
                    "title": "Implement parser",
                    "verification": "Parser suite passes",
                }
            ],
        },
    )
    first.plans.save_plan_interaction_decision(
        "session-parent",
        "provider/plan-build",
        "b" * 64,
        {
            "approved": True,
            "mode": "interactive",
            "plan": "Compare parser implementations",
            "tasks": [
                {
                    "id": "parser",
                    "title": "Implement parser",
                    "verification": "Parser suite passes",
                }
            ],
            "selected_task_ids": ["parser"],
        },
        plan_id,
    )
    auth = {"Authorization": f"Bearer {TOKEN}"}
    with TestClient(
        create_control_plane_app(token=TOKEN, services=first)
    ) as client:
        created = client.post(
            "/v1/sessions/session-parent/plan-builds",
            headers=auth,
            json={
                "plan_id": plan_id,
                "tasks": [
                    {
                        "task_id": "parser",
                        "ownership": ["runtime"],
                        "candidates": [
                            {"model": "openai:first"},
                            {"model": "anthropic:second"},
                            {"model": "gemini:third"},
                        ],
                    }
                ],
            },
        )
        assert created.status_code == 202
        build_id = created.json()["build_id"]
        for _attempt in range(200):
            builds = client.get(
                "/v1/sessions/session-parent/plan-builds",
                headers=auth,
            ).json()
            build = next(
                item for item in builds if item["build_id"] == build_id
            )
            if build["state"] == "ready":
                break
            time.sleep(0.02)
        assert build["state"] == "ready"
        candidates = build["tasks"][0]["candidates"]
        assert len(candidates) == 3
        assert all(candidate["state"] == "succeeded" for candidate in candidates)
        winner = candidates[1]["worker_id"]
        loser = candidates[0]["worker_id"]
        reviewed = client.get(
            (
                f"/v1/plan-builds/{build_id}/candidates/"
                f"{winner}/diff"
            ),
            headers=auth,
        )
        assert reviewed.status_code == 200
        assert "+anthropic:second" in reviewed.json()["diff"]
        selected = client.post(
            f"/v1/plan-builds/{build_id}/select",
            headers=auth,
            json={"worker_id": winner},
        )
        assert selected.status_code == 200
        assert selected.json()["state"] == "selected"
        for candidate in candidates:
            child = first.plans.load(
                f"session-{candidate['worker_id']}"
            )
            assert child is not None
            assert child.grants == {"tools": [], "commands": []}
            assert child.extra_roots == []
        attacker = first.sessions.get_engine(
            f"session-{candidates[0]['worker_id']}"
        )
        sibling = first.git.load(
            f"session-{candidates[2]['worker_id']}"
        )
        assert attacker is not None
        assert sibling is not None
        escaped = sibling.worktree_path / "runtime" / "escaped.txt"
        cross_write = attacker.registry.execute(
            "run_shell",
            {
                "command": (
                    "python3 -c \"from pathlib import Path; "
                    f"Path({str(escaped)!r}).write_text('escaped')\""
                )
            },
        )
        assert cross_write["exit_code"] != 0
        assert not escaped.exists()
        assert all(
            "parent-secret-marker" not in content
            for content in provider.seen_content
        )

    restarted = build_services(config, provider=CandidateProvider())
    with TestClient(
        create_control_plane_app(token=TOKEN, services=restarted)
    ) as client:
        persisted = client.get(
            "/v1/sessions/session-parent/plan-builds",
            headers=auth,
        ).json()[0]
        bypass = client.post(
            f"/v1/workers/{loser}/adopt",
            headers=auth,
        )
        selected_bypass = client.post(
            f"/v1/workers/{winner}/adopt",
            headers=auth,
        )
        adopted = client.post(
            f"/v1/plan-builds/{build_id}/adopt",
            headers=auth,
        )

        assert persisted["state"] == "selected"
        assert persisted["tasks"][0]["selected_worker_id"] == winner
        assert bypass.status_code == 409
        assert "plan build adoption" in bypass.json()["detail"]
        assert selected_bypass.status_code == 409
        assert "plan build adoption" in selected_bypass.json()["detail"]
        assert adopted.status_code == 200
        assert adopted.json()["state"] == "adopted"
        workers = client.get(
            "/v1/sessions/session-parent/workers",
            headers=auth,
        ).json()
        states = {worker["worker_id"]: worker["state"] for worker in workers}
        assert states[winner] == "adopted"
        assert states[loser] == "succeeded"
        parent_record = restarted.git.load("session-parent")
        assert parent_record is not None
        parent_path = parent_record.worktree_path

    assert (parent_path / "runtime" / "owned.py").read_text() == (
        "anthropic:second\n"
    )
    assert (workspace / "runtime" / "owned.py").read_text() == "base\n"
