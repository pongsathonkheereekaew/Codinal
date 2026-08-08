# Contributing to CEDIA

## Dev setup

1. Clone `CEDIA` (harness SSOT) and `CEDIA-IDE` (Code-OSS fork).
2. Node 24 (`export PATH="$HOME/.local/node24/bin:$PATH"` on this machine).
3. CEDIA IDE: `cd ~/cedia-ide && bash scripts/cedia-dev.sh ~/CEDIA`.

## Gates

Every change must keep both gates green:

```bash
bash ~/CEDIA/verify.sh
bash ~/cedia-ide/verify.sh
```

Optional perf lane:

```bash
CEDIA_PERF=1 bash ~/cedia-ide/verify.sh
```

## Workflow

1. Read `harness/AGENTS.md` and the relevant plan under `docs/plan/`.
2. Make the smallest correct change in `extensions/cedia-agent` (IDE) or the
   harness SSOT.
3. Add a named gate artifact under `docs/evidence/` when the change claims a
   capability.
4. Self-host: run `scripts/self-host-gate.sh` for at least one repo change.
