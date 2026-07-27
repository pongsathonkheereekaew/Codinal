"""FailoverRouter tests — chain order, pre-first-token failover, mid-stream
passthrough, toggle-off passthrough, timeout failover, all-fail surfacing.

Mirrors the inline-stub style of test_secure_provider_router.py — no shared
conftest. Stubs raise/hang on demand to exercise the probe boundary.
"""

from __future__ import annotations

import time
from typing import Iterable

import pytest

from runtime.providers.base import AssistantTurn, ModelCapabilities, ProviderClient, StreamChunk
from runtime.providers.failover import FailoverRouter


class _Stub(ProviderClient):
    """Configurable stub: complete() / stream() raise or yield on demand."""

    def __init__(
        self,
        *,
        complete_error: Exception | None = None,
        stream_chunks: list[StreamChunk] | None = None,
        stream_error: Exception | None = None,
        stream_delay: float = 0.0,
        complete_turn: AssistantTurn | None = None,
    ) -> None:
        self._complete_error = complete_error
        self._stream_chunks = stream_chunks
        self._stream_error = stream_error
        self._stream_delay = stream_delay
        self._complete_turn = complete_turn or AssistantTurn(text="ok")
        self.calls: list[str] = []

    def complete(self, *, model, messages, tools=None, **settings):
        self.calls.append(f"complete:{model}")
        if self._complete_error is not None:
            raise self._complete_error
        return self._complete_turn

    def stream(self, *, model, messages, tools=None, **settings) -> Iterable[StreamChunk]:
        self.calls.append(f"stream:{model}")
        if self._stream_delay:
            time.sleep(self._stream_delay)
        if self._stream_error is not None:
            raise self._stream_error
        for chunk in self._stream_chunks or []:
            yield chunk

    def capabilities(self, model: str) -> ModelCapabilities:
        return ModelCapabilities()


class _MultiStub(ProviderClient):
    """Holds a per-model stub map; used as the FailoverRouter's inner client."""

    def __init__(self, stubs: dict[str, _Stub]) -> None:
        self._stubs = stubs

    def complete(self, *, model, messages, tools=None, **settings):
        return self._stubs[model].complete(
            model=model, messages=messages, tools=tools, **settings
        )

    def stream(self, *, model, messages, tools=None, **settings):
        yield from self._stubs[model].stream(
            model=model, messages=messages, tools=tools, **settings
        )

    def capabilities(self, model: str) -> ModelCapabilities:
        return ModelCapabilities()


class _FakeRouting:
    """Minimal routing service stub returning a fixed failover_chain."""

    def __init__(self, chain: list[str], profile: str = "manual") -> None:
        self._chain = chain
        self._last_profile = profile

    def resolve(self, profile, *, preferred_model, user_input=""):
        return {"failover_chain": list(self._chain)}


# --- complete() path ---


def test_complete_fails_over_to_next_on_retriable_error():
    primary = _Stub(complete_error=RuntimeError("insufficient_quota"))
    fallback = _Stub()
    inner = _MultiStub({"primary": primary, "fallback": fallback})
    router = FailoverRouter(inner, routing=_FakeRouting(["primary", "fallback"]))

    turn = router.complete(model="primary", messages=[])

    assert turn.text == "ok"
    assert primary.calls == ["complete:primary"]
    assert fallback.calls == ["complete:fallback"]


def test_complete_does_not_failover_on_non_retriable():
    primary = _Stub(complete_error=ValueError("genuinely broken"))
    fallback = _Stub()
    inner = _MultiStub({"primary": primary, "fallback": fallback})
    router = FailoverRouter(inner, routing=_FakeRouting(["primary", "fallback"]))

    with pytest.raises(ValueError, match="genuinely broken"):
        router.complete(model="primary", messages=[])
    assert fallback.calls == []


def test_complete_surfaces_last_error_when_all_fail():
    primary = _Stub(complete_error=RuntimeError("insufficient_quota"))
    fallback = _Stub(complete_error=RuntimeError("503 service unavailable"))
    inner = _MultiStub({"primary": primary, "fallback": fallback})
    router = FailoverRouter(inner, routing=_FakeRouting(["primary", "fallback"]))

    with pytest.raises(RuntimeError, match="503"):
        router.complete(model="primary", messages=[])


