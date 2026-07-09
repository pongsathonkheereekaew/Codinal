# SoundToys Radiator — SoundToys (saturation / tube channel + EQ)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (manual: "Version 5, For Mac and Windows") |
| Type | Saturation / harmonic coloration — dual-stage tube mix channel with 2-band EQ |
| Format | VST / VST3 / AU / AAX (Mac + Windows; iLok authorized) |
| Source | manual: `SoundToys Radiator/SoundToys Radiator.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A "turn up the HEAT" tube channel: an emulation of the **Altec 1567A Mixer Amplifier**, a rack-mounted five-input tube mixer from the early 1960s with removable transformers, a simple two-knob EQ, and a whopping 97 dB of gain. Famous as part of the early Motown sound (1961–64, Motown Studio A) and later prized by producers (Matt Wallace, Butch Vig, Billy Bush) and bands (Black Keys built a custom console from 1567As) for cheap analog color. The original is colored, gritty, loud, and noisy by design. Radiator recreates its saturation and harmonics with **two cascaded tube saturation stages** straddling a modeled **2-band Bass/Treble tone stack**, and adds three things the hardware never had: a **Mix (Dry/Wet)** control for parallel processing inside the plug-in, a selectable **Mic/Line** mode that mirrors the 1567A's strongly impedance-dependent (level-dependent) frequency response, and an on/off choice for the modeled circuit **noise**. It's the full version; **Little Radiator** (Altec 1566A) is the stripped-down single-stage sibling. A beast on bass and drums; great for fattening guitars, vocals, electric piano, and shaking the "clean" off digital tracks.

Signal path (per manual): **clean input → Input drive → 1st tube saturation stage → 2-band EQ (Bass + Treble) tone stack → 2nd saturation stage (driven by Output) → one channel of the Dry/Wet mixer**.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Input** | −15 to +15 (knob, center 0) | Drive into the **first** tube saturation stage. Sets the gain of the signal entering Radiator's modeled circuit; as it rises, **saturation and output level both increase together**. This is the primary "amount of tube grit" control feeding the tone stack. | Main warmth/distortion control — turn up for more harmonics and break-up. Because it also raises level, gain-match (and trim with Output) when judging. |
| **Output** | −15 to +15 (knob, center 0) | Audio level out of Radiator, **and** the drive into the **second** saturation stage (post-tone-stack). Useful to make up for the level boost from Input, and — true to the original — **boosting Output adds its own additional saturation** before the wet/dry mix. | Set overall output level; push it to add a second layer of saturation, or pull it down to compensate for a hot Input. At extreme settings, trim further downstream in the host. |
| **Bass** | −10 to +10 dB (knob, 0 at 12 o'clock; CW = boost, CCW = cut) | Low-band of the modeled 2-band EQ, sitting **post-input-stage / pre-output-stage**. Models the 1567A's bass control: a **wide curve on cut, more of a sloping boost**. | Add low-end weight/thickness or tame mud; voiced like the vintage unit rather than a surgical EQ. |
| **Treble** | −10 to +10 dB (knob, 0 at 12 o'clock; CW = boost, CCW = cut) | High-band of the 2-band EQ, in the same tone-stack location. Works like the Bass control, modeling the hardware's treble behavior. | Add air/presence/bite or roll off harshness; interacts with the saturation stages for vintage top-end character. |
| **Mix** | 0% (Dry) → 100% (Wet) | Dry/wet blend. Mixes unprocessed (dry) signal with the processed (wet) signal; value = percentage of processed audio in the output. Enables **parallel processing inside the plug-in** without external bussing. (A Soundtoys addition — the hardware was effectively 100% wet only.) | Crank Input/Output for heavy saturation, then back Mix off so transients/clarity stay while harmonic density is added underneath. |
| **Mic / Line** (switch) | Mic ↔ Line | Source-impedance / level-response mode mirroring the 1567A's very level-dependent frequency response: **Mic = 150 Ω** behavior, **Line = 600 Ω** behavior. They give different overall frequency-response curves (see Fig. 3): Mic has a pronounced scooped low-mid dip + rolled top; Line is flatter through the mids with a rising top end and a small low bump. | Mic for the scooped, vintage "mic-pre" tonality; Line for a flatter, more extended response. Audition both — the difference is a tonal voicing, not just gain. |
| **Noisy / Clean** (switch) | Noisy ↔ Clean | Toggles the modeled **circuit noise** of the 1567A (noisy even at low saturation; **averages ~−68 dBu at max settings**, reduced by ~10 dB when **Line** is selected). **Clean** suppresses the modeled noise completely. | Noisy for authentic vintage hiss/character (lo-fi vibe); Clean for a clean noise floor, or when stacking many instances. |
| **Heat meter** (display) | VU-style, "HEAT" scale | Read-only VU-style meter styled after the 1567A. Calibrated to the 1567A's VU meter so Radiator and the hardware share the **same output-level and saturation characteristics** — i.e. it shows how hard you're driving the tubes ("the heat"). | Visual guide to how much saturation/level you're pushing; use it to dial repeatable drive amounts. |

## Use by lens
- **Producer (create):** A vibe/character stamp. Throw it on DI bass, drums, guitar, or electric piano and turn up **Input** for instant '60s Motown warmth and harmonic thickness; push **Output** to stack a second saturation layer for real grind. Flip **Mic** for the scooped vintage voicing and **Noisy** for old-PA grit straight into a clean digital arrangement. Use **Bass/Treble** to shape the colored tone to taste.
- **Mixing (balance):** Harmonic glue/saturation per track or on a bus. Keep **Input** modest, use **Line** for a flatter response, and dial tone with **Bass/Treble**. Use **Mix** for parallel saturation so you add density/presence without smearing transients. Remember **Input *and* Output both raise level and add saturation** — gain-match against bypass before judging, and use **Output** to re-balance. **Clean** keeps the noise floor tidy across many instances.
- **Mastering (finalize):** Not a precision mastering tool (no oversampling controls, no precise metering beyond the HEAT VU, colored by design), but small amounts add analog warmth/cohesion on a mix bus: very low **Input/Output**, **Line** + **Clean**, gentle **Bass/Treble**, and **Mix** pulled back for a subtle parallel blend. Use sparingly and A/B level-matched.

## Notes / gotchas
- **Two drive knobs, two stages:** **Input** drives stage 1 (pre-EQ), **Output** drives stage 2 (post-EQ) *and* sets level. Both couple drive ↔ level, so always gain-match (bypass A/B) and rebalance with Output / Mix when evaluating.
- **EQ sits between the two saturation stages** (post-input, pre-output), so tone-stack moves change *what* gets saturated by stage 2, not just the final EQ.
- **Mic vs Line is a tonal voicing**, not a gain trim — it re-shapes the whole frequency response (Mic = scooped/rolled, Line = flatter/extended) per the modeled 150 Ω vs 600 Ω impedance behavior. Line also drops modeled noise ~10 dB.
- **Modeled noise is intentional** (~−68 dBu at max); set **Clean** to remove it. It can accumulate if many instances run **Noisy**.
- **Heat meter is calibrated to the real 1567A VU** — same output/saturation reference as the hardware; treat it as a drive gauge, not a peak meter. At extreme **Output**, trim level later in the host or with a trim plug-in.
- Manual lists **no latency / oversampling / sidechain** controls. Part of the **Soundtoys 5** bundle (integrates with Soundtoys' Effect Rack); ships with factory presets. **100% of Radiator sales are donated** to not-for-profits (Soundtoys donation pledge). For the cut-down single-stage version (no EQ, no Mic/Line) see **Little Radiator** (Altec 1566A).

## Deep spec (Programmer only)
not reverse-engineered — capability only.
