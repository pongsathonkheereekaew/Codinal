"""Standalone sidecar configuration and startup."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import uvicorn

from runtime.events import EventHub
from runtime.settings import JsonPreferenceStore, SettingsService

from .app import create_control_plane_app
from .auth import validate_session_token


@dataclass(frozen=True)
class ServerConfig:
    token: str
    port: int
    data_dir: Path
    default_model: str
    host: str = "127.0.0.1"


@dataclass(frozen=True)
class StandaloneServices:
    events: EventHub
    settings: SettingsService


def load_server_config() -> ServerConfig:
    token = os.environ.pop("CODINAL_SESSION_TOKEN", "")
    if not token:
        raise ValueError("CODINAL_SESSION_TOKEN is required")
    validate_session_token(token)

    port_value = os.environ.get("CODINAL_PORT")
    if port_value is None:
        raise ValueError("CODINAL_PORT is required")
    try:
        port = int(port_value)
    except ValueError as error:
        raise ValueError("CODINAL_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("CODINAL_PORT must be between 1 and 65535")

    data_dir = Path(
        os.environ.get(
            "CODINAL_DATA_DIR",
            "~/Library/Application Support/Codinal",
        )
    ).expanduser()
    default_model = (
        os.environ.get("CODINAL_DEFAULT_MODEL", "openai/gpt-5").strip()
        or "openai/gpt-5"
    )
    return ServerConfig(
        token=token,
        port=port,
        data_dir=data_dir,
        default_model=default_model,
    )


def build_services(config: ServerConfig) -> StandaloneServices:
    return StandaloneServices(
        events=EventHub(),
        settings=SettingsService(
            JsonPreferenceStore(config.data_dir / "settings.json"),
            default_model=config.default_model,
        ),
    )


def run() -> None:
    config = load_server_config()
    app = create_control_plane_app(
        token=config.token,
        services=build_services(config),
    )
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        access_log=False,
        server_header=False,
    )
