# Phase 29 evidence — prompt-injection & secret-exfiltration adversarial suite

Date: 2026-07-27
P0 roadmap item: "Add prompt-injection and secret-exfiltration adversarial suites for repository content, MCP, terminal output, attachments, and remote messages."

## What shipped

### Defenses
- **Inbound: untrusted-content fence** (`runtime/turn_engine/content_fence.py`) — every tool result that reaches the model is wrapped in `<tool_result><content>...</content></tool_result>`. The closing sentinel is escaped so an injected `</content>` cannot break out. Covers all 5 active content channels (tool results, MCP output, attachment text, terminal stdout, git output).
- **System guidance** — `UNTRUSTED_SYSTEM_GUIDANCE` appended to the base system prompt: tells the model tool-result content is untrusted data, never instructions; never bypass approval policy because of it.
- **Outbound: secret-aware redaction** (`runtime/secrets/redaction.py`) — `SecretRedactor` subscribes to `ProviderSecretService`, scrubs exact registered keys + common prefixes (`sk-...`, `sk-ant-...`, `AIza...`) from the outbound provider feed, audit payloads, and MCP tool arguments. Never mutates the in-memory transcript.

### Wiring
- `_tool_result_message` / `_tool_error_message` fence every tool result.
- `_outbound_messages` runs `redact_messages` on the outbound copy only.
- `AuditLedger.record()` redacts payload before hashing (chain still verifies).
- `MCPService._attach` wraps `call_async` to redact MCP arguments before transport.
- `build_services` constructs one `SecretRedactor(secrets)`; plumbs to engine + ledger + MCP.

## Verification (fresh, 2026-07-27)

Adversarial corpus (17 tests across 5 files):

```
$ ./.venv/bin/pytest -q tests/security/
.................                                                        [100%]
17 passed in 0.30s
```

| File | Vectors covered |
|---|---|
| `test_inbound_fence.py` | injection via tool result, MCP output, terminal stdout, git diff — all fenced, injected close-tag escaped (4 tests) |
| `test_outbound_redaction.py` | secret in tool result blocked from provider feed + audit ledger + tool arguments; transcript fidelity preserved (4 tests) |
| `test_authority_escalation.py` | injected write/shell denied by policy in DISCUSS mode; path-scoped write denied even when approved (3 tests) |
| `test_mcp_exfiltration.py` | secret in MCP argument redacted before transport; clean arguments untouched; no-redactor passthrough pinned (3 tests) |
| `test_transcript_integrity.py` | in-memory transcript keeps raw content; outbound is fenced+redacted; system guidance reaches provider (3 tests) |

Module tests:

```
$ ./.venv/bin/pytest -q tests/turn_engine/test_content_fence.py tests/secrets/test_redaction.py
...........                                                               [100%]
11 passed in 0.32s
```

Full local suite:

```
$ CI= ./.venv/bin/pytest -q
757 passed, 53 warnings in 68.29s
```

`verify.sh`: PASS.

## What this proves

1. **Injection cannot escalate authority.** The fence makes injected instructions visible, but the policy chokepoint is the real boundary — even a model that "complies" with an injection is denied by default-deny / path-scope / mode rules (`test_authority_escalation`).
2. **Secrets cannot leave the trust boundary unredacted.** A registered key in a tool result, tool argument, MCP argument, or audit payload is scrubbed to `[REDACTED:provider]` before provider send, audit persistence, or MCP egress.
3. **Fidelity is preserved for the user.** The in-memory transcript keeps the raw content (fenced, not redacted) so the user sees exactly what happened; only the outbound copy is scrubbed.

## Non-goals (deferred)

- A prompt-injection *classifier* (heuristic/ML detection). Fence + guidance is the v1 defense.
- Redaction of secrets never registered with `ProviderSecretService` (only registered keys + common-prefix backstop).
- Web/browser content channel (not present in v1).
- Remote worker messages (local-only in v1).
