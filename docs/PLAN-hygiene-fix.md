# Final plan (best): harness hygiene + Fable-lite efficiency

Post-scrutinize. Supersedes the narrower hygiene-only draft where noted.

## Intent (one sentence)

Make Agent Harness **safe to sync** and **cheaper to run** (less always-on noise, soft RTK, clear effort/handoff) without pretending every tool is a Fable runtime.

## Scrutinize report

### Finding — blocker: install silently overwrites live policy
- **Why:** Live edits to `~/.agents/AGENTS.md` are destroyed on `./install.sh`.
- **Evidence:** [`install.sh`](install.sh) lines 11–13: `cp -f "$ROOT/AGENTS.md" "$DEST/AGENTS.md"` with no backup/diff check.
- **Change:** If live ≠ repo → write `AGENTS.md.bak.<ts>`, WARN, then copy (repo stays git SSOT).

### Finding — major: always-on skill table taxes every session
- **Why:** Full job→skill table is loaded into every tool that injects `AGENTS.md`, fighting Fable-like token efficiency.
- **Evidence:** [`AGENTS.md`](AGENTS.md) lines 81–103 (catalog table + domain rows) sit in the always-on file.
- **Change:** Keep 6–8 core rows + “else `ask-matt` / match SKILL.md descriptions”; move domain lists (insurance/GCP/easby) to “load when relevant” one-liners pointing at paths, not a second giant table.

### Finding — major: stale portable template can ship a second policy
- **Why:** Adopters running `templates/agents-harness/` get a diverged AGENTS (~152-line diff vs root).
- **Evidence:** `diff` root vs `templates/agents-harness/AGENTS.md`.
- **Change:** Stub or redirect template install to repo root `./install.sh`.

### Finding — do not treat “effort routing in AGENTS.md” as Fable effort API
- **Why:** Fable `output_config.effort` is adapter/API-specific; AGENTS cannot set it for Cursor/Hermes/Claude uniformly.
- **Evidence:** Effort is not referenced in harness scripts; Hermes uses model aliases in its own config/SOUL.
- **Change:** One universal line only: “match depth to difficulty; adapters pick model/effort.” Real effort knobs stay in Claude/Hermes/Cursor settings.

### Finding — drop Telegram doc purge + command dereference + auto skill cull
- **Why:** Low ROI / high risk / already correct (“No Telegram” is intentional).
- **Evidence:** Prior plan scrutinize; `commands/*.md` symlinks resolve in full clone.

### Simpler alternative (mandatory)

One PR on `harness-flow` from `origin/main`: **footgun + thin AGENTS + soft RTK + doctor nits + template redirect**.  
Do **not** open a “Fable harness rewrite” or multi-repo effort layer.

**Verdict on process:** fix-then-ship this combined plan — biggest reason = install overwrite + always-on catalog cost.

---

## Ship scope (single PR)

Branch from `origin/main` in `harness-flow`.

### A) `install.sh` — backup before AGENTS overwrite
- Diff live vs repo; on difference → `AGENTS.md.bak.<ts>` + WARN → copy.
- Unchanged: rsync skills/standards/commands from repo.

### B) `AGENTS.md` — Fable-lite always-on (same file, not a new system)
1. **Thin catalog:** core router/implement/verify/handoff/worktree/debug/grill only; domain → short “when relevant” pointers.
2. **Soft RTK:** if `rtk` on PATH, prefer for high-stdout shell (git/grep/find/ls/tree/docker); hooks remain Claude-only (keep Out of scope).
3. **Effort line:** match reasoning depth to task hardness; trivial → short path; adapters own model/effort IDs.
4. **Context survive:** before context pressure, prefer `handoff` (and project GOAL/HANDOFF when used); don’t dump huge files; don’t claim done without verification skill.

### C) Template — no second AGENTS body
- `templates/agents-harness/`: stub/README/`install.sh` → root install.

### D) `scripts/harness doctor`
- `rtk` / `lowfat`: OK | MISSING (non-fatal).
- If `~/.hermes/config.yaml` exists: WARN unless `external_dirs` → `~/.agents/skills`.

### E) README
- Edit in **git** → `./install.sh`.
- Edit live `~/.agents` → `./backup.sh` before commit, or next install overwrites (after backup WARN).

### F) Ops (local only)
```bash
cd ~/harness-flow && git fetch origin && git checkout main && git reset --hard origin/main
```

---

## Explicitly out of scope

| Item | Why |
|------|-----|
| Auto skill cull | Irreversible without inventory |
| RTK hooks in universal / Cursor | Different runtimes |
| Fable `effort` API wiring in AGENTS | Not portable across tools |
| AgentMonitor Telegram cleanup | Separate package |
| Dereference `commands/` symlinks | Works in full clone |
| New orchestrator framework | Hermes+cursor-agent already covers the pattern |

---

## Verify

```bash
bash ./verify.sh
# footgun
echo 'LIVE MARKER' >> ~/.agents/AGENTS.md
./install.sh    # must WARN + create AGENTS.md.bak.*
grep -q 'LIVE MARKER' ~/.agents/AGENTS.md.bak.* 
~/.agents/scripts/harness doctor   # rtk + hermes lines
wc -l AGENTS.md   # expect shorter than pre-change (~119 lines) after catalog thin
./install.sh      # sync thinned AGENTS to live
```

## Success criteria

- No silent AGENTS loss on install.
- Always-on policy shorter; domain skills discovery still via `ask-matt` / path pointers / SKILL descriptions.
- Doctor surfaces RTK + Hermes external_dirs.
- Template cannot install a divergent AGENTS.
- No promise that Cursor/Hermes gain Claude Fable native effort — only shared *behavior* tips.
