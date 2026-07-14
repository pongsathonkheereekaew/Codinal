# Final plan (best): harness hygiene + Fable-thin always-on

Post-scrutinize. Supersedes the hygiene-only draft where they conflict.

## Intent (one sentence)

Keep one safe Agent Harness SSOT, cut always-on token waste, and preserve quality/context-survival — without pretending every tool shares one runtime.

## Scrutinize report

### 1) Intent / simpler alternative

- **Hygiene-only** fixes footguns but does **not** improve Fable-like token/thinking.
- **Fable-full** (effort APIs, native long-lived subagents, model-specific thinking config) does **not** belong in `AGENTS.md` — most tools ignore it; bloats the lingua franca.
- **Best smaller plan:** ship **P0 install safety** + **thin AGENTS always-on** (catalog progressive disclosure) + **soft RTK + depth/handoff one-liners** + **doctor probes**. Defer skill cull and AgentMonitor Telegram archaeology.

### 2) Trace (what actually runs today)

```text
Agent start
  → load ~/.agents/AGENTS.md (full file, incl. skill table ~L81–103)
  → tool adapter (CLAUDE.md / SOUL / .mdc)
  → maybe skill on match
  → tools / shell
       Claude Bash only: lowfat-rtk-router.sh → rtk|lowfat
       Others: raw shell unless prompt remembers rtk
install.sh
  → cp -f AGENTS.md          # silent overwrite (L11–13)
  → rsync skills/standards/commands
  → harness sync / rules
```

Surprise: skill **files** are progressive; skill **index table inside AGENTS.md** is not — paid every turn.

### 3) Verify claims

| Claim | Holds? | Evidence |
|-------|--------|----------|
| Soft RTK in AGENTS helps all tools | Partial | Binary on PATH yes (`rtk 0.38.0`); auto-hook only Claude |
| Thin catalog saves tokens without losing functions | Holds if router remains | Keep `ask-matt` + ~8 core rows; rest discoverable via skill dirs / ask-matt |
| Effort ladder in AGENTS = Fable-best | Weak | No universal `output_config.effort`; put “match depth to task” wording only |
| install backup+WARN prevents data loss | Holds | Today unconditional `cp -f` in `install.sh` |
| Telegram purge in harness-flow | N/A | Mentions already “No Telegram” |

### 4) Findings (ordered)

**Blocker — install overwrites live AGENTS**  
- **Finding:** `install.sh` L11–13 `cp -f` with no diff/backup.  
- **Why:** Live edits disappear next install.  
- **Change:** If live ≠ repo → `AGENTS.md.bak.<ts>` + WARN, then copy.

**Major — always-on skill table tax**  
- **Finding:** `AGENTS.md` L81–103 embeds a wide catalog every session.  
- **Why:** Burns tokens without loading skill bodies; fights Fable progressive disclosure.  
- **Change:** Keep short core table (ask-matt, grilling, implement/tdd, diagnosing-bugs, verification-before-completion, handoff, wayfinder); one line “else open `ask-matt` / match `~/.agents/skills/*/SKILL.md` description”. Optional: `docs/SKILL-MAP.md` in repo for humans, not always-on.

**Major — stale portable template**  
- **Finding:** `templates/agents-harness/AGENTS.md` ≠ root (~152-line diff).  
- **Why:** Second policy for adopters.  
- **Change:** Stub or delegate to root `install.sh`.

**Major — doctor blind to RTK/Hermes bridge**  
- **Finding:** `harness doctor` does not mention `rtk` or `external_dirs`.  
- **Why:** New machine “looks green” while Hermes misses skills / no rtk.  
- **Change:** Non-fatal OK/MISSING/WARN lines.

**Nit — local git main drift**  
- **Finding:** local `main` at checkpoint vs `origin/main` @ PR #8.  
- **Change:** ops `reset --hard origin/main` when confirmed — not product code.

**Reject this round:** auto skill cull; RTK hooks in SSOT; dereference `commands/` symlinks; Fable API knobs in AGENTS; Telegram doc purge on harness-flow.

---

## Final plan — do this

Branch from `origin/main` on `harness-flow`.

### A. Safety (P0)

1. **`install.sh`** — backup+WARN when live `AGENTS.md` differs; then repo wins.  
2. **`templates/agents-harness`** — no divergent AGENTS body; call/document root install.  
3. **README** — git edit → `./install.sh`; live edit → `./backup.sh` or lose on next install.

### B. Fable-thin always-on (P0/P1, same PR)

4. **Slim `AGENTS.md` Skills section** — core router table only; point rest to `ask-matt`.  
5. **Context hygiene add:**  
   - Soft RTK: if on PATH, prefer for fat stdout commands.  
   - Depth: trivial → short path; hard/ambiguous → plan or heavier model in *adapter*; don’t narrate hidden chain-of-thought.  
   - Context survival: long work → `handoff` / GOAL before rotating session; don’t dump huge files.  
6. Keep Out of scope: Claude hooks, mem, RTK **hooks**, Hermes runtime details.

### C. Observability (P1)

7. **`scripts/harness doctor`** — `rtk`/`lowfat` PATH; Hermes `external_dirs` → `~/.agents/skills` if config exists.  
8. **`./install.sh`** still copies scripts → `~/.agents/scripts`.

### D. Ops (no commit)

9. Sync local main to `origin/main` after shipping.

## Out of scope

- Skill pack cull without human inventory  
- Universal RTK/Claude-mem/AgentMonitor runtime  
- Full Fable `effort` API wiring in lingua franca  
- Large agentmonitor Telegram cleanup  

## Verify

```bash
bash ./verify.sh
# footgun
echo 'marker' >> ~/.agents/AGENTS.md && ./install.sh   # expect .bak + WARN
# thin policy
wc -l AGENTS.md    # Skills section clearly shorter; ask-matt still listed
./install.sh && ~/.agents/scripts/harness doctor   # rtk + hermes lines
# regressions
test -d ~/.agents/skills/ask-matt
test -d ~/.agents/skills/verification-before-completion
```

## Verdict

**fix-then-ship** this combined plan — best ROI is **install safety + thinner always-on**; that is the Fable-aligned move available inside a universal file without lying about multi-runtime support.
