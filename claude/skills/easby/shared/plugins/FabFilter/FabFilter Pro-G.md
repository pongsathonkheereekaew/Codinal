# FabFilter Pro-G — FabFilter (gate / expander)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-G |
| Type | Gate / expander (downward + upward expansion, ducking) — dynamics |
| Format | VST, VST3, CLAP, AU (macOS), AAX Native, AudioSuite |
| Source | manual: `FabFilter Pro-G/FabFilter Pro-G.pdf` · deep spec: `easby-programming/plugins/Pro-G.md` (RE'd — black-box measurement, Programmer-only) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A workhorse gate/expander for suppressing noise, reducing bleed, gating before distortion, or enhancing dynamics on drums and busses. Distinct for five meticulously tuned, program-dependent expander/gate algorithms (including an Upward expansion style and a Ducking mode), a clear real-time transfer-curve + input/output level display, adjustable hold and optional look-ahead (pre-open) up to 10 ms, mid/side processing, up to 4× linear-phase oversampling, and an Expert mode with steep 48 dB/oct side-chain filtering plus fully flexible per-channel side-chain linking and wet/dry control.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Threshold** | −60 → 0 dB | Level at which the gate/expander opens. Lower = opens earlier (more passes through). | Primary control; set with the real-time display/metering. |
| **Ratio** | 1:1 → ∞:1 | Amount of expansion below threshold. 4:1 = each dB under threshold → −4 dB reduction. 1:1 = no expansion. >~5:1 acts increasingly like a hard gate. | Low ratios = gentle expansion; high/∞ = full gating. |
| **Range** | 0 → 100 dB (a.k.a. *floor*) | Max expansion/attenuation depth. e.g. 20 dB caps reduction at −20 dB. | Suppress noise only slightly, or expand a specific part of the dynamic range. |
| **Style** | Classic / Clean / Vocal / Guitar / Upward / Ducking | Selects the gate/expander algorithm (see Notes). All have built-in hysteresis where needed (closes at a slightly lower level than it opens, avoiding flutter). | Pick by source — see Notes for each. |
| **Attack** | 0 ms → 1 s | Speed the gate/expander opens when signal exceeds threshold. Program-dependent; very fast times available. | Fast for transient-rich drums (preserve punch); slower for smooth sources. |
| **Release** | 0 ms → 5 s | Time to close and reach max gain reduction. Program-dependent. | Short = tight gating; long = natural decays / pumping. |
| **Hold** | 0 → 250 ms | Minimum time the gate stays fully open after signal exceeds threshold. | Prevent chatter/stuttering on sustained or fluttering material. |
| **Knee** | 0 → 30 dB | Soft-knee width; gate reacts more gradually as sound drops below threshold. Visible in the transfer curve. | Smoother, less abrupt gating; 0 = hard onset. |
| **Lookahead** | 0 → 10 ms (a.k.a. *pre-open*) | Opens up to N ms *before* the level actually crosses threshold. | Catch transients without ultra-fast attack (avoids distortion/aliasing). |
| **Lookahead Enabled** | on / off (button at top-right of Lookahead knob) | Toggles look-ahead. Off + OS off = zero latency. On = adds the look-ahead latency (plus a little if OS on). | Disable for zero-latency tracking; enable for transient accuracy. |
| **Side Chain — In / Ext** | In / Ext (Expert mode) | In = detector keys off the plug-in's own input. Ext = keys off an external track routed from the host. | Ext for ducking under a voice-over, or keying a gate from another source. |
| **Audition** | button (Expert mode) | Monitors the (filtered) side-chain/trigger signal so you can hear exactly what's driving detection. | Dialling in the SC filters or external key. |
| **SC High-pass / Low-pass** | steep 48 dB/oct, draggable; bypass at far left/right (Expert) | Narrows the frequency range the detector triggers on. Drag both at once via the highlighted band or Alt/Opt. | Stop the gate triggering on rumble/cymbals; key only on the snare's body, etc. |
| **Gain L / Gain R** (inner knobs) | ±36 dB (Expert) | Volume of signal fed into each channel's level detector. Sets how hard the trigger hits per side. | Bias detection toward one channel; tune sensitivity. |
| **Mix L / Mix R** (pan rings) | L OFF … center … R OFF (Expert) | Source of each channel's trigger signal (where it's coming from L↔R). Both centered = fully stereo-linked; hard-panned per side = fully unlinked. In Mid/Side mode, pans between mid and side. | Stereo-link vs. unlink the side-chain; cross-link or key on mid/side only. |
| **Wet** | combined knob + pan ring, level ±, L OFF…R (Expert) | Level/pan of the processed (gated/expanded) signal. | "Dilute" the gating effect; parallel-style blending. |
| **Dry** | combined knob + pan ring, level ±, L OFF…R (Expert) | Level/pan of the unprocessed signal mixed back in. | Blend dry signal under the effect; control panning. |
| **Expert** | on / off (button under display) | Reveals/hides the side-chain + wet/dry section. When off: triggers on main input, fully stereo-linked, no filtering, 100% wet / 0% dry. | Turn on for SC filtering, external key, linking control, wet/dry. |
| **Oversampling** | Off / 2× / 4× (bottom bar) | Internal process runs 2–4× host rate to reduce aliasing from fast open/close. Costs CPU + small latency. | Fast attack/release with high ratio + range; quality-critical work. |
| **Channel Mode** | Left/Right / Mid/Side (bottom bar) | Process as L/R or as Mid/Side (mid→internal L, side→internal R). | Gate/expand mid and side independently; key on mono only, etc. |
| **Bypass (Global Bypass)** | on / off (bottom bar) | Latency-compensated soft bypass of the whole plug-in (no clicks). | True A/B against the unprocessed track. |
| **Input level** | gain (bottom bar, drag vertically) | Stereo level before processing. | Drive the detector/threshold relationship. |
| **Output level** | gain (bottom bar, drag vertically) | Stereo level after processing. | Make-up / final trim. |
| **MIDI trigger** | Note On (via MIDI Learn routing) | A held MIDI note forces the gate fully open (acts as if 0 dB enters the side chain). Disable/Enable MIDI in the MIDI Learn menu. | Rhythmic/manual gating; trigger-gating from MIDI. |
| **MIDI Learn** | — | Associate any MIDI controller with any parameter; Enable/Clear/Revert/Save in its menu. | Hardware control / automation. |
| **A/B + Copy** | — | Switch between two full states; Copy clones active state to the inactive one. | Compare two settings. |
| **Undo / Redo** | — | Step through the plug-in's own edit history (UI changes only; not MIDI/automation). | Roll back tweaks. |

