# SoundToys Devil-Loc Deluxe — SoundToys (extreme limiter / saturation)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 |
| Type | Extreme brickwall limiter + saturation/distortion (effect, not transparent dynamics) |
| Format | VST3 / AU / AAX (Mac & Windows) — not stated explicitly in manual; standard SoundToys 5 set |
| Source | manual: `SoundToys Devil-Loc Deluxe/SoundToys Devil-Loc Deluxe.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
"Audio Level Destroyer." A modeled emulation of the Shure Level-Loc / M62V — a 1960s consumer-grade brickwall PA limiter that producers (notably Tchad Blake) abused for its gritty, pumping, indiscriminate leveling plus heavy saturation and distortion. The job is not transparent control: it's extreme squash + grit to make drums and room mics gigantic, nasty, and lo-fi. The Deluxe version adds full studio control on top of the original's one-switch operation: tone (Darkness), switchable release times, and a wet/dry Mix so you can blend the destruction back in and automate it. Reach for it for crushed/pumping drums, sucking compression sweeps, blitzed saturated loops, and a "touch of evil" sizzle on vocals or acoustic guitar in small amounts. Bundle also includes the simpler 2-knob original Devil-Loc.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Crush** | knob, ~0→10 (drive into GR circuit) | Sets how much signal is sent into the gain-reduction circuit — more = more compression/limiting. Driven really hard, the GR circuit *saturates*, which switches the release behavior to the much longer "saturated" release times (see Notes). | The amount-of-squash control. Push up for heavier pumping/sucking compression and the extreme locked-down sound. |
| **Crunch** | knob, ~0→10 (post-limit gain / output drive) | Gain applied *after* limiting; also how hard the output amplifier stage is driven. Harder = more distortion ("plenty available"). | Dial in grit/distortion and makeup level. The dirt knob. |
| **Darkness** | knob, ~0→10 (high-cut cutoff) | Cutoff of a built-in high-cut (low-pass) filter. Filter is **post-distortion**, so it shapes/tames the harshness created by Crunch — rolls off crunchy highs for a warmer, darker tone. | Tame fizz, warm up the sound, get "dark thundering drums." |
| **Mix** | knob, 0→10 (dry↔wet %) | Dry/wet balance of processed vs. unprocessed signal. At 0 = 100% dry (signal passes through unprocessed); at 10 = 100% wet. | Parallel "New York" style crush — blend grit/ambiance under the dry, automate to stop the Devil from taking over. |
| **Release** | 2-position switch: Slow / Fast | Release time for the compression. Fast = release cut by a factor of two vs. Slow. | Slow for sustained, glued, sucking pump; Fast for snappier, more rhythmic/aggressive pumping. |

## Use by lens
- **Producer (create):** Primary sound-design tool. Slam drum buss / room mics with high Crush + Crunch for huge, nasty, pumping drums; use Release to set the pump rhythm and Darkness to keep it from getting too harsh. Use Mix to keep it usable, or go full-wet for blitzed lo-fi loops. Great as an aggressive effect on any source you want fatter, wilder, dirtier.
- **Mixing (balance):** Parallel processing is the move — set Mix low and blend crushed energy/ambiance under a clean drum buss to add density and attitude without losing transients. Small amounts add sizzle/grit to vocals or acoustic guitar. Darkness controls the brightness of the parallel layer so it sits. Not a transparent leveler — treat as a color/effect insert, usually on a parallel/aux.
- **Mastering (finalize):** Not a mastering limiter — it's a destructive effect with heavy distortion and a brickwall character; do not use for transparent loudness or final peak control. At most, a deliberate creative/lo-fi color on a stem in genre-appropriate material, parallel and subtle. Use a proper transparent limiter (e.g. Pro-L 2 / ML8000) for the actual master.

## Notes / gotchas
- **Saturated-release behavior:** When Crush drives the GR circuit into saturation, the release time jumps dramatically. Specs — Attack ≈ 1.3 ms. Slow release ≈ 1.7 s (normal) / ≈ 22 s (saturated). Fast release ≈ 0.85 s (normal) / ≈ 11 s (saturated). So heavy Crush can lock the level down for many seconds (the "locked" PA-limiter character) — expect long, sucking recovery, not a clean reset.
- **Signal order:** distortion happens before the high-cut filter, so Darkness sculpts the distortion harmonics (it's a tone shaper for the grit, not just a clean post-EQ).
- **Mix = front-panel parallel** — no external routing needed; automatable.
- **Bundle:** ships with the original 2-knob **Devil-Loc** (Crush + Crunch only, no Darkness/Mix/Release) as a separate, simpler plug-in.
- No mention of sidechain, oversampling, or reported latency in the manual; treat as a character effect, not a measurement-grade limiter.
- Mono/stereo; runs in the SoundToys Effect Rack (chainable with other SoundToys 5 effects). iLok authorization.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
