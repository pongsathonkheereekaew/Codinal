---
name: easby
description: >
  Easby suite router for audio plugin / music craft. Use when the user says easby
  without a stage, or mentions produce/mix/master/decomp/DSP clone and needs the
  correct sibling skill. Loads INDEX then routes — does not own stage decisions.
---

# Easby

1. Read [`INDEX.md`](INDEX.md) — trigger table, disambiguation, handoff contracts.
2. Route to **one** sibling: `easby-producer` | `easby-mixing` | `easby-mastering` | `easby-decomp` | `easby-programming`.
3. Bare process words (EQ / compress / limit / M/S) → ask stage if unclear (INDEX rule).
4. Shared music KB: [`shared/INDEX.md`](shared/INDEX.md). CLEAN specs may cross into product; REF/TAINTED never ships.

Desk entry that also covers insurance/คน: `desk-domains`.
