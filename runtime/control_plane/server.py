"""Standalone sidecar configuration and startup."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import uvicorn

from runtime.events import EventHub
from runtime.oauth import OAuthCoordinator
from runtime.secrets import ProviderSecretService, load_secret_bootstrap
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
    secrets: ProviderSecretService
    oauth: OAuthCoordinator


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


def build_services(
    config: ServerConfig,
    secrets: ProviderSecretService | None = None,
    oauth: OAuthCoordinator | None = None,
) -> StandaloneServices:
    return StandaloneServices(
        events=EventHub(),
        settings=SettingsService(
            JsonPreferenceStore(config.data_dir / "settings.json"),
            default_model=config.default_model,
        ),
        secrets=secrets or ProviderSecretService(),
        oauth=oauth or OAuthCoordinator(),
    )


def load_runtime_secrets(stream: TextIO) -> ProviderSecretService:
    channel = os.environ.pop("CODINAL_SECRET_BOOTSTRAP", "")
    if not channel:
        return ProviderSecretService()
    if channel != "stdin-v1":
        raise ValueError("unsupported secret bootstrap channel")
    return load_secret_bootstrap(stream)


def run() -> None:
    config = load_server_config()
    app = create_control_plane_app(
        token=config.token,
        services=build_services(config, load_runtime_secrets(sys.stdin)),
    )
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        access_log=False,
        server_header=False,
    )
