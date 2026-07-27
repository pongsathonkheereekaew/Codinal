# Phase 47 — Provider breadth + auto-failover

**Branch:** `codinal/phase-47-provider-failover`
**Status:** verified locally; PR pending.

## Goal

Two user-requested capabilities (verbatim: "ทั้งคู่ — ให้มีโมเดลที่รองรับเยอะพร้อมทั้งมีโมเดลที่สลับใช้เองอัตโนมัติแบบ cursor composer"):

- **Breadth** — plug any OpenAI-compatible gateway (OmniRoute, OpenRouter,
  OneAPI, local vLLM) as a `custom:<slug>` provider.
- **Auto-failover** — Cursor-style silent switch to the next model when the
  primary fails, before the user sees any output.

Codinal stays the **single routing authority** — OmniRoute is not bundled as
a core dependency; it's just one possible `base_url`.

## Decisions (locked)

1. **Built on merged Phase 45 (#33)** — the base_url schema widening already
   ships on main; 47A generalizes the omniroute opt-in to arbitrary slugs
   rather than re-inventing it.
2. **Custom providers ARE failover-eligible** (lifts the original plan's
   "manual-only" restriction to match the user's "both" ask).
3. **Per-provider opt-in toggle** — a custom provider joins the chain only if
   marked `failover_eligible` at registration.
4. **Fixed 15s first-token timeout** for failover probing.

## What shipped

### 47A — Generic OpenAI-compatible providers

- `runtime/secrets/service.py` — custom-provider registry:
  `set_custom_provider(slug, *, base_url, api_key, failover_eligible)`,
  `delete_custom_provider`, `custom_providers`, `is_failover_eligible`. Slug
  validation (`^[a-z0-9][a-z0-9-]{0,63}$`). Profile schema widened to
  `{api_key, base_url, failover_eligible}` for custom profiles; bootstrap
  loader + `__init__` branch correctly.
- `runtime/providers/router.py` — `_split_model` accepts `custom:slug:model`
  (two-segment prefix); dynamic dispatch via `_custom_provider_known` +
  `_custom_base_url`; `invalidate` accepts custom provider names.
- `runtime/providers/capabilities.py` — `custom:` branch (tools+streaming on,
  vision/PDF off — conservative).
- `runtime/control_plane/app.py` — `GET/POST/DELETE /v1/providers/custom`.
- Rust mirror: `SecretVault` trait gains `get_failover_flag`/`set_failover_flag`/
  `list_custom_slugs`/`set_custom_slug_registered`; macOS vault stores under
  `<provider>:failover` + a `custom-providers-index` registry; 3 Tauri commands
  (`list_custom_providers`, `set_custom_provider`, `delete_custom_provider`);
  `sync_custom_provider` control-client function.
- UI: `renderCustomProviders()` — add/remove custom providers with slug +
  base_url + api_key + failover-eligible checkbox.

### 47B — FailoverRouter (auto-failover)

- `runtime/providers/failover.py` (NEW) — `FailoverRouter(ProviderClient)`
  wraps `ProviderRouter`; reads `failover_chain` from `ModelRoutingService`.
  - `complete()` retries on retriable errors (`friendly_model_error` +
    transient markers).
  - `stream()` probes the first chunk with a 15s deadline (worker thread +
    queue; hung threads are leaked — documented trade-off). Mid-stream
    failures pass through to the existing engine partial-survives boundary.
- `runtime/routing/service.py` — `resolve()` returns `failover_chain`:
  primary + configured native tail (profile order) + eligible custom
  providers appended.
- `runtime/settings/service.py` — `failover_enabled` setting (default True) +
  `set_failover_enabled` setter.
- `runtime/control_plane/server.py` — `build_services` wraps the provider
  client in `FailoverRouter` when `routing` is supplied.
- `runtime/control_plane/app.py` — `PATCH /v1/settings/failover`.
- UI: `renderRoutingResolution` shows the chain ("fallback: X → Y → Z").

## Verification

- `tests/providers/test_failover_router.py` (NEW, 10 tests): complete
  failover on retriable, non-retriable passthrough, all-fail surfaces last
  error, disabled-passthrough, stream pre-first-token failover, mid-stream
  passthrough (no retry), timeout failover, all-fail stream, disabled
  stream, single-chain no-routing.
- `tests/providers/test_secure_provider_router.py` — custom dispatch +
  slug validation.
- `tests/secrets/test_secret_service.py` — custom register/delete/slug/url
  validation.
- Rust tests green (5 PTY + 5 secret_bootstrap).
- Full Python suite: see CI.

## What was NOT changed

- Native tier-1 quality (Claude/Gemini thinking replay, Fable/Mythos refusal
  fallback, conformance gate, keychain) — untouched.
- The engine partial-survives boundary (`engine.py:449-462`) — mid-stream
  failures still fall through there by design.
- OmniRoute is not bundled — it remains one possible `base_url`.

## Non-goals

- Mid-stream failover (tokens already shown can't be retracted).
- Auto-including custom providers in failover (per-provider opt-in).
- OmniRoute-as-core (rejected — see plan doc for full reasoning).
