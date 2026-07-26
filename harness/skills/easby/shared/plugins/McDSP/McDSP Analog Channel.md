# McDSP Analog Channel — McDSP (saturation / tape & channel-amp emulation)

| | |
|---|---|
| Vendor / ver | McDSP · v7 (manual ©2022) |
| Type | Saturation / harmonic — two configs: AC101 analog channel-amp (soft-limit/compress + saturation), AC202 analog tape-machine emulator |
| Format | AAX Native/DSP, AU, VST3 (Mac Intel + Apple silicon; VENUE S6L on HD). VST removed as of v7.0. |
| Source | manual: `McDSP Analog Channel/McDSP Analog Channel.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Analog Channel adds "analog" weight to digital tracks via two separate plug-ins. **AC101** is a fully adjustable analog channel-amplifier / Class-A pre-amp: instead of letting peaks hit digital 0 dBFS and clip, it gently soft-limits/compresses and saturates the signal — a *threshold-less* compressor with adjustable saturation curve, attack, and release. It's extremely CPU-light (≈one per track). **AC202** emulates high-end analog tape machines and tape media: bias, playback speed (7.5/15/30 ips), IEC1/IEC2 EQ, vintage vs modern tape formulations, plus several modeled playback-head types — and goes *beyond* real machines by making low-frequency roll-off and head bump fully independent of tape speed, and by exposing the tape-saturation recovery (release) time. Both are zero-latency (native; 16-sample delay only on AAX DSP/HDX) and double-precision.

## Controls (every param → musical effect)

### AC101 — Analog Channel (channel-amp / saturator)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Input | −24 to +24 dB | Input gain before processing — drives how hard the amp model is hit | Set first; push to make saturation/limiting more audible without clipping (saturation region ≈ −9…0 dB) |
| Drive | −12 to +12 dB | After input is set, scales how "hot" the channel runs into the saturation algorithm. <0 dB = less comp/saturation, >0 dB = more | Primary "amount of analog" knob; ride it watching the 3-state LED |
| Curve (Comp / Saturation) | 1 to 10 (linear → non-linear/analog) | Shape/aggressiveness of the soft-limit (saturation) transfer curve. Higher = more extreme compression + more harmonic distortion; can effectively go negative for extra headroom/"bend" | Low for clean glue; high for obvious tape/tube grit |
| Attack | 0.03–10.0 ms (spec lists 0.1–10) | How fast the saturation/comp curve engages as level rises. Min 0.03 ms = 1 sample (catch every peak) | Fast to catch clicks/digital clips; ~1–3 ms to avoid "bass-buzz" on lows |
| Release | 10.0–1000.0 ms | How fast the effect un-applies as level falls; high end disables the effect | 300–600 ms ≈ natural; <100 ms can pump/distort; >600 ms = unobtrusive glue |
| Output | −24 to +24 dB | Make-up gain on output (disabled when Auto is on) | Match level after driving the input hard |
| Auto (Auto Output) | on / off | Auto-trims output for near-constant level as Input/Drive change. Input must sit at/near 0 dB to track correctly | Quick A/B without level bias; leave off when you want manual control |
| Ø (Phase) | on / off | Inverts polarity of final output (yellow LED = 180°) | Phase-match against a parallel/dry path |
| VA (Virtual Analog meter) | toggle | Switches metering ballistics between original tube-style meters and a VU-style meter (modern productions); +3 dBfs peak shown | Cosmetic/metering preference |
| Saturation-state LED | green / yellow / orange | Real-time readout: **green** = linear (clean), **yellow** = soft limiting, **orange** = hard limiting/saturation | "How hard am I hitting it" gauge — aim for yellow flickering on peaks |
| Input / Gain-Reduction / Output meters | — | Continuous I/O + GR metering; peak LEDs warn of clipping | Watch GR + output-clip LED while driving |

### AC202 — Analog Tape Machine emulator
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Input | −24 to +24 dB | Input gain into the tape-saturation stage; tape formulations clip ≈ −4 dB (vintage) / −12 dB (modern), so input is how you reach saturation | Push to drive tape compression/saturation |
| Output | −24 to +24 dB | Output trim (disabled when Auto is on) | Bring level back after driving the tape |
| Auto (Auto Output) | on / off | Auto-maintains constant output for given Input/Bias settings (disables Output knob); needs input ≈ 0 dB | Level-matched auditioning of tape effect |
| Roll Off | 20–100 Hz | Low-frequency roll-off corner — *independent of tape speed* (real machines tie this to speed). Cuts below the set freq | Tame sub rumble; dial LF weight vs the 15-vs-30 ips trade-off, your choice |
| Bump (Head Bump) | 0–100 % (up to +6 dB) | Amount of low-frequency head-bump resonance, *independent of speed* | Add tape low-end "thump"; on drums ~6 dB bump + Freq sweep to fatten kick |
| Playback Head Type | menu (USA-A, USA-M, Swiss, Japan-O, Japan-S, Japan-T, etc.) | Selects modeled head/"ripple" character. Nicknames map to real reproducers: Swiss≈Studer A80, USA-A≈Ampex MM1200, Japan-O≈Otari MX-80, Japan-S≈Sony APR-5000, Japan-T≈"ideal" Tascam | Pick the machine's overshoot/undershoot signature; USA-A & USA-M good for drum bass/snare separation |
| Bias | −12 to +12 dB | Tape biasing. **Under-bias** (<0) = more dynamic range + HF boost; **over-bias** (>0) = less DR, rolled HF, more tape "character"/saturation. Suggested max over-bias: +6…+9 (vintage), +9…+12 (modern) | Core tape-tone control; over-bias for vintage glue, under-bias for open/bright |
| Release | 10 ms – 1.0 s | Rate the model recovers from tape-saturation back to linear (per-machine in reality) | Short = snappier; ≥1.0 s on guitar to avoid pumping |
| Speed | 7.5 / 15 / 30 ips | Playback speed — affects saturation, dynamic range. (LF roll-off decoupled here, unlike real decks.) 15 = warmer/vintage LF, 30 = cleaner highs | 15 for vintage thickness, 30 for hi-fi; 15–30 for most music |
| EQ Type | IEC1 / IEC2 | Tape EQ standard: IEC1 (=IEC/CCIR/DIN, Europe), IEC2 (=NAB, US) — changes the saturation curve character | Flavor choice; IEC2/NAB common for US records |
| Tape (Formulation) | Vintage / Modern | **Modern** = large linear region, big DR, subtle (true-to-source). **Vintage** = smaller DR, more distortion/saturation character (e.g. Ampex 456 vibe) | Vintage for obvious tape color, Modern for clean fattening |
| Input / Gain-Reduction / Output meters | — | Continuous I/O + GR metering; peak-clip LEDs | Use GR meter to see tape compression at work |
| Playback Head & Tape Response display | — (graph) | Real-time: **yellow** curve = playback-head response (roll-off + bump); **dark-green** curve = tape saturation amount vs bias/speed/IEC at high level (>−12 dB) | Visual calibration — no test tones/calibration tapes needed |

## Use by lens
- **Producer (create):** AC101 as a "make it not-digital" insert on any track — push Input/Drive into yellow LEDs for tube/tape grit, high Curve for obvious distortion (guitars, synths, drum bus). AC202 for printed-to-tape vibe: pick a head type, over-bias + Vintage tape for character, 15 ips for thickness. On distorted/clean guitar try USA-M head, 100 Hz roll-off, ~6 dB bump, over-bias at 15 ips, Release ≥1.0 s.
- **Mixing (balance):** AC101 = "Class-A glue" on the mix/group bus or per-channel — set Drive so the middle saturation LED just lights on peaks for transparent leveling; multi-mono on the stereo bus (Console 1/2/3 presets) for subtle stereo-field glue. Also a *threshold-less compressor* for smooth program limiting, and a **digital-clip repair** tool (fastest Attack ≈1 sample to catch each clip, Comp ≥50% of max, vary Release for natural "recovery"). AC202 on drum sub-bus to kill sub-rumble (Roll Off) and separate kick/snare via head-bump Freq.
- **Mastering (finalize):** AC202 on the 2-bus to emulate the classic reel-to-reel master — 20–40% head bump, roll-off 30–60 Hz to keep the kick, 15 or 30 ips, Vintage (Ampex 456-style) or Modern tape, Bias 0…+6 dB (>6 dB usually too much). VU meters: left = output, right = gain reduction. AC101 multi-mono on the master for gentle whole-mix limiting/character.

## Notes / gotchas
- **Two separate plug-ins, not modes:** AC101 (channel amp/comp/saturator) and AC202 (tape machine) instantiate independently. Use AC101→AC202 in series for a full "analog studio" channel.
- **Auto Output disables the Output knob** and only tracks correctly when the input signal is at/near 0 dB.
- **AC101 is threshold-less** — there's no threshold control; "amount" is set entirely by Input + Drive + Curve. It's "always on" (Class-A style).
- **AC202 head-type "nicknames" ≠ trademarks endorsed by those vendors** — they're modeled approximations (Studer/Ampex/Otari/Sony/Tascam/MCI references) measured by engineer Jack Endino.
- **Decoupled LF:** AC202's Roll Off and Bump are independent of Speed (real machines aren't) — a deliberate feature, not a bug.
- **Latency:** zero-latency on AAX Native/AU/VST3; 16-sample delay on AAX DSP (HDX). Very low CPU, esp. AC101.
- **No control linking** between params. All controls fully automatable.
- **Watch output clipping** when using slow attacks / "bent" curves — overshoots can occur.
- Presets named both by machine (Studer/Otari/etc.) and by source (vocal/drums/guitar).

## Deep spec (Programmer only)
not reverse-engineered — capability only.
