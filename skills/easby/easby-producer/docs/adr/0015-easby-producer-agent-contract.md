# Easby-Producer agent contract — retrieval-on-demand music-production knowledge agent

**Status:** accepted

`easby-producer` is promoted from a pile of producer-mind markdown into a real ECC-compliant agent with structured output schemas, a retrieval-on-demand load policy, a precedence rulebook, and a deterministic verifier. Variation, synthesis, and music-theory decisions emit JSON; the C++/Python variation engine executes the JSON.

## Context

`docs/easby/*` started as Welsh / Chowning / Hutchinson / Swedien reference material in first-person prose, with no machine-readable surface. The Create Variation engine (`real_helper.py` + `CreateVariationController`) was choosing amt operations from hard-coded ladders without consulting any musical reasoner, which is exactly the gap ADR-0014 (lm19) tried to close with cadence detection and a quality-preserving substitution palette. A second gap remained: lm19 still needs *someone* to decide which operation at which amt for which loop shape — that "someone" is the easby knowledge base, but as written it was un-loadable as an agent (no triggers, no scope, no schemas, first-person prompt-injection risk, all 6 files loaded at once = ~30k tokens per query, conflicting advice between files with no precedence rule, no verifier).

We considered (a) collapsing the six files into one mega-prompt; (b) keeping easby as pure prose and letting the primary agent extract decisions ad-hoc each call; (c) inlining the rules into `real_helper.py` as Python data. All three were rejected: (a) blows the context budget on every variation request and reloads recording / composition material that the variation engine never needs; (b) produces non-deterministic JSON shapes that the C++ controller can't safely parse; (c) couples musical taste to DSP code and prevents the rules from being read by humans the same way the engine reads them.

## Decision

**1. SKILL.md with explicit triggers, scope, non-scope, and load-order policy.** `.claude/skills/easby-producer/SKILL.md` defines the agent: trigger phrases (`vary this loop`, `create variation`, `develop melody`, `what waveform`, `amt`, `vary loop`, `easby`, `sound design`, `synthesis recipe`, `music theory variation`), persona in third person, scope (sound design, variation-amount selection, melodic / harmonic / rhythmic development, synthesis recipes, music-theory-grounded loop variation), and non-scope (mix-bus mastering, BPM-without-context, key detection, recording engineering). Out-of-scope requests get an explicit refusal with redirect to the subsystem that does own it.

**2. Retrieval-on-demand, not all-at-once.** Only `05-quick-decisions.md` loads on every query (hot-path lookup). The other five files load conditionally on trigger keywords (theory → `06`, synthesis → `01`+`02`, recording → `04`, arrangement → `03`, taste tiebreaker → `00`). `docs/easby/INDEX.md` is the machine-readable index of triggers and per-file token estimates. A typical chord-loop variation request loads `05` + `06` ≈ 8.5k tokens instead of all six ≈ 30k.

**3. Conflict precedence is explicit and named.** When files appear to disagree the order is `06` (theory) > `02` (recipes) > `01` (synthesis math) > `03` (composition) > `04` (recording) and `05` (quick decisions) wins for hot-path; `00` (producer mind) is taste-tiebreaker only. Easby cites the rule applied when resolving a conflict — "06 wins on theory" is a real reasoning step, not implicit. The retrograde rule (`03` lists retrograde as a melodic move; `06` flags it as a tonal-pop failure mode) is the canonical example and is annotated inline in both files.

**4. Two structured output schemas.** `VariationDecision` (for loop / melody / chord variation) carries `amt`, `operation` (closed enum: `sequence | inversion | deceptive_cadence | secondary_dominant | mode_mixture | picardy | borrowed_bVII | borrowed_bVI | sequential_lift | passing_tone | rhythmic_swing`), `slice_ops[]` of `{slice_idx, semitone_delta, time_stretch}`, `expected_audible_change`, `confidence`, and `theory_basis`. `SoundDesignTarget` (for synthesis / patch questions) carries waveform, VCF, ADSR-VCA, ADSR-VCF, optional FM params, and notes. Schemas live in SKILL.md.

**5. Refusal gates wired to the codebase.** Pitch confidence (from `SoundClassifier`) `< 0.7` drops amt one rung and refuses `inversion` / `passing_tone`. Passing-tone insertions wider than a major 3rd (4 semitones) are refused per `06-music-theory.md` §4. Pitch / confidence / key always come from the codebase (`SoundClassifier`, `AnalysisCoordinator`, `AubioUtils::estimateKey`) — easby never invents them.

**6. Codebase wiring is one-way.** Easby decides; `CreateVariationController.{h,cpp}` + `real_helper.py` execute. Easby does not call codebase entry points. `docs/easby/06-music-theory.md` carries the operation → entry-point table so future maintainers see the contract from the theory side.

**7. Deterministic verifier.** `Tools/easby-verify/check_variation.py` validates a `VariationDecision` JSON: amt in `1..5`, semitone_delta in `[-12, +12]`, time_stretch in `[0.5, 2.0]`, operation in enum, confidence-gated operations satisfied, M3 gap rule satisfied for passing-tone. Exit `0` PASS, `1` FAIL. Single-file, stdlib only, < 80 lines. A worked end-to-end example sits at `docs/easby/examples/01-variation-trace.md` and passes the verifier.

## Consequences

- Variation requests load ~8.5k tokens (`05` + `06`) instead of ~30k (all six). Synthesis-recipe requests load ~13.5k (`05` + `01` + `02`). Recording / composition material does not enter the context of a variation call.
- `CreateVariationController` and `real_helper.py` can parse a fixed JSON shape and reject malformed easby output via the verifier — no more interpreting prose.
- First-person prose in instruction tables (prompt-injection risk: "I reach for X" rules being re-narrated as if the model were the producer) is rewritten to imperative / "Easby" voice across `00..06`. Epigraph quotes stay first-person because they are explicitly bounded as quotes, not rules.
- `01-synthesis-engine.md` is compressed by ~30% — the parametric base-model knowledge (Bessel-function derivation, Carson's-rule derivation, general wavetable theory) is removed, the our-specific decisions (cheatsheets, `J0=0 at I=2.4`, `BW ≈ 2(D+M)`, "always interpolate, SNR 109 dB vs 48 dB") are kept.
- ADR-0014 lm19's "quality-preserving palette" constraint propagates into the easby schema: deceptive-cadence is *bVI-based proxy* in audio land, picardy and mode-mixture are constrained to whole-chunk operations that preserve chord quality. The schema enum admits these names without misrepresenting what the DSP actually does.
- Adding a future operation (lm20 RAVE-based timbral substitution, partial-aware pitch shift) requires extending the `operation` enum in SKILL.md + verifier + theory wiring section; no change to `00..05`.
- `00-producer-mind.md`'s status as taste-only tiebreaker is documented — preventing it from being weaponised to override a `06` theory rule on a variation request.
- AGENTS.md gains an easby-producer row in its skill table so the issue-tracker and primary-agent bootstrap see the agent as a first-class skill.
