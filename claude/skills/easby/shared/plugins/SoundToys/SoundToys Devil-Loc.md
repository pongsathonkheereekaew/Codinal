# SoundToys Devil-Loc — SoundToys (compressor/limiter + saturation)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (manual "Version 5, For Mac and Windows", © 2015) |
| Type | Brickwall limiter / heavy compressor + distortion (lo-fi "audio level destroyer") |
| Format | VST3 / AU / AAX (Soundtoys 5 era; manual states Mac & Windows) |
| Source | manual: `SoundToys Devil-Loc/SoundToys Devil-Loc.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Devil-Loc is a deliberately destructive limiter/compressor modeled on the Shure **Level-Loc** (Model M62 / M62V Audio Level Controller), a late-1960s consumer brickwall limiting amplifier built to keep PA/podium mic levels even. Engineers (notably Tchad Blake) repurposed its indiscriminate leveling, level-dependent auto-release, and gnarly distortion to make drums sound enormous. The plug-in distills that box down to **two knobs — Crush and Crunch** — for extreme compression, parallel "sucking" pump, fuzzy gating, and saturated lo-fi grime. Drive it hard for blitzed break-up; back it off for a vintage halo on loops, drums, or even the mix bus. It's the smaller sibling of Devil-Loc Deluxe (which adds Mix, Darkness, and selectable release).

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Crush** | knob 0–10 (panel detents 0–10) | Sets how much signal is driven into the (virtual) gain-reduction circuit. More signal in = more compression; drive it hard and the GR circuit saturates, producing a severe pumping/sucking effect. This is the "compression amount" control. | Add weight, pump, and room-ambience inflation to drums/loops; crank for extreme gating where loud hits crush to near-silence. |
| **Crunch** | knob 0–10 (panel detents 0–10) | Sets makeup gain applied **after** limiting and how hard the output amplifier stage is driven. The harder the output is driven, the more distortion — and there is plenty. This is the "drive/distortion + output level" control. | Dial in grit, fuzz, and harmonic break-up; use to restore/over-drive level after Crush squashes it. |

> The two knobs are interdependent — Crush feeds the GR circuit, Crunch drives the output. **Balancing Crush against Crunch** is how you span the full range from subtle vintage glue to all-out destruction. (No bypass/mix/release controls on plain Devil-Loc — those live in Devil-Loc Deluxe.)

## Use by lens
- **Producer (create):** The headline effect. Slam it on a drum kit, room mic, or loop to make it huge, ambient, and exciting; push Crush + Crunch to extremes for fuzzy gated "crush-to-silence" hits and saturated lo-fi loops. A go-to for character/effect rather than transparent control.
- **Mixing (balance):** Use in **parallel** (on a send/aux or a duplicate bus) for "sucking" parallel compression that inflates room/ambience without destroying the dry transients — blend to taste outside the plug-in since plain Devil-Loc has no Mix knob. Lighter settings add vintage grit/halo to drums, vocals, or guitars.
- **Mastering (finalize):** Not a clean mastering limiter — it's a flavor/effect. The manual cheekily invites trying it on the mix bus "if you dare"; use only at very gentle settings as a subtle vibe/glue move, in parallel, and A/B carefully. Reach for true limiters for final level.

## Notes / gotchas
- **Character, not transparency:** descriptors from the manual itself are "Dirty, Nasty, Trashy, Absolutely Wonderful." Expect distortion, pumping, and unpredictability by design.
- **Timing (from Specs):** Attack ≈ **1.3 ms**; Release ≈ **1.7 s (normal)**, stretching to ≈ **22 s when saturated** — i.e. the release lengthens dramatically as the circuit is pushed, recreating the Level-Loc's level-dependent auto-release. This is why hard settings can "duck and hold."
- **No Mix control:** for parallel compression you must blend externally (duplicate track / aux send). Devil-Loc **Deluxe** adds Mix, Darkness (tone), and selectable release time if you need to tame it.
- Not sold individually — part of the Soundtoys bundle. iLok authorized.
- Manual lists no oversampling/latency/CPU specifics beyond the attack/release times above.

## Deep spec (Programmer only)
Not reverse-engineered — capability only.
