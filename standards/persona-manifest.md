# Persona manifest (on-demand)
<!-- spec-version: 1.0.0 -->

Load when authoring or installing a **persona** — a thicker identity prompt than a normal skill. Personas are optional; most work stays on skills + thin `AGENTS.md`.

**persona ⊇ skill:** same YAML-frontmatter + markdown body shape as `SKILL.md`, with extra structured fields.

## Where personas live

| Kind | Place |
|------|--------|
| Coding / domain personas | Portable skill under `~/.agents/skills/<id>/` (or a `PERSONA.md` next to related skills) |
| Hermes / messaging identity | Tool-private `SOUL.md` (see `adapters/SOUL.md.example`) — not in always-on `AGENTS.md` |
| Always-on policy | Never — do not paste a full persona body into `AGENTS.md` |

## Required frontmatter

```yaml
---
id: ops                    # filesystem-safe slug: [a-z0-9][a-z0-9_-]{0,63}
name: Ops Coworker         # human title
---
```

Body after the closing `---` is the system prompt (required, non-empty).

## Optional fields

| Key | Values / shape | Notes |
|-----|----------------|-------|
| `family` | `code` \| `knowledge` | `code` → git-centric workspace; `knowledge` → deliverable-oriented |
| `tools` | list of capability ids | Only ids the host catalogs (e.g. files, search, shell, todo, git) |
| `default_permission_mode` | host-native permission surface | Hint only — name the host's own flag/setting (see `agent-guardrails`); no harness mode enum |
| `skills` | list of skill names | Progressive disclosure — catalog only until loaded |
| `messaging` | bool | May receive/send via messaging connectors when the host supports it |
| `connectors` | bool | May use connected apps when the host supports it |
| `recommends` | list of maps | Suggested connectors/MCP (see below) |
| `recommended_models` | list of strings | Soft hints only — never hard-require a vendor in shared policy |
| `icon` / `tagline` / `description` | strings | UI / picker metadata |

### `recommends` items

Each item is a mapping with either `connector:` or `mcp:`, plus optional `reason` and `tier` (`core` \| `optional`):

```yaml
recommends:
  - connector: github
    reason: inspect PRs and deploys
    tier: core
  - mcp: some-server
    reason: pull metrics
    tier: optional
```

Recommendations are not validated against a shipped connector list — a persona may name something the host does not install yet.

## Rules

- Personas are **on-demand**. Install via harness skills path; invoke when the session needs that identity.
- Risk and approval still follow `~/.agents/standards/agent-guardrails.md` — a persona never silently raises autonomy.
- Fan-out / small workers follow `orchestrating-workers` and thin Orchestration rules in `AGENTS.md`.
- Do not build a second desktop-coworker runtime in this repo; manifests are portable docs for any host that loads them.
