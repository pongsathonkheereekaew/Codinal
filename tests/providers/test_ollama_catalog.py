from __future__ import annotations

from types import SimpleNamespace
from urllib.error import URLError
from urllib.request import ProxyHandler

from runtime.providers.ollama import discover_ollama_models


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, _limit: int | None = None) -> bytes:
        return self._body


def test_discover_ollama_models_returns_prefixed_unique_names(monkeypatch) -> None:
    def open_request(request, *, timeout):
        assert request.full_url == "http://127.0.0.1:11434/api/tags"
        assert timeout == 0.75
        return _Response(
            b'{"models":[{"name":"qwen3:8b"},{"name":"llama3.2"},'
            b'{"name":"qwen3:8b"},{"name":"  "},{"name":"qwen 3"},'
            b'{"name":"\xe6\xa8\xa1\xe5\x9e\x8b"},{"name":42}]}'
        )

    monkeypatch.setattr(
        "runtime.providers.ollama.build_opener",
        lambda *_handlers: SimpleNamespace(open=open_request),
    )

    assert discover_ollama_models() == {
        "available": True,
        "models": ["ollama:qwen3:8b", "ollama:llama3.2"],
    }


def test_discover_ollama_models_is_unavailable_when_local_service_is_down(
    monkeypatch,
) -> None:
    def open_request(_request, *, timeout):
        assert timeout == 0.75
        raise URLError("connection refused")

    monkeypatch.setattr(
        "runtime.providers.ollama.build_opener",
        lambda *_handlers: SimpleNamespace(open=open_request),
    )

    assert discover_ollama_models() == {"available": False, "models": []}


def test_discover_ollama_models_disables_proxy_handlers(monkeypatch) -> None:
    handlers = []

    def make_opener(*configured_handlers):
        handlers.extend(configured_handlers)
        return SimpleNamespace(
            open=lambda _request, *, timeout: _Response(b'{"models":[]}')
        )

    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:8080")
    monkeypatch.setattr("runtime.providers.ollama.build_opener", make_opener)

    assert discover_ollama_models() == {"available": True, "models": []}
    proxy = next(handler for handler in handlers if isinstance(handler, ProxyHandler))
    assert proxy.proxies == {}
