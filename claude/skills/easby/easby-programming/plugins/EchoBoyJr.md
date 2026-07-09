# EchoBoy Jr. — Soundtoys (delay / simplified single echo)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Delay — simplified single-echo subset of EchoBoy (tape/analog/lo-fi styles, one delay line) |
| Tech | C++ VST3, shared "Soundtoys" static framework (one plugin per process). AAX = PACE; VST3 = pedalboard-hostable |
| Binary | universal (x86_64 + arm64) MH_BUNDLE, 37.8 MB; not measured statically (CLEAN-only task) |
| Provenance | **CLEAN** — black-box measurement (pedalboard). Decoded as an EchoBoy subset; shared-engine facts inherited (tagged). |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/delay_probe.py`, `out/EchoBoyJr_*.json`) |

## Signal chain
```
x → inputgain → [single delay line: Normal / Wide / Ping-Pong]
                  time → STYLE colour model (sat + HF/LF + mod) → feedback (×g, in-loop)
              → lowcut / highcut → wet
   x (dry) ───────────────────────────────────────────────────────→ ┐
   wet ──────────────────────────────────────────────────────────────┴─ mix → outputgain → y
```
Same engine as EchoBoy but **one echo generator**, fewer styles, no Dual/Rhythm/groove/feel/prime. Adds a `glide` toggle (smooth vs stepped delay-time change).

## Per-stage formula (tag each CLEAN / REF)
- **Delay time → actual** (CLEAN): `echotime_msec` (echomode = Time) is **linear / true-ms** across the range. Measured: 50 ms→49.9, 234.4→234.3, 500→500.7, 1875→1874.9, 6328→6328.0, 15000→14999.8 — ratio ≈ 1.00 throughout (cleaner than EchoBoy even at short times). PDC latency = **32 samples**.
- **Feedback** (CLEAN behaviour partly host-limited): identical engine to EchoBoy → expect the same loop-gain law (g<1 to ~1.0, self-osc ≳1.10) and in-loop tape compression. **In pedalboard the `feedback` write did not recirculate** (single echo for fb 0→1.0; the param string updated 0.00→1.00 but no decaying tail/extra taps appeared). This matches the host-restart limitation also seen on EchoBoy's `style` (below). **Feedback decay law for ES-L = take it from EchoBoy** (shared framework, same 0–1.25 range). Mark Jr's own feedback **unmeasured in pedalboard** (needs REAPER, where the param-commit happens host-side).
- **Style models** (CLEAN list; per-style fingerprint unmeasured): `style` = **7** entries — Studio Tape, EchoPlex, Space Echo, Cheap Tape, Memory Man, Ambient, Transmitter (a curated subset of EchoBoy's 28). Only **Studio Tape** (boot default) is measurable in pedalboard; selecting another style **mutes the wet path** here (same host-restart issue as EchoBoy). Studio-Tape colour = inherit EchoBoy's measured numbers (saturation odd-harmonic, gentle HF/LF cuts, accumulating wow/flutter).
- **mode** (CLEAN): Normal (mono echo), **Wide** (default — splits the single echo into a slightly offset stereo pair, measured taps at 145.9 + 153.9 ms ≈ ±4 ms L/R for a 150 ms set → ~8 ms inter-channel offset = Haas widening), Ping-Pong (bounces repeats L↔R).
- **glide** (CLEAN, param): On (default) = delay time ramps smoothly when changed (tape-style pitch-bend "glide"); Off = stepped. Audible-design control inherited from tape transport behaviour.

## Why / design rationale (music ↔ code)
- **One-echo simplification with curated 7 styles** → fewer decisions, fast results → the "Jr." is the get-a-good-tape-echo-in-two-knobs version of EchoBoy; same colour engine, smaller surface.
- **Wide mode = micro-offset stereo (Haas)** → instant stereo width from a mono source without a true second delay → the ~8 ms L/R offset reads as space, not as a discrete second tap.
- **Glide toggle** → emulates moving the tape-head/changing delay on the fly → the signature pitch-slide when sweeping delay time, switchable for clean digital-style time changes.
- Same in-loop tape saturation + HF roll + wow/flutter rationale as EchoBoy → repeats darken, warm, and wobble as they regenerate.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| inputgain_db | dB | −24…+24 | |
| outputgain_db | dB | −24…+24 | |
| mix | % | 0…100 | default 40 |
| mode | enum | Normal, Wide, Ping-Pong | default Wide; Wide = ~8 ms Haas stereo split |
| style | enum | Studio Tape, EchoPlex, Space Echo, Cheap Tape, Memory Man, Ambient, Transmitter | only Studio Tape measurable in pedalboard |
| glide | bool | Off/On | default On; smooth (pitch-glide) vs stepped time change |
| echomode | enum | Time, Note, Dotted, Triplet, Beats | only Time measurable (no host transport) |
| echonote | enum | 1/1…1/64 + trip/dot | sync note (tempo-sync: unmeasured) |
| echotime_msec | ms | 0…15000 | linear true-ms delay |
| feedback | ratio | 0…1.25 | regeneration (law per EchoBoy; inert in pedalboard) |
| saturation_db | dB | 0…24 | in-loop drive (odd-harmonic, per EchoBoy) |
| lowcut | norm | 0…1 | wet HP, gentle |
| highcut | norm | 0…1 | wet LP, gentle (default fully open) |

## CLEAN measurements
- Delay-time map: linear true-ms (ratio ≈ 1.00, 50 ms–15 s); PDC 32 samp.
- Wide mode: 150 ms set → L/R taps 145.9 / 153.9 ms (~8 ms Haas offset).
- Feedback & per-style colour: **inherited from EchoBoy** (shared engine); Jr's own feedback inert in pedalboard.

## To implement (CLEAN-only)
- Reuse the **EchoBoy building blocks** (fractional delay, in-loop soft-sat + 1-pole HP/LP, feedback law, wow/flutter) with a single echo generator.
- **Wide** = duplicate the echo to L/R with a small (~8 ms) inter-channel time offset (Haas).
- **glide** = slew the delay-time target (one-pole ramp) when On; jump when Off.
- 7 style presets = a curated subset of the EchoBoy (sat, HF, LF, mod) tuples.
- tempo-sync = host-BPM × note; **unmeasured (needs REAPER transport)**.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). Feedback law & per-style colour inherited from EchoBoy (shared Soundtoys engine; reproduce black-box before shipping). **REF** = none.
