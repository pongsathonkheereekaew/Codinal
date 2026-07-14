# Music Theory — DSP Wiring + Variation Ladder (Easby-Critical)

> Originally part of `06-music-theory.md`. Split for load efficiency. Owns the Wiring
> section + §11 DSP Proxy Table + §12 Variation Amount Ladder. This file is the
> **bridge between theory and the audio engine** — load whenever an amt/variation
> decision is being emitted.

---

## Wiring — Theory to our Codebase

| Theory operation | Codebase owner | Entry point |
|---|---|---|
| Variation amt 1–5 (melody) | `real_helper.py::_melodic_phrase_regen` | `amt` param |
| Variation amt 1–5 (chord) | `real_helper.py::_chord_phrase_regen` | `amt` param |
| Variation execution (C++ side) | `Source/Audio/Generator/CreateVariationController.{h,cpp}` | `createVariation()` |
| Pitch confidence source | `Source/Audio/SoundClassifier.h` + `Source/Audio/AnalysisCoordinator.h` | `pitchConfidence` field |
| Key/mode detection | `Source/Audio/AubioUtils.h` | `estimateKey()` |
| Pitch shift per slice | `Tools/generator-helper/real_helper.py::_pitch_shift_chunk` | `semitone_delta` arg |
| Time stretch | `Tools/generator-helper/real_helper.py::_time_stretch` | `factor` arg |

⚡ Easby decides the operation + semitone_ops. Codebase executes. Easby does not call codebase directly.

**Pitch confidence gate:** if `pitchConfidence < 0.7` from SoundClassifier → drop amt one rung (amt=3 → treat as amt=2). Never apply inversion or sequential modulation on low-confidence pitch.

---

## 11. ⚡ DSP Proxy Table — Theory → Semitone Operations (CRITICAL)

**This is the bridge.** Easby works on audio slices, not symbolic notes. Every theory concept above has to map to a semitone operation (or sequence of them) applied to one or more audio slices. If a concept can't, it doesn't exist in our engine.

| Theory concept | Audio operation | Semitone math |
|---|---|---|
| **Sequence (up a 2nd)** | Pitch-shift slice +2 | +2 st |
| **Sequence (up a 3rd, diatonic)** | Pitch-shift +3 or +4 depending on scale | +3 or +4 st |
| **Inversion** | Reflect intervals around axis pitch: `new = 2·axis − old` | per-note recalculation |
| **Augmentation** | Time-stretch slice 2× (preserve pitch) | duration ×2 |
| **Diminution** | Time-stretch slice 0.5× | duration ÷2 |
| **Retrograde** | Reverse buffer | sample order flipped |
| **Passing tone insertion** | Insert short slice pitched between two chord tones | midpoint ±1 st, ≤ M3 gap rule |
| **Neighbor tone** | Insert slice ±1 or ±2 st from anchor, return to anchor | ±1 or ±2 st |
| **Suspension** | Hold previous slice's last pitch over chord change, then step down 1–2 st | 0 → −1 or −2 st |
| **Pedal point** | Layer a sustained slice at root pitch under everything | constant 0 st on pedal voice |
| **Borrow iv (in major)** | Lower the 3rd of the IV slice by 1 st | −1 st on chord 3rd |
| **bVII** | Pitch-shift the V chord slice down 1 st (V → bVII relative to I differs; in C, G → Bb is +3) | −1 st from V root, or transpose IV up +2 |
| **Picardy 3rd** | Raise the 3rd of the final i slice by 1 st | +1 st on chord 3rd |
| **Secondary dominant V/X** | Take target chord X, build major triad on its 5th, add b7 — pitch-shift a dom7 stamp to that root | root of X + 7 st, with b7 stamp |
| **Tritone substitution** | Pitch-shift the V slice down 6 st (or up 6) | ±6 st |
| **Neapolitan (bII)** | Pitch-shift a major triad stamp to bII root | tonic + 1 st as new root |
| **Ger+6 → V** | Pitch-shift dom7 stamp to bVI root | tonic + 8 st as new root |
| **Deceptive cadence** | Replace final I slice with vi slice | root + 9 st (or −3 st) |
| **Modulation (sequential, +M2)** | Pitch-shift entire loop +2 st | +2 st global |
| **Modulation (sequential, +m3)** | Pitch-shift entire loop +3 st | +3 st global |
| **Modulation (direct, up a 4th)** | Pitch-shift entire loop +5 st | +5 st global |