## Use by lens
- **Producer (create):** Reach for character and rhythm. Use **Classic** on drums for vintage-strip gating, **Guitar** before an amp/distortion (low 2:1–5:1 ratios) to kill rumble while keeping natural decay, and **Ducking** (with external side-chain key) for the classic side-chain "pumping" effect or to duck a music bed under a voice. MIDI-note triggering and look-ahead make tight rhythmic gates easy.
- **Mixing (balance):** The everyday job — tighten drums (Attack fast, short Hold/Release, set Range so spill drops but doesn't fully cut), clean vocals/dialogue with the **Vocal** style (gentle, breath-aware) or **Clean** for transparency, and gate bleed off close mics. Use the **SC high-/low-pass** to trigger only on the wanted source, and Mid/Side or per-channel **Mix** linking to gate a stereo source without image wander.
- **Mastering (finalize):** Gates are rare on a master, but **Upward** expansion (separate Threshold/Ratio, smaller ranges) can subtly restore macro-dynamics or lift the loud parts on an over-compressed mix — use moderate ratios and avoid high ratio + low threshold (extreme amplification). Mid/Side lets you gently expand only the side/stereo information. Enable **oversampling** and **look-ahead** for cleanliness; blend with **Wet/Dry** for a light touch.

## Notes / gotchas
- **Styles:** *Classic* — vintage strip flavor, aggressive or subtle, great all-rounder on drums. *Clean* — minimal flutter/distortion, most transparent. *Vocal* — gates gently on breaths, releases gently but fast enough to cut noise/bleed. *Guitar* — follows the guitar's natural decay (best at 2:1–5:1) so it stays lively even after distortion. *Upward* — amplifies signals **above** threshold instead of reducing below it; uses its own smaller-range Threshold/Ratio. *Ducking* — inverted gate: lowers level above threshold (voice-over ducking, pumping).
- **Hysteresis** is built into all styles where needed: it closes at a slightly lower threshold than it opens, preventing chatter around the threshold.
- **MIDI fully opens the gate:** any held note acts like a 0 dB side-chain signal → the gate is fully triggered. Turn this off via *Disable MIDI* in the MIDI Learn menu if you don't want it.
- **Expert-off defaults:** triggers on main input, 100% stereo-linked, no SC filtering, 100% wet / 0% dry. SC filters bypass at the far edges of their range.
- **Latency:** zero when look-ahead and oversampling are both off. Look-ahead adds its set time; oversampling adds a small extra amount. (Measured PDC: ~441 smp lookahead, +62/+68 smp for OS — see deep spec.)
- **Metering:** real-time display shows output (light blue) over input (dark blue) on a fixed 60 dB scale, with the transfer curve overlaid; the dB read-out above the meter is resettable by clicking. Clipping indication is informational — audio is **not** clipped inside Pro-G.
- **Resize/scaling:** Small/Medium/Large/Extra-Large + custom scaling; Full-Screen mode for precise work.

## Deep spec (Programmer only)
`/Users/pongsathonkheeereekaew/.claude/skills/easby/easby-programming/plugins/Pro-G.md` — black-box measured (no disasm): pure time-varying gain (harmonics < −160 dBc), downward-expander law `gain_dB = (R−1)·(in_dB − thr_dB)` clamped to −range, Giannoulis soft knee (width = knee), upward/ducking laws, dB-domain attack/hold/release smoother, SC HP/LP act on detector only.
