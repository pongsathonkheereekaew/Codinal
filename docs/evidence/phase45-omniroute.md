# Phase 45 — Native OmniRoute provider

**Branch:** `codinal/phase-45-omniroute`
**Status:** verified locally; PR pending.

## Goal

Add [OmniRoute](https://github.com/diegosouzapw/OmniRoute) as a native,
first-class provider in Codinal — an open-source OpenAI-compatible
self-hosted gateway that routes across 290+ upstream LLM providers with
19 strategies (including a zero-config `auto` router).

The challenge vs prior OpenAI-compat providers (ZAI, DeepSeek) is that
OmniRoute's base URL is **user-configurable** (self-hosted, default
`http://localhost:20128/v1`) rather than a hardcoded vendor endpoint.

## Approach

Widened the secret profile schema from `{api_key}` to `{api_key, base_url?}`.
`base_url` is optional and only accepted by opt-in providers
(`_PROVIDERS_WITH_BASE_URL = {"omniroute"}`); all other providers reject it
so the wire format stays tight. The same slot future-proofs vLLM / LM Studio
backends.

## Changes

### Python runtime

- `runtime/secrets/service.py` —
  - `SUPPORTED_PROVIDERS` += `"omniroute"`.
  - `set_api_key(provider, api_key, *, base_url=None)` — validates and stores
    the optional base_url (ASCII, ≤512B, http(s) URL).
  - `_validate_base_url` static helper (mirrors router's ollama URL check).
  - `get_base_url(provider)` helper for the router.
  - Profile schema accepted in `__init__` and `load_secret_bootstrap` widened
    to `{api_key}` or `{api_key, base_url}`.
- `runtime/providers/router.py` —
  - `_CLOUD_PROVIDERS` += `"omniroute"`.
  - New omniroute elif branch in `_client`: builds
    `OpenAIProvider(base_url=self._omniroute_base_url(), secret_profile="omniroute", secrets=…)`.
  - `_omniroute_base_url()` reads `secrets.get_base_url("omniroute")`,
    falling back to `http://localhost:20128/v1`.
- `runtime/providers/capabilities.py` — `omniroute` branch
  (`streaming=True`; vision/PDF/reasoning are model-dependent through the
  gateway).
- `runtime/control_plane/app.py` — `_read_api_key` now returns
  `(api_key, base_url)`; PUT handler passes `base_url=` through.

### Rust desktop bridge

- `desktop/src-tauri/src/secrets.rs` —
  - `SUPPORTED_PROVIDERS` += `"omniroute"` (now 7 entries).
  - `ProviderSecret` struct += `base_url: Option<String>`
    (`#[serde(skip_serializing_if)]`).
  - `SecretVault` trait += `get_base_url`/`set_base_url` with default
    no-op impls (existing/test vaults compile unchanged).
  - macOS `PlatformSecretVault` overrides them, storing the URL under a
    separate keychain account `<provider>:base_url`.
  - `update_provider_secret` accepts `base_url: Option<&str>`, validates
    (http(s), ≤512B, opt-in provider only), persists, and rolls back on
    sync failure.
  - `encode_secret_bootstrap` carries `base_url` for opt-in providers.
- `desktop/src-tauri/src/control_client.rs` — `sync_provider_secret`
  accepts `base_url: Option<&str>` and includes it in the PUT payload when
  non-empty.
- `desktop/src-tauri/src/lib.rs` — `set_provider_secret` Tauri command
  accepts `base_url: Option<String>`; `delete_provider_secret` passes
  `None`.

### Native Settings UI

- `desktop/ui/startup.js` `renderProviders()` — when
  `provider.provider === "omniroute"`, renders an extra `<input type="text">`
  for the base URL (placeholder `http://localhost:20128/v1`); the save
  handler posts `{provider, apiKey, baseUrl}`.

### Tests

- `tests/providers/test_secure_provider_router.py` — omniroute added to the
  supported-clients test; 2 new tests (configured base_url from secrets;
  fallback to default when unset).
- `tests/secrets/test_secret_service.py` — omniroute added to `status()`
  expected list; 5 new tests (base_url round-trip, None when unset, invalid
  URL rejection ×4, non-opt-in provider rejection, bootstrap round-trip).
- `tests/control_plane/test_auth.py` + `test_server.py` — omniroute added
  to all hardcoded provider status lists.
- `desktop/src-tauri/tests/secret_bootstrap.rs` — expected status JSON
  extended to 7 entries; 2 new tests (omniroute base_url bootstrap
  round-trip; non-opt-in provider rejects base_url).

### Docs

- `docs/conformance/capability-matrix.md` — OmniRoute row in both the
  providers table and the conservative capability matrix.
- `docs/plan/codinal-parity-roadmap.md` — Phase 45 entry in the L84
  conformance checklist.
- `docs/evidence/phase45-omniroute.md` — this file.

## Verification

```
./.venv/bin/pytest -q tests/providers tests/secrets tests/desktop_ui \
    tests/control_plane/test_auth.py tests/control_plane/test_server.py
# → 122 passed

cd desktop/src-tauri && cargo test --test secret_bootstrap
# → 5 passed

./verify.sh
# → Codinal verify: PASS
```

## Usage

1. Launch Codinal → Settings → Provider credentials. The OmniRoute row now
   appears with **two** fields: API key + base URL.
2. Enter the OmniRoute bearer token and (optionally) adjust the base URL if
   the gateway runs on a non-default host/port. Defaults to
   `http://localhost:20128/v1`.
3. Use `omniroute:<model>` in the model picker, or `omniroute:auto` for the
   zero-config router.

## Out of scope

- OmniRoute's MCP (`/api/mcp/stream`, `/api/mcp/sse`) and A2A
  (`/.well-known/agent.json`) endpoints — we use only the OpenAI-compat
  `/v1/chat/completions` path.
- Tokenized URL-path auth alias (`/vscode/<key>/…`) — we use the Bearer
  header.
- Per-routing-strategy selection in the UI — OmniRoute's `model` field is
  passed through verbatim, so `omniroute:auto` and any explicit strategy
  already work without extra UI.
