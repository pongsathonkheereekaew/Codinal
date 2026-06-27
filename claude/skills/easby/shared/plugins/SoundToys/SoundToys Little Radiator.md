# SoundToys Little Radiator — SoundToys (saturation / tube preamp)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (manual: "Version 5, For Mac and Windows") |
| Type | Saturation / harmonic coloration — modeled tube mic-preamp |
| Format | VST / VST3 / AU / AAX (Mac + Windows; iLok authorized) |
| Source | manual: `SoundToys Little Radiator/SoundToys Little Radiator.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A "little tube heat" coloration box: an emulation of the **Altec 1566A**, a simple three-stage tube mic preamp / power-amp from the early 1960s (Motown era, found in PA systems, churches, school auditoriums). It injects rich tube harmonic distortion, warmth, and "punch" — driving and breaking up the way the original hardware did. Distinct from a clean preamp: it is intentionally colored and gritty, with a modeled version of the unit's old-fashioned circuit noise. It's the stripped-down sibling of **Radiator** (the 1567A, which adds EQ and Mic/Line modes); Little Radiator drops all that and exposes only the four essentials. Great for fattening bass, guitar, drums, vocals, and especially electric piano, and for shaking the "clean" off digital recordings.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Heat** | −15 to +15 (knob, center 0) | Master drive. Sets the gain of the signal entering the modeled tube circuit; as Heat increases, **both saturation and output level increase together**. This is the amount of drive into the tube saturation stage → more harmonic distortion the higher you go. | The main tone control — turn up for more warmth/grit/harmonics; near 0/low for subtle color. Note output level rises with it, so re-balance after. |
| **Mix** | 0% (Dry) → 100% (Wet) | Dry/wet blend. Mixes unprocessed (dry) signal with the processed (wet) signal; the value is the percentage of processed audio in the output. Enables **parallel saturation inside the plug-in** without external bussing. (Not on the original hardware — a Soundtoys addition.) | Parallel processing: crank Heat hard, then back Mix off to taste so transients/clarity stay while harmonics are added underneath. |
| **Bias** | switch: OFF / ON | Selects between two saturation styles modeled from different observed 1566A units. **ON = more distorted** (dirtier, slightly choppy/misaligned grit). **OFF = more accurate / pristine** hardware sim with gentler saturation. | OFF for clean-ish warmth; ON for lo-fi grit on drums or to rough up vocals. |
| **Noise** | switch: ON (up/engaged) / OFF (down/disengaged) | Toggles the modeled circuit noise of the original 1566A (which is noisy even at low saturation). Down = no modeled noise. | Engage for authentic vintage hiss/character (lo-fi vibe); disengage for a clean noise floor. |

## Use by lens
- **Producer (create):** A character/vibe stamp. Throw it on a DI bass, electric piano, guitar, or a drum bus and turn up **Heat** for instant '60s warmth and harmonic thickness. Flip **Bias ON** + **Noise ON** for deliberately lo-fi, gritty drums or grungy vocals — that "tape/old-PA" flavor straight into a clean digital arrangement.
- **Mixing (balance):** Use as gentle harmonic glue/saturation per track or on a bus. Keep **Heat** modest, **Bias OFF** for cleaner warmth, and use **Mix** for parallel saturation so you add density and presence without smearing transients. Watch that **Heat raises output** — gain-match against bypass before judging.
- **Mastering (finalize):** Not a precision mastering tool (no metering, no oversampling controls, colored by design), but small amounts can add analog warmth/cohesion to a mix bus: very low **Heat**, **Bias OFF**, **Noise OFF**, and **Mix** pulled back for a subtle parallel blend. Use sparingly and A/B level-matched.

## Notes / gotchas
- **Heat couples drive and output** — increasing it makes things louder as well as more saturated; always gain-match (bypass A/B) when evaluating, and use Mix to re-balance.
- **Two distortion flavors only** via the Bias switch (ON = dirtier, OFF = cleaner) — there's no continuous bias control.
- **Modeled noise is intentional**; if you want it gone, set the Noise switch down. It can build up if many instances are noise-on across a session.
- **No EQ / no Mic-Line / no metering** — this is the cut-down version. For tone-shaping (EQ section, Mic/Line modes) reach for the bigger **Radiator** (Altec 1567A).
- Manual lists no latency/oversampling/sidechain. Part of the **Soundtoys 5** bundle; integrates with Soundtoys' Effect Rack. Comes with factory presets.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
