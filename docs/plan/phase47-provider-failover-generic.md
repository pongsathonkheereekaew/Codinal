# Phase 47 — Provider breadth + auto-failover (Hybrid architecture)

**Status:** revised 2026-07-28 (built on top of merged Phase 45 / PR #33)
**Branch:** `codinal/phase-47-provider-failover` off `main` (post-#33)

Codinal stays the single routing authority. Two additions, **no OmniRoute
dependency**:

- **47A — Generic OpenAI-compatible providers** (breadth): user plugs any
  OpenAI-compatible gateway (OmniRoute / OpenRouter / OneAPI / local vLLM) as
  a `custom:<slug>` provider via `base_url` + `api_key`. Reuses the Phase 45
  base_url schema widening already on main.
- **47B — `FailoverRouter`** (auto-failover, always-on + toggle): wraps
  `ProviderRouter`, retries the next model in the chain when the primary fails
  **before the first stream chunk** (15s timeout). Custom providers participate
  in failover via a per-provider opt-in toggle.

Native tier-1 quality (Claude/Gemini thinking replay, Fable/Mythos refusal
fallback, conformance gate, keychain) **untouched**.

---

## Decisions (locked, revised from original plan)

1. **Built on merged #33** — the base_url schema widening
   (`{api_key, base_url?}`, `_PROVIDERS_WITH_BASE_URL`, Rust
   `get_base_url`/`set_base_url`) already ships on main. 47A generalizes the
   `omniroute` opt-in to arbitrary `custom:<slug>` providers; it does NOT
   re-invent the schema.
2. **Custom providers ARE failover-eligible** (user's verbatim "both" ask).
   Original plan's "manual-only" restriction is lifted.
3. **Per-provider opt-in toggle** — a custom provider joins the failover chain
   only if the user marks it failover-eligible at registration time. Default
   off (matches base_url's opt-in philosophy; flaky gateways shouldn't silently
   enter the chain).
4. **Fixed 15s first-token timeout** for failover probing. If the primary
   yields no chunk within 15s, FailoverRouter cancels it and tries the next.
   Mid-stream failures (after first chunk) hit the existing partial-survives
   path — tokens already shown can't be retracted.

---

## 47A — Generic OpenAI-compatible providers

The Phase 45 omniroute integration is the template. omniroute is now just one
specific `custom:` provider that we ship pre-registered; the new work makes
the mechanism generic.

### `runtime/secrets/service.py`
1. **Generalize `_PROVIDERS_WITH_BASE_URL`** (currently `frozenset({"omniroute"})`)
   → drop the fixed set; ANY profile may carry `base_url` if it's a custom
   provider. Keep `omniroute` as a pre-registered custom provider for
   backward-compat with existing Phase 45 setups.
2. **New custom-provider registry** alongside `SUPPORTED_PROVIDERS`:
   - `custom_providers() -> list[dict]` — returns `[{slug, base_url, failover_eligible}, ...]`.
   - `set_custom_provider(slug, *, base_url, api_key, failover_eligible=False)`
     storing under `provider:custom:<slug>` with `{api_key, base_url, failover_eligible}`.
     Slug validation: ascii, `^[a-z0-9][a-z0-9-]{0,63}$`, no leading/trailing `-`.
   - `delete_custom_provider(slug)`.
   - `is_failover_eligible(provider) -> bool` — used by the routing service
     when building the chain.
3. **`status()`** (L83-92) — include registered custom providers in the catalog
   so the UI shows them.

### `runtime/providers/router.py`
4. **Generalize `_OPENAI_COMPATIBLE`** (L20-23) → dynamic view. Add
   `_openai_compatible(self) -> dict[str, tuple[str,str]]` merging static
   `zai`/`deepseek` (still hardcoded — known good endpoints) with dynamic
   custom providers from `self._secrets.custom_providers()`. Custom ids:
   `custom:<slug>`.
5. **`_client()`** (L108-120) — the omniroute elif branch (currently special-
   cased) becomes a general `custom:<slug>` branch reading base_url from
   secrets. omniroute dispatches through this same path.
6. **`_split_model()`** (L124-142) — allow `custom:<slug>:<model>` (note: two
   colons — provider slug + model). Validate slug registered. Keep loopback-
   only Ollama branch.
7. `invalidate(provider)` (L53-60) — already clears the client cache on
   secret change; custom-provider add/delete calls `_notify` which fires this.

### `runtime/providers/capabilities.py`
8. `custom:` prefix branch: `tools=True, streaming=True, vision=False,
   pdf=False, parallel_tool_calls=False`. Conservative — gates UI hints +
   degradation notices only.

### `runtime/control_plane/app.py`
9. New endpoints:
   - `POST /v1/providers/custom` — body `{slug, base_url, api_key,
     failover_eligible?}` → `set_custom_provider`.
   - `DELETE /v1/providers/custom/{slug}` → `delete_custom_provider`.
   - `GET /v1/providers/custom` → `custom_providers()` (for UI listing).
   The existing `PUT /v1/secrets/providers/{provider}` (L1329) already
   handles `base_url` for known providers (Phase 45) — leave it.

### Rust mirror
10. `desktop/src-tauri/src/secrets.rs` — leave native `SUPPORTED_PROVIDERS`
    (6-tuple). New Tauri commands `set_custom_provider`, `delete_custom_provider`,
    `list_custom_providers` mirroring `set_provider_secret` (lib.rs:92). Custom
    provider keychain entries use account `custom:<slug>` + `custom:<slug>:base_url`
    (Phase 45 pattern) + new `custom:<slug>:failover` flag.

---

## 47B — `FailoverRouter` (auto-failover, always-on + toggle)

### New `runtime/providers/failover.py`
`FailoverRouter(ProviderClient)` wraps a `ProviderRouter` + reads chain from
`ModelRoutingService`.

- **`complete()`** — try chain in order; on retriable error
  (`friendly_model_error` from `runtime/providers/errors.py` —
  access/quota/5xx/timeout) → next; surface last error if all fail.
- **`stream()`** — first-token probing with 15s timeout (the load-bearing
  part):
  1. Start the primary's stream generator.
  2. `next()` with a 15s deadline (thread-based timeout — generators can't be
     interrupted, so run `next()` in a worker thread + join with timeout; on
     timeout, abandon the primary — its partial state is discarded since no
     chunk reached the user).
  3. If first chunk arrives within 15s → yield it, then pipe the rest of the
     generator straight through. Mid-stream failures fall through to the
     existing `engine.py:449-462` partial-survives boundary (cannot fail over
     after tokens reached user).
  4. If primary errors OR times out before first chunk → log, cancel, try
     next chain entry. Repeat up to chain length.
  5. All fail → surface the last error.
- **Chain source**: `ModelRoutingService.resolve(...).get("failover_chain")`
  (new field, see item 11). Primary first.

### `runtime/routing/service.py`
11. **Extend `resolve()` return** (L141-150) with `"failover_chain": [...]`:
    - For `quality`/`balanced`/`economy`: the existing `_PROFILE_ORDER[profile]`
      tuple filtered to configured providers, PLUS any custom providers marked
      `failover_eligible` (appended at the end, after the 3 native models).
    - For `manual`: `[preferred_model]` + the same fallback tail (configured
      native order + eligible custom). User's manual selection stays primary.
    - Each entry is a full model id like `custom:my-openrouter:gpt-4o` or
      `anthropic:claude-sonnet-4-6`.

### Settings toggle
12. New setting `failover_enabled: bool` (default `True`). `FailoverRouter`
    reads it; off → delegates straight to wrapped router (zero behavior
    change). Surfaced via `GET/PATCH /v1/settings` (app.py L822/L832).

### Wiring
13. `runtime/control_plane/server.py:120` + `runtime/composition.py:123-126`:
    wrap `provider_client = ProviderRouter(...)` in
    `FailoverRouter(provider_client, routing, secrets)` before it reaches
    `TurnEngine`. Engine code unchanged — failover transparent at the
    `ProviderClient` boundary.

---

## UI (`desktop/ui/`)

14. **`startup.js renderProviders()`** (L4433-4493): add "Custom OpenAI-
    compatible provider" section — `slug` + `base_url` + `api_key` +
    `failover eligible` checkbox → new Tauri commands. Lists registered
    custom providers + Remove.
15. **`renderRoutingResolution()`** (L382-399): render `failover_chain`
    ("primary X → fallback Y → Z") + failover toggle. Placeholder at L399
    already says "fallback appear here" — now real.
16. Custom models auto-appear in catalog (via `status()` extension).

---

## Tests (mirror existing stubs — no new conftest)

17. `tests/providers/test_failover_router.py` (NEW): `FixtureProvider`-style
    stubs that raise/hang on demand; assert (a) primary fails pre-first-token
    → next chain model used; (b) primary yields first chunk then errors
    mid-stream → existing partial-survives path runs (no failover); (c) toggle
    off → no failover (passthrough); (d) primary hangs past 15s → timeout
    triggers failover; (e) all fail → last error surfaced. Mirror
    `test_secure_provider_router.py:90-120`.
18. `tests/providers/test_secure_provider_router.py`: add parametrize row for
    `custom:` provider + `_split_model` validation tests for `custom:slug:model`
    ids.
19. `tests/routing/test_service.py`: assert `failover_chain` in `resolve()` for
    each profile incl. `manual`; assert eligible custom providers appended.
20. `tests/secrets/`: custom provider register/forget round-trip +
    `failover_eligible` flag persistence.
21. Conformance: custom providers reachable via `ProviderConformanceAdapter`
    unchanged — add row to `scripts/run_conformance_matrix.py`.

---

## Docs

22. `docs/conformance/capability-matrix.md`: add "Custom OpenAI-compatible"
    row + note failover-eligible semantics.
23. `docs/evidence/phase47-provider-failover-generic.md`.

---

## Verification (done criteria)

- `./.venv/bin/python -X faulthandler -m pytest -q --timeout=90
  --timeout-method=thread -p no:cacheprovider` passes (full `tests/`).
- `bash verify.sh` green.
- `test_failover_router.py` proves all 5 cases (a–e above).
- Manual smoke: register a custom provider pointing at a flaky endpoint;
  appears in catalog, selectable, fails over to native model on hang/error.

## Non-goals

- **Not** bundling OmniRoute/Node — it's just one possible `base_url`.
- **Not** mid-stream failover (tokens already shown can't be retracted).
- **Not** auto-including custom providers in failover (per-provider opt-in).
- No changes to native provider clients (thinking/conformance untouched).
