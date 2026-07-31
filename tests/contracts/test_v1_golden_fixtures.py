"""Golden v1 fixtures consumed by both reference and native runtimes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from runtime.control_plane import create_control_plane_app
from runtime.control_plane.contracts import v1_route_surface, v1_route_surface_json
from runtime.control_plane.server import ServerConfig, build_services
from runtime.events import EventHub
from runtime.secrets import ProviderSecretService


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "contracts" / "v1" / "control-plane.json"
STORAGE_FIXTURE_PATH = ROOT / "contracts" / "v1" / "storage.json"
TOKEN = "fixture-session-token-with-at-least-32-characters"


class _Settings:
    def view(self) -> dict[str, object]:
        return {"model": "fixture/model", "models": ["fixture/model"]}


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _storage_fixture() -> dict[str, object]:
    return json.loads(STORAGE_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_golden_control_plane_fixture_is_versioned_and_secret_free() -> None:
    fixture = _fixture()

    assert fixture["fixture_version"] == 1
    assert fixture["contract"] == "codinal.control-plane.v1"
    payload = dict(fixture)
    payload.pop("redaction")
    serialized = json.dumps(payload, sort_keys=True).lower()
    for marker in fixture["redaction"]["forbidden_value_markers"]:
        assert marker not in serialized


def test_reference_http_behavior_matches_golden_fixture() -> None:
    services = SimpleNamespace(
        events=EventHub(),
        settings=_Settings(),
        secrets=ProviderSecretService(),
    )
    client = TestClient(create_control_plane_app(token=TOKEN, services=services))

    for case in _fixture()["http"]:
        request = case["request"]
        headers = dict(request["headers"])
        if headers.get("authorization") == "Bearer <session-token>":
            headers["authorization"] = f"Bearer {TOKEN}"
        response = client.request(
            request["method"], request["path"], headers=headers
        )
        expected = case["response"]
        assert response.status_code == expected["status"], case["id"]
        assert response.json() == expected["json"], case["id"]
        for name, value in expected.get("headers", {}).items():
            assert response.headers[name] == value, case["id"]


def test_every_reference_v1_route_matches_golden_auth_negative_case(
    tmp_path: Path,
) -> None:
    services = build_services(
        ServerConfig(
            token=TOKEN,
            port=3000,
            data_dir=tmp_path,
            default_model="fixture/model",
        )
    )
    app = create_control_plane_app(token=TOKEN, services=services)
    client = TestClient(app)
    expected = _fixture()["all_v1_http_routes"]
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", "").startswith("/v1/")
    ]
    assert routes
    surface = v1_route_surface(app)
    assert surface == sorted(
        surface,
        key=lambda item: (item["path"], item["kind"], item["methods"]),
    )
    expected_surface = _fixture()["route_surface"]
    assert len(surface) == expected_surface["count"]
    canonical = v1_route_surface_json(app)
    assert json.loads(canonical) == surface
    assert hashlib.sha256(canonical).hexdigest() == expected_surface[
        "sha256"
    ]
    for route in routes:
        path = route.path.replace("{session_id}", "fixture-session")
        path = path.replace("{approval_id}", "0" * 32)
        path = path.replace("{package_id}", "fixture-package")
        path = path.replace("{goal_id}", "fixture-goal")
        path = path.replace("{build_id}", "fixture-build")
        path = path.replace("{worker_id}", "fixture-worker")
        path = path.replace("{interaction_id}", "fixture-interaction")
        path = path.replace("{server_name}", "fixture-server")
        path = path.replace("{checkpoint_id}", "fixture-checkpoint")
        path = path.replace("{slug}", "fixture")
        method = next(iter(route.methods - {"HEAD", "OPTIONS"}))
        response = client.request(method, path)
        assert response.status_code == expected["unauthenticated_status"], path
        assert response.headers["www-authenticate"] == expected[
            "www_authenticate"
        ], path


def test_reference_websocket_behavior_matches_golden_fixture() -> None:
    services = SimpleNamespace(
        events=EventHub(), settings=_Settings(), secrets=ProviderSecretService()
    )
    client = TestClient(create_control_plane_app(token=TOKEN, services=services))

    for case in _fixture()["websocket"]:
        path = case["path"]
        protocols = [
            protocol.replace("<session-token>", TOKEN)
            for protocol in case["protocols"]
        ]
        if "close_code" in case:
            with pytest.raises(WebSocketDisconnect) as error:
                with client.websocket_connect(
                    path,
                    subprotocols=protocols,
                    headers={"Origin": case.get("origin", "")},
                ):
                    pass
            assert error.value.code == case["close_code"], case["id"]
            continue

        assert all(part not in path for part in case["forbidden_url_parts"])
        with client.websocket_connect(path, subprotocols=protocols) as socket:
            assert socket.accepted_subprotocol == case["accepted_subprotocol"]
            socket.send_text("ping")
            assert socket.receive_json() == case["ping_response"]


def test_reference_event_order_matches_golden_fixture() -> None:
    async def collect() -> list[str]:
        hub = EventHub()
        received: list[str] = []

        async def listener(event: dict[str, object]) -> None:
            received.append(str(event["type"]))

        unsubscribe = hub.subscribe_session("fixture-session", listener)
        for event_type in _fixture()["events"][0]["sequence"]:
            await hub.publish_session("fixture-session", {"type": event_type})
        unsubscribe()
        return received

    assert asyncio.run(collect()) == _fixture()["events"][0]["sequence"]


def test_build_services_sqlite_inventory_matches_golden_fixture(tmp_path: Path) -> None:
    build_services(
        ServerConfig(
            token=TOKEN,
            port=3000,
            data_dir=tmp_path,
            default_model="fixture/model",
        )
    )
    actual = []
    for path in sorted(tmp_path.glob("*.db")):
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        try:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                )
            ]
            actual.append(
                {
                    "file": path.name,
                    "user_version": connection.execute(
                        "PRAGMA user_version"
                    ).fetchone()[0],
                    "tables": tables,
                }
            )
        finally:
            connection.close()

    fixture = _storage_fixture()
    assert fixture["fixture_version"] == 1
    assert fixture["contract"] == "codinal.sqlite.v1"
    assert actual == fixture["databases"]
