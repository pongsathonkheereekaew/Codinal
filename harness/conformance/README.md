# Provider conformance policy

`cases.json` is the harness-owned, versioned policy for assigning provider
tiers. `cases.schema.json` validates its declarative shape. Runtime code may
execute these cases but must not silently weaken or replace their expectations.

Tier rules:

- Tier 1: every tool-call-schema and system-prompt-fidelity case passes.
- Tier 2: every tool-call-schema case passes, but prompt fidelity does not.
- Incompatible: tool-call-schema fails.
- Streaming and JSON mode are informational and never promote a tier.

Each run replaces `{nonce}` with a fresh random value. Provider adapters must
normalize responses into `runtime.conformance.ProviderResponse`; tool calls are
then parsed by the same strict `runtime.policy.parse_tool_calls` contract used
by the execution boundary. Reports contain only bounded identities, pass/fail
details, and capability flags—not raw prompts, responses, exceptions, or
credentials.

Phase 1.6 provides the cases, parser, and runner. Live provider adapters and
published model results belong to Phase 2; no provider is Tier 1 merely because
the offline fixture tests pass.
