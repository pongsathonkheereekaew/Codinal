# SoundToys Little PrimalTap — SoundToys (delay)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (manual "Version 5: For Mac and Windows", © 2015) |
| Type | Vintage digital delay (lo-fi / pitch-warp / saturated feedback) |
| Format | VST/VST3/AU/AAX (typical SoundToys; not explicit in manual). Mac & Windows. iLok authorized. |
| Source | manual: `SoundToys Little PrimalTap/SoundToys Little PrimalTap.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A character digital-delay emulation of the Lexicon Prime Time Model 93 (1978) — a "Little" (stripped, single-knob-each) version of SoundToys' full PrimalTap. Its signature is the **Multiply** behavior of the original hardware: to fake long delay times on 1970s memory, the unit *halved its sample rate (and engaged steep anti-aliasing filters) every time the delay was doubled*. So fidelity drops as delay grows — at the max 8X setting bandwidth collapses to a very lo-fi ~1.5 kHz. Combined with a smooth **Adjust** sample-rate sweep that pitch-bends the delay (bucket-brigade / Memory-Man style), an **Input drive** stage with its own saturation, and a **Feedback** that can go infinite, it produces gritty echoes, octave/pitch jumps, chorus/flange smears, runaway loops, and sci-fi "space noise." A creative mangler, not a clean/tempo-synced echo. Changing Time/Multiply while audio plays glitches on purpose (period-correct artifact).

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Time** (numeric "PRIME" readout + knob) | milliseconds; base up to ~512 ms (doubled from the original's 256 ms; 128 ms on non-expanded units) | Sets base delay time, old-school style in raw ms (no tempo sync). Turning it while audio plays *creates audible glitches* — by design, like the hardware. Total delay is further shaped by Adjust & Multiply. | Dial the core echo length / loop length; long values = big looping power. Automate it for tape-stop-ish jumps. |
| **Adjust** | 1X → .5X (smooth, continuous) | Smoothly *reduces* the set Time by up to one-half by changing the delay's sample rate. Because it's continuous you hear an obvious **pitch bend / chorus / flange** sweep as you move it (bucket-brigade behavior). Dramatic when feedback is high or a snippet is captured. | Pitch-warp, chorus, flange, dive-bombs, "wow"-style modulation; performable/automatable pitch shifting. |
| **Multiply** | stepped: 1X · 1.5X · 2X · 3X · 4X · 6X · 8X · 12X (panel marks 1X 1.5 2X 3 4X 6 8X 12) | Multiplies the current delay time by the selected factor. Each step up halves sample rate + engages steeper anti-alias filtering, so **higher = longer but more lo-fi** (8X ≈ 1.5 kHz bandwidth, the classic grimy PrimalTap tone). Changing it mid-audio causes glitches; great for **octave shifting** with long times + feedback. | Reach for lo-fi grit, extended delay/loop times, octave drops, "fidelity goes down as delay goes up" character. |
| **IN** (slider) | input gain | Drives the input stage. A little = louder; a lot = saturates/overdrives with a distinctive lo-fi **saturation** character of its own. | Add dirt/warmth; push the delay into distortion for aggressive lo-fi echoes. |
| **FB** (slider) | feedback amount, up to infinite | "Regen"/repeats — how much delayed signal is fed back to the input. Low = a few repeats; high = long luscious regeneration; max = **infinite, saturated, self-oscillating loops** (LOUDNESS WARNING). Combine with Adjust/Multiply for evolving cascades. | Dub repeats, sustained loops, runaway sci-fi noise, synth-like drones, sound-design layers. |
| **Mix** (slider) | dry↔wet, 0–100% wet | Wet/dry balance. Full up = 100% wet (only processed sound); full down = 0% processed (dry only). | Blend echo into a track (send-like low values) or go fully wet on an aux/return. |

## Use by lens
- **Producer (create):** The fun engine. Capture a phrase, crank **FB** toward infinite, then sweep **Adjust** and step **Multiply** for octave jumps, pitch dives, chorus/flange and otherworldly cascades — instant sci-fi pads, dub throws, lo-fi tape-ish echoes, and synth-from-feedback textures. Automate **Time**/**Multiply** for glitchy transitions. Push **IN** for grit on its own.
- **Mixing (balance):** Use as a *character* delay on an aux/return (Mix high) to add vintage lo-fi color, grime, and width to vocals, guitars, synths, drums. Higher **Multiply** darkens/dirties the tail so echoes sit behind the dry source without masking. Moderate **FB**, modest **IN** drive for warmth. Not your clean/tempo-synced workhorse delay.
- **Mastering (finalize):** Not a mastering tool — it's an unclean, glitch-prone, self-oscillating creative effect with no tempo sync or transparent mode. Avoid on a master bus except for deliberate special-FX/transition moments.

## Notes / gotchas
- **Glitches by design:** moving **Time** or **Multiply** during playback produces audible anomalies/glitches — intended period-correct behavior, not a bug.
- **Fidelity tied to delay length:** higher **Multiply** = lower bandwidth/more lo-fi (8X ≈ 1.5 kHz). The grime is the feature.
- **Adjust = sample-rate/pitch sweep:** it shortens Time by up to half *and* shifts pitch continuously (bucket-brigade style); expect chorus/flange/pitch artifacts whenever you turn it.
- **Feedback can self-oscillate → LOUDNESS WARNING:** high/infinite **FB** with **IN** drive can get very loud and saturated fast; watch levels.
- **No tempo sync / no ms snapping shown:** Time is set in raw milliseconds; this is not a beat-synced delay.
- **"Little" = single control per function**, no preset menu/modes detailed in the manual. The deluxe **PrimalTap** adds two independent delay lines, an LFO for automated pitch shifting, selectable delay algorithms, and a Freeze effect — reach for it when you need those.
- **Automation-friendly:** SoundToys highlights using automation (esp. Time, Multiply, Adjust) to bring tracks to life.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
