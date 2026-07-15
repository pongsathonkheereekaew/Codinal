# Review: Telegram + Hermes + Cursor workflow

Impartial root-cause review and **checklist for when back home**.

---

## Architecture (3 loosely coupled systems)

```
[Phone / Telegram]
        │
        ▼
[Hermes gateway on home Mac]   ← requires Mac awake + logged in + process running
        │
        ├──► 9router :20128 (LLM router)
        └──► Cursor Cloud Agents API (coding in cloud VM)
                    │
                    ▼
            [GitHub repo — harness-flow, private]

[Home Mac — Cursor IDE]        ← separate from Cloud Agent
```

**Facts from repo:**
- No hard Hermes ↔ Cursor integration code — only `config.yaml` + `SOUL.md` (soft LLM instructions).
- Cursor bridge plugin/skill is **not bundled** — install separately.
- Repo is **private** — `curl` from raw GitHub does not work for remote apply.

---

## Reported symptoms (3 groups — not the same bug)

| Group | Symptom | Meaning |
|---|---|---|
| **A. Bot silent** | Telegram no reply at all | Gateway / Mac / token / network |
| **B. Duplicate messages** | 2+ bubbles or same answer repeated | Display / streaming / session DB |
| **C. Session won't start** | Stuck on same prompt / agent won't kick off | Cursor bridge + session state (+ B) |

**Current state:** Bot reported **silent (A)** — groups B/C cannot be fixed until A is resolved.

---

## Causes by layer (evidence-based)

### Layer 0: Mac / infrastructure (A)

| Cause | Confidence |
|---|---|
| Mac asleep | High |
| Logged out / stuck at login screen (`gui/$(id -u)` launchd) | High |
| Home internet down | Medium |
| Token revoked (@BotFather) | Medium |
| New config not applied to `~/.hermes/` | High |

### Layer 1: Hermes gateway / Telegram (A + B)

| Cause | Upstream | Confidence |
|---|---|---|
| Gateway process not running | — | High if `pgrep` empty |
| Interrupt race (stale + new reply) | [#8221](https://github.com/NousResearch/hermes-agent/issues/8221), PR [#10235](https://github.com/NousResearch/hermes-agent/pull/10235) | High |
| Streaming + flood control duplicates | [#8375](https://github.com/NousResearch/hermes-agent/issues/8375), [#51828](https://github.com/NousResearch/hermes-agent/issues/51828) | High when `streaming.enabled: true` + `transport: edit` |
| `interim_assistant_messages: true` (Telegram default) | [#43835](https://github.com/NousResearch/hermes-agent/issues/43835) — intentional, looks like duplicates | High |
| Session DB missing assistant rows | [#44100](https://github.com/NousResearch/hermes-agent/issues/44100) | High on some versions |
| Old config: `skill: claude-code` on topics | repo history | High — conflicted with Cursor workflow |

### Layer 2: 9router

| Cause | Symptom |
|---|---|
| 9router down on :20128 | Slow / error replies (usually not full silence if gateway runs) |

### Layer 3: Workflow / SOUL / Cursor bridge (C)

| Cause | Confidence |
|---|---|
| No integration code — SOUL only | High (fact) |
| Cursor plugin not installed | High if never set up |
| LLM may ignore anti-loop SOUL rules | Medium–High |
| No state machine for `cursor_agent_id` | Medium |

### Layer 4: Cursor Cloud Agent

| Fact |
|---|
| Runs on Cursor VM — works even when Hermes is down |
| Mobile → Cloud Agent bypasses Telegram entirely |

---

## What this PR / bundle fixes vs does not fix

| Change | Fixes | Does not fix |
|---|---|---|
| `interim_assistant_messages: false` | B: double bubbles | A: silent bot |
| `streaming.enabled: false` | B: streaming duplicates | Live stream UX |
| SOUL anti-loop rules | C: reduces loops if LLM follows | Hard guarantee |
| `doctor.sh` / `restart-gateway.sh` / `apply-fix.sh` | Diagnose + apply on Mac | Remote apply without Mac access |
| Remove `skill: claude-code` from topics | Wrong tool routing | Missing Cursor plugin |

---

## Checklist — when back home

Run in order on the Mac (Terminal):

```bash
# 0. Pull latest
cd ~/harness-flow && git pull origin main
# (or ~/easby-workflow if that's your clone path)

# 1. Diagnose
bash hermes/doctor.sh

# 2. Restart gateway (if process missing)
bash hermes/restart-gateway.sh

# 3. Apply anti-loop config + SOUL
bash hermes/apply-fix.sh

# 4. Test Telegram — one message → expect one reply bubble

# 5. Optional: upgrade Hermes
# brew upgrade hermes-agent   # or official updater

# 6. Optional: verify 9router
curl -s http://127.0.0.1:20128/dashboard | head

# 7. Optional: Cursor bridge (if not installed)
# - cursor-cloud-agents skill, or
# - https://github.com/fernandoabolafio/cursor-hermes-plugin
# + set Cursor API key in Hermes env
```

### If bot still silent after step 2

- Wake Mac, confirm logged in (not login screen).
- Check token: `hermes pairing approve telegram <CODE>` if prompted.
- Re-install token: `cd harness-flow/hermes && TELEGRAM_BOT_TOKEN=xxx ./install.sh`
- Paste `doctor.sh` output for next debug pass.

### If bot works but messages duplicate

- Confirm `~/.hermes/config.yaml` has `interim_assistant_messages: false` and `streaming.enabled: false`.
- Upgrade Hermes to latest.

### If Cursor session loops

- Confirm Cursor plugin + API key installed.
- Confirm SOUL loaded: `grep -i "anti-loop" ~/.hermes/SOUL.md`

---

## Recommended paths forward (pick one or combine)

| Path | When | Trade-off |
|---|---|---|
| **Fix Hermes on Mac** | Want Telegram bot | Need physical/remote Mac access once |
| **Cursor mobile only** | Coding focus, bot broken | No Telegram bridge |
| **Tailscale + SSH** | Remote fix next time | One-time Mac setup |

---

## Files changed in this effort

| File | Role |
|---|---|
| `hermes/config.yaml` | Anti-duplicate display, streaming off, no forced claude-code |
| `hermes/SOUL.md` | Cursor bridge + anti-loop rules |
| `hermes/apply-fix.sh` | Pull config from local clone → `~/.hermes` + restart |
| `hermes/doctor.sh` | Health check |
| `hermes/restart-gateway.sh` | launchd restart |
| `hermes/README.md` | Troubleshooting |
| `hermes/REVIEW-HOME.md` | This document |

---

## Open questions (need Mac logs)

1. Hermes version on home Mac?
2. Contents of `~/.hermes/logs/launchd.err` when bot was silent?
3. Is `~/.hermes/config.yaml` old or new?
4. Cursor plugin + API key installed?
