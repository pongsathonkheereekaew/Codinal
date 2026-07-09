# SoundToys LittleAlterBoy — SoundToys (pitch/formant + saturation)

| | |
|---|---|
| Vendor / ver | Soundtoys · (manual © 2015) |
| Type | Monophonic voice manipulation — pitch shift + formant shift + tube saturation |
| Format | VST/AU/AAX (Mac & Windows; manual predates explicit format list) |
| Source | manual: `SoundToys Little AlterBoy/SoundToys LittleAlterBoy.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Little AlterBoy is a focused vocal pitch- and formant-manipulation tool: it transposes pitch in semitones, independently shifts formants to change vocal character (gender/age), and runs the result through a tube-saturation model borrowed from Decapitator. Pitch heritage comes from Soundtoys' PurePitch (the first real-time formant-shifting plug-in). It does everything from subtle transposition and doubling to gender/character morphing, hard auto-tune-style quantization, and single-note robot/vocoder effects. **Designed for clean, MONOPHONIC vocal tracks** — if chaining effects, insert it FIRST in the chain.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Pitch** | ±12.0 semitones (−12 = down one octave, +12 = up one octave) | Transposes vocal pitch up/down in semitones. In ROBOT mode it sets the locked note instead (0.0 = one octave above middle C). | Octave/interval shifts, harmonies, chipmunk/deep effects, DJ-style warps. |
| **Link** | on / off | Couples Formant to Pitch. ON: formant tracks pitch (tape-style speed-up/slow-down sound; smoother on tough material; needed for DJ pitch warping). OFF: pitch-shifts stay natural-sounding and Formant is adjustable independently. | ON for tape-warp / smoother shifts; OFF for natural shifts + independent formant control. |
| **Formant** | ±semitone-style display (e.g. −3.0) | Warps the vocal formant (EQ-resonance fingerprint) without changing pitch. UP = brighter/"feminine"/chipmunky; DOWN = deeper/richer/"masculine". Active when Link is OFF. | Gender/character morphing; add depth/richness to nasal or thin voices (−1 to −3 on backing vox); realism (nudge formant same direction as pitch shift). |
| **Mode: Transpose** | mode select | "Normal" mode — Pitch shifts the vocal with no auto-correction. | Standard pitch shifting, harmonies, doubling. |
| **Mode: Quantize** | mode select | Snaps vocal to nearest chromatic semitone as fast as possible — the hard, audible auto-tune/T-Pain effect heard on pop/rap/R&B. | Aggressive auto-tune robotic-vocal sound. |
| **Mode: Robot** | mode select | Locks the whole vocal to a single fixed note set by Pitch (0.0 = octave above middle C). Pitch knob plays the note; MIDI-mappable for vocoder-style playing. | Monotone/robot vocals, vocoder-style melodic robot lines via MIDI. |
| **Drive** | Min → Max | Analog-modeled tube saturation (Decapitator-derived) on the altered signal. Small = warmth; large = grit/edge/distortion. | Warmth, attitude, or full distortion; classic "Quantize + heavy Drive" pop vocal. |
| **Mix** | Dry → Wet | Blends dry original with wet processed signal. | Parallel harmony/doubling without bussing — blend a shifted voice under the original. |

## Use by lens
- **Producer (create):** Robot mode + MIDI keyboard for vocoder/robot melodies; Quantize + Drive for the in-your-face T-Pain pop hook; big ±12 pitch shifts with Formant for character voices (chipmunk, monster, gender-swap). MIDI-control Pitch for played intervals in Transpose/Quantize.
- **Mixing (balance):** Independent Formant (Link OFF) to reshape vocal character — drop formant −1 to −3 to add depth/richness to thin or nasal backing vocals; small Pitch + Mix blend to fatten a single take into a double or simple harmony; a touch of Drive for analog warmth/presence.
- **Mastering (finalize):** Not a mastering tool — it's a mono vocal-track insert, not a bus/master processor. Avoid on full mixes.

## Notes / gotchas
- **Monophonic vocals only** — single-note clean sources. Polyphony / dense material will artifact.
- **Insert FIRST** in any vocal effect chain (before EQ/comp/reverb/etc.).
- **Link** fundamentally changes the shifted sound: ON = tape-warp (formant follows pitch), OFF = natural + independent formant. ON is also smoother on difficult tracks.
- **Robot mode** ignores incoming melody (locks to one note); use Pitch or MIDI to set/play it.
- **Realism trick:** nudge Formant slightly in the same direction as the Pitch shift (up when up-shifting, down when down-shifting).
- **MIDI:** Pitch is MIDI-mappable for playing intervals (Transpose/Quantize) and notes (Robot) — see Soundtoys FAQ for DAW setup.
- Drive is the same tube-saturation lineage as Decapitator.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
