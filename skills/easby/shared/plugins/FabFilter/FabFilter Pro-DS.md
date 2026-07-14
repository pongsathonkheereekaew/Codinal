# FabFilter Pro-DS — FabFilter (de-esser)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-DS (v1.x) |
| Type | De-esser / frequency-selective dynamics (also usable as HF limiter) |
| Format | VST, VST3, CLAP, AU (macOS), AAX Native, AudioSuite |
| Source | manual: `FabFilter Pro-DS/FabFilter Pro-DS.pdf` · deep spec: `easby-programming/plugins/Pro-DS.md` (reverse-engineered) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Pro-DS tames over-sibilant vocals and harsh high frequencies. A tunable band-pass sidechain detector watches a chosen frequency range (the "s"/"t" region, typically 8–10 kHz) and applies program-dependent gain reduction when that band crosses the threshold. Its standout feature is the **Single Vocal** detection algorithm, which intelligently separates sibilance from non-sibilance for transparent, surgical de-essing of voices. Switched to **Allround** mode it becomes a general high-frequency limiter for drums, full mixes, or any bright material. Wide-band vs split-band processing, lookahead, mid/side handling, and up to 4× linear-phase oversampling round it out.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Threshold | −∞ … 0 dB | Sidechain level above which de-essing triggers. Circular meter around the knob shows the filtered (and stereo-linked) detection level. | Lower until sibilance is caught without grabbing non-"s" sounds. In Single Vocal you can go to −∞ to reduce all sibilance by a roughly constant amount (set by Range). |
| Range | 0 … 24 dB | Caps/scales the maximum gain reduction applied — i.e. the depth of de-essing. | Set how hard the "s" is pulled down. Bigger = more aggressive. |
| HP slider (sidechain) | 2 kHz … 20 kHz | High-pass corner of the detection band — sets the lower edge of the triggering range. | Move up to zoom in on just the harsh sibilance; in Split Band it also sets the split point. |
| LP slider (sidechain) | 2 kHz … 20 kHz | Low-pass corner of the detection band — upper edge of the triggering range. | Narrow the band down to the offending frequencies. Built-in spectrum analyzer lights up strong frequencies to guide placement. |
| Audition Sidechain | button (under HP/LP) | Solos the filtered detection signal so you hear exactly what the detector hears. | While tuning HP/LP to find the exact "s" frequency; also reveals effect of stereo link / mid-side. |
| Audition Triggering | button (top-left of Threshold) | Plays only the parts being acted on and how much de-essing is happening (the "removed" signal). | To confirm you're catching all sibilance and nothing else; pair with Lookahead tuning. |
| Mode: Single Vocal / Allround | 2-state | **Single Vocal** = intelligent sibilance-vs-tone detection for one vocal. **Allround** = trigger purely on band + threshold, for full mixes/drums/mastering. | Single Vocal for solo voices; Allround for buses, mixes, HF limiting. |
| Processing: Wide Band / Split Band | 2-state | **Wide Band** ducks the whole signal by the gain reduction (keyed by HF). **Split Band** attenuates only the high band (split set automatically by the HP sidechain freq), low band passes untouched. | Wide Band often best/most natural on single vocals; Split Band for full mixes/complex audio and mastering HF-limiting. Note: Split Band adds latency. |
| Side Chain: In / Ext | 2-state | Detector source = internal (the track itself) or external sidechain input. | Use Ext to key from a clean vocal when the main signal is heavily processed/distorted, for better detection. |
| Stereo Link | 0% … 100%, then Mid-/Side-only | 0% = channels de-essed independently; 100% = identical gain reduction both channels. Turning past 100% processes only the Mid (mono) or only the Side (stereo) content. | Raise for cohesive stereo de-essing. Mid-only leaves stereo content untouched (center lead vocal); Side-only leaves mono/center untouched (de-ess panned backing vox). |
| Stereo Link Mode (Mid / Side) | menu (small btn at knob's bottom-right) | Chooses whether the >100% region targets Mid or Side signal. Stereo version only. | Pick Mid vs Side target for the mid/side-only de-essing above. |
| Lookahead time | 0 … 15 ms | Starts de-essing up to 15 ms before the level actually crosses threshold — catches transients / the very start of sibilance. ~10 ms is often ideal. | Turn up when initial "s" transients slip through; back off to keep a natural s-sound. |
| Lookahead Enabled | on/off (top-right of Lookahead knob) | Toggles lookahead. When on, latency = 15 ms (+ small extra if oversampling/split-band). When off + Wide Band + oversampling off, plug-in is zero-latency. | Disable for live/zero-latency tracking. |
| Oversampling | Off / 2× / 4× | Runs internal processing at 2–4× host rate to reduce aliasing from the fast gain changes de-essing makes. Linear-phase. | Turn up when triggering often or using high Range, where aliasing/distortion appears. Costs CPU + a little latency. |
| Input gain / pan | dB (bottom bar) | Level/pan into the de-essing process (before detection). | Drive the detector hotter/colder; double-click to type. |
| Output gain / pan | dB (bottom bar) | Final level/pan after processing. | Make-up / trim. Linked with input (Alt-drag) for level-matched A/B. |
| Global Bypass | on/off (bottom bar) | Latency-compensated, click-free soft bypass of the whole plug-in (display dims, red light). | True A/B without level/timing jumps. |

## Use by lens
- **Producer (create):** Drop on a tracked vocal in **Single Vocal / Wide Band**, hit Audition Sidechain to park the HP/LP over the harsh "s" (~6–10 kHz), then lower Threshold while watching the ring meter and set Range to taste. Keep Lookahead off for zero-latency monitoring while recording; flip it on at mix.
- **Mixing (balance):** Single Vocal on lead/backing vox; use Mid-only or Side-only stereo modes to de-ess panned doubles without touching the centered lead (or vice versa). For a heavily distorted/processed vocal, feed the clean vocal via Side Chain → Ext so detection stays accurate. Tighten HP/LP to surgically target only the sibilance.
- **Mastering (finalize):** **Allround + Split Band** as a high-frequency limiter — clamp transients in the top band, then optionally lift that same range back with a high shelf (e.g. Pro-Q) to brighten while gluing. Raise Oversampling to keep it clean; mind the added latency.

## Notes / gotchas
- **Two independent mode pairs:** Single Vocal/Allround (detection intelligence) is separate from Wide Band/Split Band (audio path). Mix freely.
- **Latency:** zero-latency only when Lookahead off + Wide Band + Oversampling off. Lookahead = 15 ms; Split Band and Oversampling each add a little more.
- **No clip on output by itself** — meter clip indicators (red) are informational, mainly for hosts that clamp at 0 dBFS (e.g. Pro Tools HD). Click the meter/read-out to reset peak hold.
- **Detection is band-filtered peak**, not RMS; the circular meter and spectrum analyzer both reflect the *post-filter* sidechain, so what you see is what triggers.
- **MIDI Learn** on every param; external sidechain routing differs per host (see manual for Pro Tools / Logic / Live / Cubase specifics — in Logic, External SC and AU-MIDI-controlled instancing are mutually exclusive).
- Resizable (Small/Medium/Large/XL) + Full Screen + interface scaling; VST3 supports free window-edge resizing.

## Deep spec (Programmer only)
`/Users/pongsathonkheeereekaew/.claude/skills/easby/easby-programming/plugins/Pro-DS.md` (reverse-engineered — measured DSP: band-pass detector ≈12 dB/oct, ratio ≈2.5:1, fixed attack τ≈10.6 ms / release ≈22 ms, stereo-link & mid/side crossfade behaviour). That layer is RE/measured and is **not** part of this CLEAN card.