def test_complete_passthrough_when_failover_disabled():
    primary = _Stub(complete_error=RuntimeError("insufficient_quota"))
    fallback = _Stub()
    inner = _MultiStub({"primary": primary, "fallback": fallback})
    router = FailoverRouter(
        inner, routing=_FakeRouting(["primary", "fallback"]), failover_enabled=lambda: False
    )

    with pytest.raises(RuntimeError, match="insufficient_quota"):
        router.complete(model="primary", messages=[])
    assert fallback.calls == []


# --- stream() path ---


def test_stream_fails_over_pre_first_token():
    primary = _Stub(stream_error=RuntimeError("insufficient_quota"))
    fallback = _Stub(stream_chunks=[StreamChunk(text_delta="hi")])
    inner = _MultiStub({"primary": primary, "fallback": fallback})
    router = FailoverRouter(inner, routing=_FakeRouting(["primary", "fallback"]))

    chunks = list(router.stream(model="primary", messages=[]))

    assert any(c.text_delta == "hi" for c in chunks)
    assert fallback.calls == ["stream:fallback"]


def test_stream_passthrough_after_first_chunk_no_failover_on_mid_stream_error():
    """Once first chunk is yielded, mid-stream errors fall through to the
    engine partial-survives boundary — FailoverRouter must NOT retry."""

    class _MidStreamFail(_Stub):
        def stream(self, **kw):
            self.calls.append(f"stream:{kw['model']}")
            yield StreamChunk(text_delta="first")
            raise RuntimeError("insufficient_quota")  # mid-stream

    primary = _MidStreamFail()
    fallback = _Stub(stream_chunks=[StreamChunk(text_delta="fallback")])
    inner = _MultiStub({"primary": primary, "fallback": fallback})
    router = FailoverRouter(inner, routing=_FakeRouting(["primary", "fallback"]))

    chunks = []
    with pytest.raises(RuntimeError, match="insufficient_quota"):
        for chunk in router.stream(model="primary", messages=[]):
            chunks.append(chunk)

    # First chunk survived; mid-stream error propagated; fallback NOT tried.
    assert any(c.text_delta == "first" for c in chunks)
    assert fallback.calls == []


def test_stream_timeout_triggers_failover():
    """Primary hangs past the probe deadline → failover to next."""
    primary = _Stub(stream_delay=5.0, stream_chunks=[StreamChunk(text_delta="late")])
    fallback = _Stub(stream_chunks=[StreamChunk(text_delta="fast")])
    inner = _MultiStub({"primary": primary, "fallback": fallback})
    router = FailoverRouter(
        inner,
        routing=_FakeRouting(["primary", "fallback"]),
        first_token_timeout=0.5,
    )

    chunks = list(router.stream(model="primary", messages=[]))

    assert any(c.text_delta == "fast" for c in chunks)
    assert fallback.calls == ["stream:fallback"]


def test_stream_all_fail_surfaces_last_error():
    primary = _Stub(stream_error=RuntimeError("insufficient_quota"))
    fallback = _Stub(stream_error=RuntimeError("503"))
    inner = _MultiStub({"primary": primary, "fallback": fallback})
    router = FailoverRouter(inner, routing=_FakeRouting(["primary", "fallback"]))

    with pytest.raises(RuntimeError, match="503"):
        list(router.stream(model="primary", messages=[]))


def test_stream_passthrough_when_disabled():
    primary = _Stub(stream_error=RuntimeError("insufficient_quota"))
    fallback = _Stub(stream_chunks=[StreamChunk(text_delta="hi")])
    inner = _MultiStub({"primary": primary, "fallback": fallback})
    router = FailoverRouter(
        inner, routing=_FakeRouting(["primary", "fallback"]), failover_enabled=lambda: False
    )

    with pytest.raises(RuntimeError, match="insufficient_quota"):
        list(router.stream(model="primary", messages=[]))
    assert fallback.calls == []


def test_stream_single_chain_no_routing():
    """No routing service → single-element chain → no failover, just passthrough."""
    stub = _Stub(stream_chunks=[StreamChunk(text_delta="hi")])
    inner = _MultiStub({"only": stub})
    router = FailoverRouter(inner, routing=None)

    chunks = list(router.stream(model="only", messages=[]))

    assert any(c.text_delta == "hi" for c in chunks)
