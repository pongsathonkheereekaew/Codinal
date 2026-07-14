# Thinking-flow eval — protocol

Compare **Condition A** (freestyle “final plan”) vs **Condition B** (Matt-thin gate: classify → draft → **scrutinize** → revise or mark rework).

## Rubric (0–2 each, max 12)

| ID | Criterion |
|----|-----------|
| R1 | Goal stated in one sentence; scope boundaries clear |
| R2 | Simpler alternative considered (or explicit why not) |
| R3 | Touches real paths/files that exist (or flags missing evidence) |
| R4 | Failure modes / footguns named |
| R5 | Distinguishes always-on vs skill vs adapter correctly |
| R6 | Actionable ship steps without parallel “religions” or prompt dumps |

**Pass threshold:** B mean ≥ A mean + 1.5 total points across scenarios, or B wins ≥2/3 scenarios on total score.

## Conditions

- **A:** Write a final plan in one pass. No self-scrutinize. Aim for speed.
- **B:** Draft → run scrutinize workflow on that draft → emit final plan + verdict.

Same model, same fixtures, same rubric. Scorer must cite lines from the artifact.

## Non-goals

- Not an LLM-vs-LLM model bakeoff
- Does not prove production bug reduction — only plan-quality under process
