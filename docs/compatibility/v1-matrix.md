# v1 compatibility matrix

This matrix is the R0 compatibility baseline. Rust remains a read-only
consumer until the R1 corpus validates every listed durable store.

| Surface | Current contract | Rust cutover rule |
| --- | --- | --- |
| Local HTTP and WebSocket | `contracts/v1/control-plane.json`; bearer header for HTTP and `codinal.auth.<token>` subprotocol for WebSocket | Preserve paths, status/close codes, ordering, and no-token-in-URL rule. |
| SQLite durable state | `contracts/v1/storage.json`; nine databases and their `PRAGMA user_version`/tables | Read existing versions before becoming writer; migrate forward only with backup/recovery. |
| Keychain provider account | `openai`, `anthropic`, `gemini`, `ollama`, `omniroute`, `custom:<slug>` | Identifiers and account schema are immutable across cutover. |
| Provider identifiers | `openai`, `anthropic`, `gemini`, `ollama`, `omniroute`, `custom:<slug>` | Unknown identifiers fail closed; no identifier translation. |
| Integration manifests | `codinal.integration.v1` declarative manifest | Validate atomically; reject executable hooks, installers, native libraries, and WASM. |
| Audit events | append-only hash chain in `audit.db.events` | Preserve event order and redact before persistence or fixture export. |

Fixture values contain placeholders only. Real bearer tokens, provider keys,
OAuth codes, and user messages are prohibited from `contracts/v1/`.
