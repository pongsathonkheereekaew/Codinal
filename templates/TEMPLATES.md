# Templates in this folder

| Path | Purpose |
|------|---------|
| [`agents-harness/`](agents-harness/) | **Portable Agent Harness starter** (`AGENTS.md` + scripts + adapter examples) |
| [`README.md`](README.md) | Scaffold body for a new Easby plugin README |
| [`verify.sh`](verify.sh) | Plugin-side verify stub used when bootstrapping |
| [`project-wiki/`](project-wiki/) | Per-repo engineering wiki (Karpathy pattern) |

## Agent Harness (for other people / new machines)

```bash
bash templates/agents-harness/install.sh
~/.agents/scripts/harness sync
~/.agents/scripts/harness doctor
```

See [`agents-harness/README.md`](agents-harness/README.md) and [`docs/AGENT_HARNESS.md`](../docs/AGENT_HARNESS.md).

## Project wiki

Install into any git repo:

```bash
bash templates/project-wiki/init-wiki.sh /path/to/your-repo
```

See [`project-wiki/README.md`](project-wiki/README.md). Does not replace claude-mem — `docs/wiki/` is durable engineering docs in that repo.