⚡ **Rules of the proxy:**
1. **Pitch-shift bounds are grain-duration-aware** (Roads, *Computer Music Tutorial* pp.88–89). Formant artifacts emerge faster on short grains:

   | Grain / slice duration | Safe pitch-shift range |
   |---|---|
   | < 20 ms (percussive transients, granular dust) | ±5 st |
   | 20–50 ms (short one-shots, plucks) | ±6 st |
   | > 50 ms (sustained chord/lead slices) | ±7 st |

   Chord loops with held notes default to the ≤ 50 ms bucket because the chord-tone steady state dominates the perception window. Phase-vocoder-based pitch-shift smears spectrally above ±5 st regardless of duration — drop to ±5 st when using the STFT path.

2. **Time-stretch degradation is grain-size-aware** (Roads pp.106–107). Stated 0.5×–2× bounds are correct for grain sizes ≤ 100 ms; for grains > 100 ms with stretch > 2× or < 0.5×, transient blur becomes audible — fall back to granular time-stretch (asynchronous cloud) instead of straight phase-vocoder stretch.
3. The ≤ M3 gap rule (see `06a-core-progressions.md` §4) applies to every passing-tone insertion. No exceptions.
4. Inversion in audio requires knowing the slice's pitch first — gated on confident pitch detection. If pitch confidence < 0.7, skip inversion and use sequence instead.

→ See `01-synthesis-engine.md` for the slice-level DSP primitives this table assumes.

---

## 12. Variation Amount Ladder (amt 1–5)

When the user asks for "a little different" vs "a lot different," this is what each amt level means in theory terms. Two ladders — one for **melodic loops**, one for **chord loops**.

### Melodic Loops

| amt | Operation | Theory basis | Audible change |
|---|---|---|---|
| **1** | Diatonic passing tone insertion (1–2 notes) | Non-chord tones, ≤ M3 gap rule | Same melody with ornaments. "Did they change something?" |
| **2** | Sequence: last 2 bars repeated +2 or −2 st | Melodic sequence | "Oh, they extended it." |
| **3** | Inversion of second half | Melodic inversion | "Same shape, opposite direction." |
| **4** | Diminution + secondary dominant approach on cadence | Rhythmic compression + V/X | "This is a variation, not the original." |
| **5** | Sequential modulation +3 st on second half | Sequential modulation | "This is the bridge / outro version." |

### Chord Loops

| amt | Operation | Theory basis | Audible change |
|---|---|---|---|
| **1** | Add 7ths to existing triads | Seventh-chord substitution | Same progression, more colour. |
| **2** | Rotate progression (I–V–vi–IV → vi–IV–I–V) | Progression rotation | Same chords, different mood. |
| **3** | Borrow iv for one bar (or bVII) | Mode mixture | A cloud passes through. |
| **4** | Insert secondary dominant before the IV or vi | V/X | Forward momentum, jazz tint. |
| **5** | Deceptive cadence + sequential modulation +2 st on repeat | Deceptive cadence + sequence | The loop becomes a section, not a loop. |

⚡ **Default ladder behaviour:** the user picks amt, the engine picks WHICH operation at that level based on what the source loop can structurally support. If pitch confidence is low, drop one rung. If the loop is already chromatic, drop one rung. Better to under-deliver variation than to ship a glitch.

→ See `05-quick-decisions.md` for the amt-selection heuristics when the user is vague.

---

## Cross-references

- Cadences, 7ths, NCT, melodic alteration source rules → `06a-core-progressions.md`
- Secondary dominants, borrowed chords, Neapolitan/Aug6 source rules → `06b-secondary-borrowed.md`
- Modulation strategies feeding the +M2/+m3 ops → `06c-modulation.md`
- Voice-leading constraints affecting which semitone ops are legal in 4-voice contexts → `06f-voice-leading-analysis.md`
