"""Auto-failover wrapper around ``ProviderRouter``.

Tries the configured model chain in order. For ``complete`` it retries on any
retriable error. For ``stream`` it retries only **before the first chunk** is
yielded — once the user has seen tokens, mid-stream failures fall through to
the existing engine partial-survives boundary (``engine.py``); tokens already
shown can't be retracted, so failover there would double-charge + confuse.

The first-token probe uses a worker thread + queue so the main thread can
apply the 15s deadline without being blocked by a hung provider generator.
A timed-out worker thread is leaked (Python cannot safely kill a thread that
may hold locks); this is the documented trade-off for hang-resistance.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Iterable, Optional

from .base import AssistantTurn, ModelCapabilities, ProviderClient, StreamChunk
from .errors import friendly_model_error

_LOG = logging.getLogger(__name__)

# How long to wait for the first stream chunk before declaring the primary
# dead and failing over. Tuned to tolerate slow providers (cold start, network
# RTT) while not leaving the user staring at a blank screen.
FIRST_TOKEN_TIMEOUT_SECONDS = 15.0


def _is_retriable(model: str, exc: Exception) -> bool:
    """True if the error is the kind we fail over on (access/quota/5xx/timeout).

    Uses ``friendly_model_error`` for the access/quota classification and
    falls back to common transient markers in the exception text. Returns
    False for unrecognized errors so genuine bugs surface instead of
    silently retrying.
    """
    if isinstance(exc, TimeoutError):
        return True
    if friendly_model_error(model, exc) is not None:
        return True
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "timeout",
            "timed out",
            "connection reset",
            "connection refused",
            "temporarily unavailable",
            "503",
            "504",
            "502",
            "internal server error",
            # OpenAI-compat aggregator gateways (OmniRoute/OpenRouter) can
            # return 200 with empty content when an upstream free-tier flaked.
            # Treat as retriable so we fall over to the next chain entry.
            "returned an empty response",
        )
    )


class FailoverRouter(ProviderClient):
    """Wraps a ``ProviderRouter`` with chain-based auto-failover.

    ``routing`` is a ``ModelRoutingService`` (or duck-typed equivalent) whose
    ``resolve`` returns a ``failover_chain`` list of model ids. ``failover_enabled``
    is read at call time via the ``enabled()`` callable so the toggle can be
    flipped in Settings without rebuilding the router.
    """

    def __init__(
        self,
        inner: ProviderClient,
        *,
        routing: Any,
        failover_enabled: Any = lambda: True,
        first_token_timeout: float = FIRST_TOKEN_TIMEOUT_SECONDS,
    ) -> None:
        self._inner = inner
        self._routing = routing
        self._enabled = failover_enabled
        self._first_token_timeout = float(first_token_timeout)

    # ProviderClient surface — delegate the non-failover bits straight through.
    def capabilities(self, model: str) -> ModelCapabilities:
        return self._inner.capabilities(model)

    def resolve(self, model: str):
        return self._inner.resolve(model)

    def client_for(self, model: str) -> ProviderClient:
        return self._inner.client_for(model)

    def invalidate(self, provider: Optional[str] = None) -> None:
        self._inner.invalidate(provider)

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **settings: Any,
    ) -> AssistantTurn:
        chain = self._chain_for(model)
        last_error: Optional[Exception] = None
        for candidate in chain:
            try:
                return self._inner.complete(
                    model=candidate,
                    messages=messages,
                    tools=tools,
                    **settings,
                )
            except Exception as exc:  # noqa: BLE001 — provider boundary
                last_error = exc
                if not _is_retriable(candidate, exc):
                    raise
                _LOG.warning(
                    "failover: primary %s failed (%s); trying next in chain",
                    candidate,
                    exc,
                )
        # All candidates retriable-failed.
        assert last_error is not None
        raise last_error

    def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **settings: Any,
    ) -> Iterable[StreamChunk]:
        chain = self._chain_for(model)
        last_error: Optional[Exception] = None
        for candidate in chain:
            try:
                first_chunk, gen = self._probe_first_chunk(
                    candidate, messages, tools, settings
                )
            except _ProbeFailed as probe:
                last_error = probe.__cause__ or probe.error or probe
                if not _is_retriable(candidate, last_error):
                    raise last_error
                _LOG.warning(
                    "failover: primary %s failed pre-first-token (%s); trying next",
                    candidate,
                    last_error,
                )
                continue
            # First chunk arrived — pipe the rest of THIS generator straight
            # through. Mid-stream failures fall through to the engine partial-
            # survives boundary. We must NOT re-call self._inner.stream here:
            # that would re-issue the request and double-charge.
            yield first_chunk
            yield from gen
            return
        assert last_error is not None
        raise last_error

    def _chain_for(self, model: str) -> list[str]:
        """Return the failover chain: ``[model, ...fallbacks]``.

        If failover is disabled (toggle off or no routing service), returns
        ``[model]`` — single-element chain means no failover, zero behavior
        change vs the wrapped router.
        """
        try:
            enabled = self._enabled()
        except Exception:  # noqa: BLE001 — defensive
            enabled = True
        if not enabled or self._routing is None:
            return [model]
        resolve = getattr(self._routing, "resolve", None)
        if not callable(resolve):
            return [model]
        try:
            resolution = resolve(
                getattr(self._routing, "_last_profile", "manual"),
                preferred_model=model,
                user_input="",
            )
        except Exception:  # noqa: BLE001 — routing failure shouldn't crash the turn
            return [model]
        chain = resolution.get("failover_chain") if isinstance(resolution, dict) else None
        if not isinstance(chain, list) or not chain:
            return [model]
        # Primary first; de-dup while preserving order. ``model`` is always
        # the head even if it also appears in the routing chain.
        seen: set[str] = {model}
        ordered = [model] + [c for c in chain if c not in seen and not seen.add(c)]
        return ordered

    def _probe_first_chunk(
        self,
        candidate: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]],
        settings: dict[str, Any],
    ) -> tuple[StreamChunk, Iterable[StreamChunk]]:
        """Pull the provider stream generator and return (first chunk, generator).

        The returned generator is the SAME one the first chunk came from, so
        continuing to iterate it yields subsequent chunks without re-issuing
        the request. Raises ``_ProbeFailed`` (wrapping the original error or a
        TimeoutError) if the generator errors or times out before yielding.
        """
        gen = iter(self._inner.stream(
            model=candidate,
            messages=messages,
            tools=tools,
            **settings,
        ))
        q: queue.Queue = queue.Queue(maxsize=1)

        def _worker() -> None:
            try:
                chunk = next(gen)
                q.put(("ok", chunk))
            except StopIteration:
                q.put(("empty", None))
            except BaseException as exc:  # noqa: BLE001 — provider boundary
                q.put(("err", exc))

        t = threading.Thread(
            target=_worker, name=f"failover-probe-{candidate}", daemon=True
        )
        t.start()
        try:
            kind, payload = q.get(timeout=self._first_token_timeout)
        except queue.Empty:
            raise _ProbeFailed(TimeoutError(
                f"{candidate} produced no first chunk within {self._first_token_timeout}s"
            )) from None
        if kind == "ok":
            assert isinstance(payload, StreamChunk)
            return payload, gen
        if kind == "err":
            assert isinstance(payload, BaseException)
            raise _ProbeFailed(payload) from payload
        # Generator yielded nothing (empty stream) — treat as a probe failure
        # so failover kicks in; a provider that returns zero chunks is broken.
        raise _ProbeFailed(RuntimeError(f"{candidate} returned an empty stream"))


class _ProbeFailed(Exception):
    """Internal sentinel: the first-chunk probe failed (error or timeout).

    Carries the underlying error in ``error`` so callers can classify it for
    failover decisions even when ``__cause__`` is None (the timeout case uses
    ``raise ... from None`` to suppress the unrelated worker-thread traceback).
    """

    def __init__(self, error: Exception) -> None:
        super().__init__(str(error))
        self.error = error
