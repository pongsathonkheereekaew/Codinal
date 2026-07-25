import asyncio
import io
import os
from pathlib import Path

import pytest

from runtime.control_plane.server import (
    ServerConfig,
    build_services,
    load_runtime_secrets,
    load_server_config,
)
from runtime.turns import SessionNotFoundError


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
