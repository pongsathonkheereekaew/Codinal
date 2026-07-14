# Thinking-flow eval — results summary

**Date:** 2026-07-14  
**Protocol:** [PROTOCOL.md](PROTOCOL.md)  
**Artifacts:** [runs/2026-07-14-A.md](runs/2026-07-14-A.md) · [runs/2026-07-14-B.md](runs/2026-07-14-B.md) · [runs/2026-07-14-SCORE.md](runs/2026-07-14-SCORE.md)

## Headline

Condition **B** (draft → scrutinize → final) beat freestyle **A** on all 3 scenarios (sum 36 vs 9). Threshold **PASS**.

Process does **not** raise model IQ; it raised **plan quality under a fixed rubric** in this session (simpler alternatives, layering, footguns).

## Decisions locked by eval

| Topic | Decision |
|-------|----------|
| `finalize-plan` skill | **No** — enhance `scrutinize` + AGENTS bullet |
| Always grilling+wayfinder | **No** — classify XOR |
| Drop AGENTS.bak | **No** — keep backup; optional prune |

## Round 2 (same day)

Held-out fixtures · A = **best-effort freestyle** · B = scrutinize gate.  
Scores: [runs/2026-07-14-R2-SCORE.md](runs/2026-07-14-R2-SCORE.md) — **marginal PASS** (Δ +2 vs R1 Δ +27).

**Takeaway:** process helps most when freestyle is thin; against careful freestyle the edge is small but cheap to keep (one AGENTS bullet + skill description).

## Shipped

Thin wiring landed on branch `feat/thinking-flow-wiring`: AGENTS Default loop classify + final-plan gate; `scrutinize` / `grilling` / `ask-matt` cross-links. Design: [DESIGN-thinking-flow.md](../../DESIGN-thinking-flow.md).

Optional later: third round with a different model as scorer only.
