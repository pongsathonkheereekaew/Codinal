# Phase 42 evidence — ZAI + DeepSeek providers + conformance harness

Date: 2026-07-27
Roadmap item: "Run live conformance against at least three cloud models and publish the exact supported capability matrix." (`docs/plan/codinal-parity-roadmap.md:84`)

## Summary

Registered **ZAI (Z.ai GLM)** and **DeepSeek** as first-class cloud providers, bringing the supported set to **five cloud backends** (OpenAI, Anthropic, Gemini, ZAI, DeepSeek) plus Ollama. Both are OpenAI-compatible, so they reuse `OpenAIProvider` with their own `base_url` and a per-provider secret profile — no new SDK plumbing, no HTML/JS/Rust changes (the credentials pipeline is data-driven off `SUPPORTED_PROVIDERS`).

Shipped the published capability matrix (`docs/conformance/capability-matrix.md`) and a live conformance harness (`scripts/run_conformance_matrix.py`) ready to run once provider keys are entered via Settings.

## What shipped

**1. Generalized OpenAI-compatible credential resolution** (`runtime/providers/openai_provider.py`)
- `resolve_api_key(secrets, profile="openai")` — now reads any `provider:<name>` entry.
- `OpenAIProvider.__init__(…, secret_profile="openai")` — selects which secret store entry supplies the key. `_ensure_client` passes it through.
- DeepSeek/GLM `reasoning_content` thinking text was already handled (L50-55).

**2. Registered the two backends** (`runtime/providers/router.py`)
- `_CLOUD_PROVIDERS` now includes `zai`, `deepseek`.
- New `_OPENAI_COMPATIBLE` map: `zai → ("https://api.z.ai/api/paas/v4/", "zai")`, `deepseek → ("https://api.deepseek.com", "deepseek")` (base URLs confirmed from official docs).
- `_client` dispatch builds `OpenAIProvider(base_url=…, secret_profile=…, secrets=…)` for each. Ollama's placeholder-key path is unchanged.

**3. Lit up Settings credentials UI** (`runtime/secrets/service.py`)
- `SUPPORTED_PROVIDERS` extended with `zai`, `deepseek`. Single change: the Settings "Provider credentials" rows render automatically (data-driven via `status()`), and PUT/DELETE now accept the new names. Keys are stored in macOS Keychain via the Rust bridge; the Python runtime sees them only in memory.

**4. Conservative capabilities** (`runtime/providers/capabilities.py`)
- `zai` → streaming + vision (GLM-4V multimodal).
- `deepseek` → streaming (reasoning surfaced as thinking text).

**5. Published capability matrix** (`docs/conformance/capability-matrix.md`)
- Per-provider × per-capability (streaming / vision / PDF / parallel-tool / reasoning) grid reflecting the runtime registry, plus run instructions.

**6. Live conformance harness** (`scripts/run_conformance_matrix.py`)
- Probes each configured provider (a real no-tools turn) + records runtime-registry advertisements for streaming/tool-calling/parallel-tool. Emits markdown; exits non-zero on regression; `SKIPPED (no key)` for un-configured providers. Not run in CI (needs real keys).

## What was NOT changed (and why)

- **No HTML/JS/Rust changes.** The credentials pipeline is fully data-driven off `SUPPORTED_PROVIDERS` + `secrets.status()`, so adding the names automatically lights up the Settings rows and the desktop bridge forwards whatever the UI sends.
- **No new SDK dependency.** Both backends speak the OpenAI Chat Completions wire format; the existing `openai` SDK covers them.

## Verification

```
$ ./.venv/bin/pytest -q tests/providers tests/secrets
.........................................................                [100%]
57 passed in 0.39s    # +3 new (parametrized ZAI/DeepSeek base_url + profile test)
```

```
$ ./.venv/bin/python scripts/run_conformance_matrix.py --help   # harness OK
$ ./.venv/bin/python -c "import ast; ast.parse(open('scripts/run_conformance_matrix.py').read())"  # syntax OK
```

```
$ CI= ./.venv/bin/pytest -q
865 passed, 1 skipped   # full suite unchanged (new tests counted; macOS-gated E2Es unaffected)
```

```
$ CI= ./verify.sh
Codinal verify: PASS
```

## Live conformance run — pending keys

The harness is ready to run. The moment provider keys are entered via Settings (you indicated you'll do this yourself):

```
./.venv/bin/python scripts/run_conformance_matrix.py \
    --base-url http://127.0.0.1:43123 \
    --token <session-token>
```

This overwrites `docs/conformance/capability-matrix.md` with live PASS/FAIL per capability and exits non-zero if any configured provider fails a probe it advertises.
