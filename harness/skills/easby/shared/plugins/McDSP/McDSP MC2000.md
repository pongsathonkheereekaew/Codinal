# McDSP MC2000 — McDSP (multi-band compressor)

| | |
|---|---|
| Vendor / ver | McDSP · v7 (manual rev 2022) |
| Type | Multi-band dynamics compressor (2 / 3 / 4 band) |
| Format | AAX Native + AAX DSP, AU, VST3 (HD adds VENUE S6L). VST dropped as of v7. Intel + Apple Silicon. Mono + stereo, plus master-fader versions. |
| Source | manual: `McDSP MC2000/McDSP MC2000.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
MC2000 is a multi-band compressor whose every band is a full McDSP CompressorBank (CB1) compressor, split by steep 24 dB/oct FilterBank crossovers. Beyond standard Threshold/Ratio it adds two non-standard articulation controls — **Knee** (bidirectional: negative = soft "over-easy" dbx-style, positive = "overshoot" pumping + a "tail" range that backs off gain as level rises, opto-style) and **BITE** (lets transients pass while overall compression stays constant) — plus selectable peak-detection circuits (pure peak / adaptive release / auto). This lets one band morph between classic-compressor topologies (dbx 165, Neve 33609, 1176, LA-2A, Avalon AD2044), so you can run different "vintage units" per frequency band simultaneously. Ships as three plug-ins: **MC202** (2-band), **MC303** (3-band), **MC404** (4-band).

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Input** (master) | −24 to +24 dB | Gain into the comp algorithm, applied to L+R equally. No saturation — purely level. | Drive bands into threshold; keep band-input meters out of red. |
| **Output** (master) | −24 to +24 dB | Make-up gain after band summing (final output stage). Link-able in stereo. | Match bypassed loudness after compression. |
| **Crossover X1 / X2 / X3** | 20 Hz – 20 kHz | Split points between adjacent bands (24 dB/oct). Drag on Crossover Display or type values. | Place band edges around the trouble region (e.g. low/low-mid/presence/air). |
| **Master Bypass** | on/off | Forces all band In/Out to "Out" (bypassed). | True-bypass A/B of the whole processor. |
| **Master Link source** | Unlinked / Master 1..4 | Pick which band is master; others slave to it. | Gang bands for one-knob multiband moves. |
| **Master Meters** | Band Ins / Band Outs | Selects what the per-band OUTPUT METER shows (input vs output). | Watch what's hitting each band vs what's leaving. |
| **GAIN** (per band) | −24 to +24 dB | Make-up gain for that band after compression. | Restore band level after gain reduction; rebalance spectrum. |
| **THRESH** (per band) | −48 to 0 dB | Level above which the band compresses. | Set how much of the band's signal gets caught. |
| **COMP** (ratio, per band) | 1:1 to 10:1 | Compression ratio above threshold. | 2:1–4:1 gentle; 8:1+ heavy; with flat Knee + fast attack → brick-wall limiting. |
| **KNEE** (per band) | −10.0 to +15.0 | −10→0 = undershoot (soft/over-easy, dbx); 0 = hard knee; 0→+10 = overshoot (pumping/breathing, Neve 33609); +10→+15 = overshoot with "tail" (gain reduction eases as level rises → LA-2A/opto presence). | The character knob — morphs which classic compressor this band "is". Watch the Compression Display. |
| **BITE** (per band) | 1.0 to 50.0 | Bidirectional Intelligent Transient Enhancement — lets fast transients pass while overall compression amount stays the same; higher = more transient "bite". | Keep punch/attack alive under heavy GR; emulate analog transient behavior (used to mimic dbx 165 attack). |
| **ATTACK** (per band) | 0.25 to 25.0 ms | Rate the comp responds as signal rises above threshold. | Fast = catch transients (can pump/"cog"); slow = let attack through. Disabled in Auto. |
| **REL (Release)** (per band) | 25.0 to 2500.0 ms | Rate comp stops acting as signal falls below threshold. | Fast = aggressive/pumping; slow = smooth. Disabled in Auto. |
| **REL2 (Release 2)** | (spec table: part of TC; ~5 ms to 5.0 s per Quick Start) | Secondary/program release used by the adaptive circuit. Links relatively to Attack/Release. | Shapes multi-stage release behavior on Type-2. |
| **TC TYPE** (per band) | Type-1 / Type-2 | Detection circuit: Type-1 = pure peak detection (release unaffected by new signals below current release level); Type-2 = adaptive release (release reacts to new signals regardless of level). | Type-1 for predictable peak control; Type-2 for program-dependent, more analog feel. |
| **AUTO** (per band) | on/off | Automatic attack + release (and Release2); disables Attack/Release/REL2 controls. | Set-and-forget, program-adaptive timing. |
| **SOLO / IN (per band)** | on/off each | SOLO mutes all other bands (multiple solos allowed); IN enables/bypasses the band. | Audition a band in isolation; bypass a band to compare. |
| **MSTR (per band)** | on/off | Designates this band as the link master (only one at a time). | Choose the band whose moves drive the rest. |
| **Phase polarity (ø)** | normal/invert (in/out) | Polarity flip on the master I/O section. | Fix polarity issues; mid/side or parallel tricks. |

## Use by lens
- **Producer (create):** Treat each band as a different vintage box — e.g. dbx-style soft knee (−Knee) on lows for glue, Neve-33609 overshoot (+Knee) on mids for pump, LA-2A "tail" (+12–15 Knee) on highs for presence. Push BITE to keep drum/vocal transients snapping while still squashing. Use solo to dial each band, then un-solo. Great for parallel-style attitude on a bus.
- **Mixing (balance):** Tame specific problem ranges without touching the rest — sibilance/harsh mids, boomy lows, loud breaths. Set crossovers around the offending region, modest ratio (2:1–4:1), gentle negative Knee for transparency, Auto or Type-2 release. Link bands (Master) when you only need a global threshold nudge but want per-band offsets preserved.
- **Mastering (finalize):** Subtle, wide-band multiband control with steep 24 dB/oct splits and minimal crosstalk. Low ratios, soft knee, small per-band GAIN trims; watch the Compression Display for smooth curves. Use a band as a brick-wall limiter via flat overshoot Knee + 0.25 ms attack + high ratio when needed. Keep Input below clip (≈ −20 dBFS reference) — no input saturation stage.

## Notes / gotchas
- **Three separate plug-ins** (MC202/303/404) share one DSP chip; presets are interchangeable across band counts — bands missing in a smaller config default out, and switching CB config keeps prior settings. Loading an incompatible preset (e.g. a FilterBank EQ preset) → warning beep, settings retained.
- **Linking rules:** Gain/Threshold/Comp/Knee/Bite/Attack/Release link *relatively* (offsets preserved); TC Type + Auto link *absolutely* (slaves snap to master, but a slave's TC/Auto change unlinks just that control). SOLO and IN/Out never link (except Master Bypass).
- **Input has no saturation** ("Dolby Level" ≈ −20 dB reference) — don't expect tape/analog drive; use it purely for gain staging into the detectors.
- **Latency:** AAX DSP = 16 samples internal delay; AAX Native / AU / VST3 = zero latency. CPU ~doubles at 88.2/96 kHz.
- **Compression meter** is orange, reads right→left (more GR = further left); at 0 dB output (unity) input + comp-gain meters sum to output — useful to learn comp behavior. Click master output peak LED (hold Option/Alt) to clear all peak holds.
- **Preset families** map to the modeled gear: "blackface" (1176), "British Comp"/"British Limiter" (Neve 33609), "Old Smoothie" (dbx 165), "Class A Opto" (Avalon AD2044), "LA too, eh?" (LA-2A), plus app presets (vocal/drums/guitar/dialog).

## Deep spec (Programmer only)
not reverse-engineered — capability only.
