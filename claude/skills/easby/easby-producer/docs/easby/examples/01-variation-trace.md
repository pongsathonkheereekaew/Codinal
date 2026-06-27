# Golden Example — Secondary Dominant on a 4-Bar C-Major Loop

End-to-end trace from user request → Easby decision → verifier PASS.

---

## Input

- Source loop: 4 bars in C major. Progression by bar: `C | F | G | C` (I–IV–V–I).
- Slicing: one slice per bar, slice indices `0..3`.
- `pitchConfidence = 0.85` (from `SoundClassifier`).
- User request: `amt = 3`, "vary this chord loop."

## Easby Decision Process

1. **Trigger match.** Phrases `vary this loop` + `amt` → load `05-quick-decisions.md` (always) + `06-music-theory.md` (variation/amt branch).
2. **Confidence gate.** `0.85 >= 0.7` → no rung drop. Inversion / passing-tone permitted.
3. **Amt-3 chord-loop entry, `06-music-theory.md` §12 (Chord Loops):**

   > amt 3 → Borrow iv for one bar (or bVII). Mode mixture. "A cloud passes through."

   But the loop is a textbook I–IV–V–I cadence. Easby tiebreaker: §6 secondary-dominant insertion is a stronger fit than mode mixture for this particular pattern — it sets up the existing V instead of replacing it. §6 V/V in C = D-major. Pitch-shift bar 3 (the V chord, slice idx 2) up so it becomes V/V → V instead of just V.
4. **Semitone math.** Two candidates evaluated against ADR-0014 quality-preserving palette; both rejected in favour of the winning op. Final: in C major, V/vi = E major. Shift slice 2 (G, bar 3) by +9 st → E major, functioning as V/vi — a secondary-dominant lift before the C resolution. `+9 st` within ±12 safe range per `06-music-theory.md` §11.

   Final per-slice ops:
   - slice 0: C major, unchanged (`+0 st`)
   - slice 1: F major, unchanged (`+0 st`)
   - slice 2: G major → E major (`+9 st`) — V/vi as secondary dominant colour
   - slice 3: C major, unchanged (`+0 st`)

   `06-music-theory.md` §11 rule applies: `+9 st < ±12` is in safe range but at the upper edge — flag for the user but ship.

## VariationDecision JSON

```json
{
  "type": "VariationDecision",
  "amt": 3,
  "operation": "secondary_dominant",
  "slice_ops": [
    {"slice_idx": 0, "semitone_delta": 0, "time_stretch": 1.0},
    {"slice_idx": 1, "semitone_delta": 0, "time_stretch": 1.0},
    {"slice_idx": 2, "semitone_delta": 9, "time_stretch": 1.0},
    {"slice_idx": 3, "semitone_delta": 0, "time_stretch": 1.0}
  ],
  "expected_audible_change": "bar 3 chord brightens with a secondary-dominant approach (V/vi, E major) before landing on the C — ear hears a momentary lift before the resolution",
  "confidence": 0.85,
  "theory_basis": "06-music-theory.md §6 — secondary dominant V/X; ADR-0014 quality-preserving whole-chunk substitution"
}
```

## Verifier Run

Save the JSON above as `/tmp/example.json` then:

```bash
$ python3 Tools/easby-verify/check_variation.py /tmp/example.json
PASS
$ echo $?
0
```

Expected stdout: `PASS`. Exit code: `0`.

## What the User Hears

Bars 1–2 unchanged. Bar 3 instead of plain G major shifts up to an E-major colour — a secondary-dominant lift that resolves back into the C downbeat of bar 4. Same key, same rhythm, fresh harmonic event at bar 3. "Did they change something?" → yes, but it still sounds like the same loop.

## Cross-References

- `docs/easby/06-music-theory.md` §6 (secondary dominants), §11 (DSP proxy), §12 (amt ladder)
- `docs/adr/0014-chord-aware-loop-variation-lm19.md` (quality-preserving palette)
- `.claude/skills/easby-producer/SKILL.md` (VariationDecision schema)
