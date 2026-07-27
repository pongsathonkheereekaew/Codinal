# Codinal provider capability matrix

Status: **pending live run** — populated by `scripts/run_conformance_matrix.py`
once provider API keys are entered via the Codinal Settings UI (Provider
credentials). Until then, cells reflect the conservative runtime capability
registry (`runtime/providers/capabilities.py`), which is the same source the
engine uses to decide tool-call shaping, streaming, and parallel-tool fan-out.

## Supported providers

| Provider | Default model | OpenAI-compatible base URL | Secret profile |
| --- | --- | --- | --- |
| OpenAI | `gpt-5.6-sol` | `https://api.openai.com/v1` | `provider:openai` |
| Anthropic | `claude-sonnet-4-6` | `https://api.anthropic.com` (native) | `provider:anthropic` |
| Google Gemini | `gemini-2.5-flash` | `https://generativelanguage.googleapis.com` (native) | `provider:gemini` |
| Z.ai (GLM) | `glm-4.6` | `https://api.z.ai/api/paas/v4/` | `provider:zai` |
| DeepSeek | `deepseek-chat` | `https://api.deepseek.com` | `provider:deepseek` |
| Ollama (local) | any pulled model | `http://127.0.0.1:11434/v1` | (placeholder key) |

ZAI and DeepSeek are OpenAI-compatible backends and reuse the OpenAI SDK via
`OpenAIProvider(base_url=…, secret_profile=…)`. GitHub Models also reads a
`provider:github` secret (where applicable).

## Conservative capability matrix (runtime defaults)

This is what the engine assumes before a live probe confirms. Run
`scripts/run_conformance_matrix.py` to replace it with live evidence.

| Provider | Streaming | Vision | PDF | Parallel tool calls | Reasoning (`reasoning_content`) |
| --- | --- | --- | --- | --- | --- |
| OpenAI (gpt-5 / gpt-4) | ✅ | ✅ | ❌ | ✅ | ❌ (OpenAI reasoning is separate) |
| OpenAI (o1 / o3 / o4) | ✅ | ❌ | ❌ | ❌ | ✅ |
| Anthropic | ✅ | ✅ | ✅ | ✅ | ❌ |
| Google Gemini | ✅ | ✅ | ✅ | ✅ | ❌ |
| Z.ai GLM | ✅ | ✅ (GLM-4V) | ❌ | ✅ | ✅ (GLM reasoning) |
| DeepSeek | ✅ | ❌ | ❌ | ✅ | ✅ (`reasoning_content`) |
| Ollama | ✅ | ❌ | ❌ | ❌ | model-dependent |

## How to run the live matrix

1. Launch Codinal and open **Settings → Provider credentials**. The ZAI and
   DeepSeek rows appear automatically (the credentials pipeline is data-driven
   off `SUPPORTED_PROVIDERS`). Enter the keys for the providers you want to
   exercise; keys are stored in macOS Keychain and sent only to the local
   runtime.
2. With the runtime running locally:
   ```bash
   ./.venv/bin/python scripts/run_conformance_matrix.py \
       --base-url http://127.0.0.1:43123 \
       --token <your-session-token>
   ```
3. The script overwrites this file with live pass/fail results and exits
   non-zero if any configured provider fails a probe (a regression).
   Providers without a configured key are recorded as `SKIPPED (no key)`.

## Capabilities the live harness exercises

- **`plain_completion`** — a real no-tools turn against each configured
  provider; PASS if it returns assistant text.
- **`streaming`**, **`tool_calling`**, **`parallel_tool_calls`** — recorded
  from the runtime capability registry (the conservative source the engine
  uses) until a richer live probe lands.
