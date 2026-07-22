---
name: desk-domains
description: >
  Route desk work across ของ (product/Easby DSP/music) and คน (insurance clients,
  sales decks, leadership rewrites). Use when the user mentions ของ, คน, Easby,
  plugin/DSP/mix/master/decomp, Tokio Marine, commission, premium, nuiny, sales
  deck, or exec/management status rewrite — and the Matt build flow is not the
  primary need.
---

# Desk domains — ของ + คน

Thin router for **this desk's** domains. Process/build flow stays with `ask-matt`.

Pick **one** lane. If ของ and คน both apply, finish the blocker lane first or ask one question.

## ของ — product / craft

Audio plugins, DSP, RE, music production pipeline.

| Trigger | Skill |
|---------|--------|
| Bare "easby" / unclear stage | `easby` (reads suite INDEX) |
| Sound design / variation / theory | `easby-producer` |
| Track/bus mix balance | `easby-mixing` |
| LUFS / master / true-peak | `easby-mastering` |
| Decompile / RE / measure plugin | `easby-decomp` |
| Implement/clone DSP (CLEAN only) | `easby-programming` |

Standards when coding plugins: `easby-dsp`, `easby-ui`. Never weaken plugin `./verify.sh`.

## คน — clients / people comms

Insurance sales math, client decks, leadership-shaped updates.

| Trigger | Skill |
|---------|--------|
| Commission from plan + premium | `insurance-commission` |
| Premium / plan finding | `insurance-premium-finding` |
| Thai sales deck from proposal PDF | `nuiny` |
| Exec/VP/PM Slack/JIRA/standup rewrite | `management-talk` |

## After routing

1. Load the chosen skill's `SKILL.md` (progressive disclosure).
2. Do not paste sibling skill bodies.
3. Cross-lane handoff: one sentence of state + which skill owns next — then switch.
