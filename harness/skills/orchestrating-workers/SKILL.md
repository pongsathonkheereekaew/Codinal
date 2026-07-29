---
name: orchestrating-workers
version: 1.0.0
description: Fan-out to small workers, parallel explore-then-report, multi-agent coordination, or สั่งงานตัวเล็ก. Use when tasks are independent, exploration spans many files, or the parent should route while workers return conclusions. Tool-agnostic — works across Cursor, Claude, Codex, Gemini, Hermes, and other hosts.
---

# Orchestrating workers

Universal rules for splitting work across small workers. **Orchestrator ≠ worker.** Parent routes, bounds the task, and merges; workers return conclusions — not dumps. In the shared language, a worker is a **subagent**; vendors may call the same thing a task, agent, child, or delegate.

Do **not** invent a second orchestrator product. Use the host’s native worker API when present; otherwise sequential self-calls with the same brief contract.

## When to fan out

- Independent sub-tasks (no data dependency between them).
- Broad unfamiliar exploration spanning many files (~>3) — workers search and return a report.
- Parallel design alternatives (e.g. several radically different interfaces).

## When not to

- Single known file or path — read it in the parent.
- Strict sequential dependencies — do the chain in one context.
- User asked for one path / one recommendation — do not spawn parallel opinions unless asked.

## Worker brief contract

Every dispatch includes:

1. **Goal** — one outcome sentence.
2. **Constraints** — in/out of scope; files or dirs to touch (or read-only).
3. **Risk ceiling** — max risk class from `agent-guardrails` (`read` / `write_local` / `exec` / `external`). Worker ceiling ≤ parent-allowed consequential class; default workers to `read`.
4. **Done criterion** — what proves finished (path list, measured check, “no matches”).
5. **Return shape** — conclusions, paths, open questions — **no** full-file dumps.

## Portable subagent envelope

Use these neutral fields whenever a host, plugin, or MCP server can exchange
subagent state. This is a semantic contract, not a claim that every host has a
native subagent API.

```json
{
  "protocol": "harness.subagent.v1",
  "id": "host-generated-id",
  "parent_id": "optional-parent-task-id",
  "state": "queued|running|succeeded|failed|cancelled|adopted",
  "goal": "one bounded outcome",
  "ownership": ["paths the subagent may change"],
  "dependencies": ["subagent ids that must finish first"],
  "capabilities": ["task.execute", "task.status", "task.cancel"],
  "result": {"summary": "conclusions only", "artifacts": []}
}
```

- Hosts and plugins map their native fields to this envelope at their adapter
  boundary; do not put vendor-specific names in the shared policy.
- Unknown protocol versions, states, or missing required capabilities fail
  closed. A host without subagents reports that capability as unsupported and
  continues sequentially.
- `ownership` and approvals remain enforced by `agent-guardrails`; the envelope
  never grants write, exec, network, or credential access.

## Risk inheritance

- Worker risk class ≤ parent-allowed consequential class.
- Consequential actions still need human approval when the session is interactive or unattended-with-inbox (see `agent-guardrails`).
- Unattended does **not** raise autonomy — park asks; do not silently approve `exec`.

## Merge

- Synthesize into one answer for the user.
- Cite paths (`path` or `path:line`); keep the reply short.
- Drop duplicate evidence; surface blockers and assumptions once.

## Adapter mapping (host-specific)

Use whichever the current tool provides — same policy, different API:

| Host | Typical mechanism |
|------|-------------------|
| Cursor | Task / subagents |
| Claude Code | Explore / Agent tool; Superpowers fan-out plugins (adapter-only) |
| Codex / Gemini / OpenCode / others | Native parallel tools, or sequential turns with the brief above |
| Hermes | Route to desk agent; do not double-dispatch the same build |

Tool-private plugin names stay in adapters (e.g. `~/.claude/CLAUDE.md`). This skill is the SSOT for *when* and *how* to fan out.
