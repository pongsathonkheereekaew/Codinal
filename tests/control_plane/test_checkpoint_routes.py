from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.checkpoint_restore import CheckpointRestoreCoordinator
from runtime.control_plane import create_control_plane_app
from runtime.events import EventHub
from runtime.git import (
    CheckpointRestoreRecord,
    CheckpointRestoreState,
    CheckpointState,
    GitWorkspaceError,
)
from runtime.oauth import OAuthCoordinator
from runtime.secrets import ProviderSecretService


TOKEN = "test-session-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
CHECKPOINT_ID = "a" * 32


class FakeTurns:
    async def recover(self):
        return 0

    async def shutdown(self):
        return True

    def is_active(self, _session_id):
        return False

    async def restore_when_idle(self, restore):
        return restore()


class FakeGit:
    def __init__(self):
        self.actions = []
        self.restore_operation = None

    def load(self, session_id):
        return object() if session_id == "session-1" else None

    def list_checkpoints(self, _session_id):
        return [
            SimpleNamespace(
                checkpoint_id=CHECKPOINT_ID,
                before_message_count=2,
                after_message_count=4,
                created_at="2026-07-26T00:00:00Z",
            )
        ]

    def load_checkpoint(self, checkpoint_id):
        if checkpoint_id != CHECKPOINT_ID:
            return None
        return SimpleNamespace(
            checkpoint_id=checkpoint_id,
            session_id="session-1",
            before_message_count=2,
            state=CheckpointState.COMPLETED,
        )

    def restore_checkpoint_code(self, session_id, checkpoint_id):
        self.actions.append(("restore", session_id, checkpoint_id))
        return {"ok": True}

    def reapply_checkpoint_code(self, session_id, checkpoint_id):
        self.actions.append(("reapply", session_id, checkpoint_id))
        return {"ok": True}

    def discard_checkpoint_history(self, session_id, checkpoint_id):
        self.actions.append(("discard", session_id, checkpoint_id))
        return 1

    def begin_restore(self, session_id, checkpoint_id, scope):
        checkpoint = self.load_checkpoint(checkpoint_id)
        if (
            checkpoint is None
            or checkpoint.session_id != session_id
            or checkpoint.state is not CheckpointState.COMPLETED
        ):
            raise GitWorkspaceError("checkpoint not found")
        self.actions.append(("journal", session_id, checkpoint_id))
        self.restore_operation = CheckpointRestoreRecord(
            operation_id="b" * 32,
            checkpoint_id=checkpoint_id,
            session_id=session_id,
            scope=scope,
            state=CheckpointRestoreState.PREPARED,
            message_count=2,
            code_before_tree=(
                "c" * 40 if scope.value != "conversation" else ""
            ),
            code_after_tree=(
                "d" * 40 if scope.value != "conversation" else ""
            ),
            discard_checkpoint_ids=(
                (checkpoint_id,)
                if scope.value != "code"
                else ()
            ),
        )
        return self.restore_operation

    def pending_restores(self):
        return (
            [self.restore_operation]
            if self.restore_operation is not None
            else []
        )

    def resume_restore_code(self, operation_id):
        assert operation_id == "b" * 32
        return self.restore_checkpoint_code(
            "session-1",
            CHECKPOINT_ID,
        )

    def advance_restore(self, operation_id, state):
        assert operation_id == "b" * 32
        self.restore_operation = CheckpointRestoreRecord(
            **{
                **self.restore_operation.__dict__,
                "state": state,
            }
        )
        return self.restore_operation

    def finish_restore(self, operation_id):
        assert operation_id == "b" * 32
        self.actions.append(("finish", "session-1", CHECKPOINT_ID))
        self.restore_operation = None
        return True

    def discard_restore_history(self, operation_id):
        assert operation_id == "b" * 32
        return self.discard_checkpoint_history(
            "session-1",
            CHECKPOINT_ID,
        )

    def close(self):
        pass


class FailingSessions:
    def restore_conversation(self, _session_id, *, message_count):
        assert message_count == 2
        raise RuntimeError("conversation persistence failed")


class SuccessfulSessions:
    def restore_conversation(self, _session_id, *, message_count):
        assert message_count == 2
        return True


def make_client(*, sessions=None):
    git = FakeGit()
    session_control = sessions or FailingSessions()
    services = SimpleNamespace(
        events=EventHub(),
        settings=SimpleNamespace(view=lambda: {}),
        secrets=ProviderSecretService(),
        oauth=OAuthCoordinator(),
        turns=FakeTurns(),
        sessions=session_control,
        git=git,
        restores=CheckpointRestoreCoordinator(
            git=git,
            sessions=session_control,
        ),
        mcp=None,
        approvals=None,
    )
    return (
        TestClient(
            create_control_plane_app(
                token=TOKEN,
                services=services,
            )
        ),
        git,
    )


def test_checkpoint_routes_require_auth_and_validate_scope():
    client, _git = make_client()

    unauthorized = client.get(
        "/v1/sessions/session-1/checkpoints"
    )
    listed = client.get(
        "/v1/sessions/session-1/checkpoints",
        headers=AUTH,
    )
    invalid = client.post(
        (
            "/v1/sessions/session-1/checkpoints/"
            f"{CHECKPOINT_ID}/restore"
        ),
        headers=AUTH,
        json={"scope": "everything"},
    )

    assert unauthorized.status_code == 401
    assert listed.status_code == 200
    assert listed.json()[0]["checkpoint_id"] == CHECKPOINT_ID
    assert invalid.status_code == 400


def test_checkpoint_restore_payload_is_bounded():
    client, _git = make_client()

    response = client.post(
        (
            "/v1/sessions/session-1/checkpoints/"
            f"{CHECKPOINT_ID}/restore"
        ),
        headers={
            **AUTH,
            "Content-Type": "application/json",
        },
        content=b'{"scope":"code"}' + (b" " * 2048),
    )

    assert response.status_code == 400


def test_pending_checkpoint_cannot_be_restored():
    client, git = make_client(sessions=SuccessfulSessions())
    original_load = git.load_checkpoint

    def load_pending(checkpoint_id):
        checkpoint = original_load(checkpoint_id)
        checkpoint.state = CheckpointState.PENDING
        return checkpoint

    git.load_checkpoint = load_pending

    response = client.post(
        (
            "/v1/sessions/session-1/checkpoints/"
            f"{CHECKPOINT_ID}/restore"
        ),
        headers=AUTH,
        json={"scope": "conversation"},
    )

    assert response.status_code == 404
    assert git.actions == []


def test_combined_restore_keeps_journal_if_conversation_fails():
    client, git = make_client()

    response = client.post(
        (
            "/v1/sessions/session-1/checkpoints/"
            f"{CHECKPOINT_ID}/restore"
        ),
        headers=AUTH,
        json={"scope": "both"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "conversation persistence failed"
    )
    assert git.actions == [
        ("journal", "session-1", CHECKPOINT_ID),
        ("restore", "session-1", CHECKPOINT_ID),
    ]


def test_conversation_restore_discards_rewound_checkpoint_history():
    client, git = make_client(sessions=SuccessfulSessions())

    response = client.post(
        (
            "/v1/sessions/session-1/checkpoints/"
            f"{CHECKPOINT_ID}/restore"
        ),
        headers=AUTH,
        json={"scope": "conversation"},
    )

    assert response.status_code == 200
    assert git.actions == [
        ("journal", "session-1", CHECKPOINT_ID),
        ("discard", "session-1", CHECKPOINT_ID),
        ("finish", "session-1", CHECKPOINT_ID),
    ]


def test_code_only_restore_keeps_checkpoint_history():
    client, git = make_client(sessions=SuccessfulSessions())

    response = client.post(
        (
            "/v1/sessions/session-1/checkpoints/"
            f"{CHECKPOINT_ID}/restore"
        ),
        headers=AUTH,
        json={"scope": "code"},
    )

    assert response.status_code == 200
    assert git.actions == [
        ("journal", "session-1", CHECKPOINT_ID),
        ("restore", "session-1", CHECKPOINT_ID),
        ("finish", "session-1", CHECKPOINT_ID),
    ]
