# Pro-C 3 — FabFilter (Compressor, multi-style feed-forward)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-C 3 · VST3 (Fx\|Dynamics) · no DRM (no PACE/iLok) |
| Type | **Compressor — feed-forward, multi-style (14)**: downward + upward, opto/vari-mu/VCA emulations, optional character saturation, 6-band sidechain EQ, oversampling, lookahead, M/S stereo-link |
| Tech | VST3 (FabFilter, native Metal/GL UI). C++; no Rust/FFI. |
| Binary | universal Mach-O bundle (x86_64+arm64), **STRIPPED** — exactly 6 ext syms = VST3/AU entry points (`_FFPluginMain _GetPluginFactory _VSTPluginMain _bundleEntry _bundleExit _main_macho`), no PACE/iLok. **Static is a wall → black-box ONLY.** |
| Provenance | **ALL facts CLEAN** (black-box measured). No disasm used. |
| Measured on | Pro-C 3 · SR 96 kHz · pedalboard 0.9.17 · scipy 1.13 · `private-research/Pro-C3/Tools/proc3_sysid.py` · 2026-06-22 (2 passes; detector-law/release-shape/SC-EQ/stereo-matrix/pre-duck added 2026-06-22) |
| Source | `private-research/Pro-C3/` — `Tools/proc3_sysid.py`, `docs/measurements.md` |

## Signal chain (CLEAN behaviour)
```
inL,inR
  → input_level / input_pan
  → [character saturation if routing=Pre]   (Off/Tube/Diode/Bright, ×character_drive)
  → COMPRESSOR core (per style):
       sidechain: internal | external | host-sync | MIDI  → 6-band SC EQ → level detector (RMS-ish)
       gain computer: threshold, ratio (1..100:1), knee(dB width), range(max GR clamp)
       ballistics: attack, release (+ hold, + auto_release adaptive), per-style time/knee shaping
       stereo_link % (+ M/S mode) blends the two-channel detector into a shared gain
  → [character saturation if routing=Post]
  → auto_gain makeup  (≈0.358·|thr|·(1−1/R) dB)
  → mix (scales APPLIED gain-reduction in dB) + dry_gain parallel path
  → wet_gain / wet_pan, output_level / output_pan
  → outL,outR
```
Detector is **RMS-following, feed-forward** — proven decisively (CLEAN, `detlaw`): square vs sine at **equal
peak** → square ducks **+2.21 dB more** (it carries +3.01 dB more RMS); at **equal RMS** the residual collapses
to **+0.80 dB**. Δ≈0 at equal-RMS ⇒ tracks RMS, not instantaneous peak (the +0.8 dB residual = slight peak
bleed typical of FF detectors). Zero measured latency in offline render (see below).

## Per-stage formula (all CLEAN — measured)
- **Gain computer** (CLEAN): displayed **ratio = true ratio** (measured deep above thr: set 4:1→3.91, 8:1→7.64,
  100:1→167:1 ≈ limiting). `knee` dB = total soft-knee width centred on threshold (Giannoulis-style: knee 72
  starts GR ~30 dB below thr; knee 0 = sharp onset exactly at thr). `range` = hard floor on GR (range 24 → GR
  cannot exceed 23.3 dB). Below thr slope = 1.0 exactly.
- **Ballistics** (CLEAN): attack/release are nominal exponential time-constants; measured 90 %-transit ≈ 2–2.3×
  the knob. `auto_release` = adaptive (release longer after sustained GR: 70→111 ms for 20→200 ms bursts);
  even with auto OFF there is mild program dependence (37→83 ms).
- **auto_gain makeup** (CLEAN, recovered law): **makeup_dB ≈ 0.358 · |threshold_dB| · (1 − 1/ratio)** —
  ~36 % of textbook full makeup (conservative; won't over-boost). Fit ~exact over thr∈[−40..−10], R∈[2..6].
- **mix** (CLEAN): NOT a parallel dry/wet sum — it **linearly scales applied gain-reduction in dB**
  (GR_applied = mix · GR_full; mix 50 % gives exactly half the dB of GR). `dry_gain` is the separate genuine
  parallel-dry path.
- **stereo_link %** (CLEAN): blends the shared detector — 0 % independent, 100 % both channels driven by the
  louder/linked GR (R ducks 0→−13→−18→−21→−22.9 dB for link 0/25/50/75/100 % under an L-only burst).
- **character saturation** (CLEAN, see table): Tube = very subtle symmetric (THD 0.36 % only at +24 dB);
  Diode = odd-harmonic soft-clip (H3≫H2, THD→30.7 %); Bright = asymmetric, even-harmonic-rich, aggressive.

## Parameters (105 total; DSP-relevant subset — full dump via `proc3_sysid.py params`)
| param | unit | range | notes |
|---|---|---|---|
| style | enum 14 | Clean, Versatile, Smooth, Punch, Upward, TTM, Op-El, Vari-Mu, Classic, Opto, Vocal, Mastering, Bus, Pumping | sets detector/ballistics/knee/harmonic character; **Upward = upward comp** (boosts quiet, ~no downward GR) |
| threshold | dB | −60..0 | GR onset exactly at this level |
| auto_threshold / lock_auto_threshold | bool | Off/On | auto-set threshold |
| ratio | :1 | 1.00 .. 100:1 (cont.) | label = TRUE ratio; ≈∞/limiting at top |
| knee | dB | 0..72 | total soft-knee width (centred on thr) |
| range | dB | 0..60 | hard max-GR clamp |
| attack | ms | 0.005 .. 250 | exp/log map (see harness table); nominal time-constant |
| release | ms / s | 10 ms .. 2.5 s | exp/log map; ms below ~1 s then "sec" |
| auto_release | bool | Off/On | adaptive program-dependent release |
| hold | ms | 0..500 | GR hold before release |
| lookahead | ms (readout) | [0..0] | display only; **maximum_lookahead** is the control |
| maximum_lookahead | enum | Off / 1 / 2 / 5 / 10 / 20 ms | look-ahead budget (PDC host-dependent; 0 latency offline) |
| character | enum 4 | Off / Tube / Diode / Bright | saturation engine |
| character_routing | enum | Pre / Post Compression | saturate before vs after comp |
| character_drive | dB | −24..+24 | drive into the saturation device |
| wet_gain / dry_gain | dB | −inf..+36 | wet level / **parallel dry** level |
| wet_pan / dry_pan / input_pan / output_pan | M/S+L/R | — | per-path pan (Mid/Side & L/R balance) |
| auto_gain | bool | Off/On | makeup ≈ 0.358·\|thr\|·(1−1/R) dB |
| mix | % | 0..200 | scales applied GR in dB (100 % = full; 200 % = over-compress) |
| input_level / output_level | dB | −inf..+36 | trims |
| stereo_link | % | 0..100 (raw 0..1 == 0..100% linear) | detector link blend (crossfade per-ch gain → shared) |
| stereo_link_mode | enum | **Mid / Side / M→S / S→M** | which M/S component feeds shared detector; **on plain 2.0 stereo all 4 are degenerate** (identical cross-feed measured) — only differentiate on surround layouts (HOST-BLOCKED) |
| stereo_link_center/surrounds/tops/lfe | bool | Excl/Incl | surround channel inclusion in link |
| side_chain_input | enum | Internal / External / Host Sync / MIDI | detector source |
| side_chain_level | dB | −36..36 | SC drive |
| side_chain_eq_band_1..6_* | — | freq **10..30k LOG** (Hz=10·3000^raw), gain ±30, Q .025..40, 10 shapes (below), slopes{6..96 dB/oct,Brickwall} | 6-band detector EQ; `_used` flag (not just `_enabled`) gates a band; shape responses mapped via `sceq` |
| host_trigger_sync/offset/length | enum/% | Whole..1/16 Note / 50..200 % / 0..100 % | tempo-synced gate trigger (**HOST-BLOCKED** — needs transport) |
| audition_side_chain / audition_triggering | bool | Off/On | monitor SC |
| oversampling | enum | Off / 2 / 4 / 8 / 16 / 32× | engages (alters signal) but 0 offline latency |
| bypass / host_bypass | bool | — | |

Enum raw→label map, full 105-param table, and attack/release raw→ms tables: `docs/measurements.md`.

## CLEAN measurements (headline tables; full set in docs/measurements.md)
- **Static IO** (Clean 4:1 thr −30 knee 0): −60..−30 → GR 0; −12 → −11.4; 0 dBFS → −20.3 dB GR.
- **Effective ratio = label** (deep above thr): 2→1.98, 4→3.91, 8→7.64, 100→167:1.
- **14-style fingerprint** (GR@0dBFS · atk · rel · H3 · H2): Clean −20.9/3/212/−58/floor; Vocal −29.9/6/247/−97/−141
  (deepest, softest knee); Upward −1.8 (upward!); Vari-Mu −15.3 (strongest H3 −43); Mastering/Pumping ultra-clean.
- **character**: Tube THD 0.36 % (subtle, symmetric) · Diode 30.7 % (odd, H3≫H2) · Bright 16.1 % (even/asym).
- **auto_gain**: 0.358·|thr|·(1−1/R) dB. **mix**: scales GR in dB (not parallel sum). **stereo_link**: detector blend.
- **latency**: 0 samples for all OS & lookahead in offline pedalboard render (host-PDC not exposed offline).

## Resolved deep-dives (CLEAN — 2026-06-22 pass 2)
1. **Detector law = RMS** (`detlaw`). Sine vs square: equal-PEAK Δ=**+2.21 dB** (square ducks more, it has +3.01 dB
   RMS); equal-RMS Δ=**+0.80 dB** (≈0). ⇒ tracks RMS; small +0.8 dB peak bleed. Build: RMS/level detector,
   not a peak follower.
2. **Per-style release pole shape** (`relcurve`, loud→quiet step, de-spiked recovery ladder vs an ideal
   single-pole of the same t63; `early_dev` = mean pp below ideal over first 20 ms):
   | style | t63 ms | %recovered @[5 10 20 40 80 160 320] ms | early_dev | shape |
   |---|---|---|---|---|
   | Clean | 81 | 2 / 9 / 20 / 39 / 63 / 85 / 96 | −2.9 pp | **single 1-pole** |
   | Upward | 270 | 0 / 0.3 / 4 / 11 / 23 / 43 / 70 | −2.8 pp | **single 1-pole** (long) |
   | Opto | 125 | 1 / 4 / 10 / 22 / 44 / 76 / 100 | −3.7 pp | **mild program-dep** (S-curve) |
   | Pumping | 169 | 0 / 0.2 / 1 / 6 / 20 / 59 / 100 | −6.1 pp | **program-dep / 2-stage** (slow→fast) |
   ⇒ default styles ≈ single one-pole; Opto adds mild program-dependence; **Pumping is the strongest convex
   (hold-then-release) shape**. `auto_release` ON deepens this further (prior pass: 70→111 ms spread).
3. **SC-EQ shape→response map** (`sceq`, through-comp in LINEAR 2:1 region, GR_delta/0.5 = EQ dB; freq is
   LOG: Hz=10·3000^raw). All 10 shapes map to textbook filters — band1 @1k Q2 +6 dB / 0 dB:
   Bell = symmetric peak @fc; LowShelf = +6 below ~125 Hz→0 by 5k; HiShelf = mirror; **LowCut = HPF on the
   detector** (−∞ below fc, passes above); HiCut = LPF; Notch = deep band reject; BandPass = pass only near fc;
   TiltShelf = ±6 lo/hi pivot @fc; FlatTilt = gentle constant-slope tilt; AllPass = flat magnitude. Corner
   tracks fc; skirt tracks Q. Detector "hears" the EQ'd side-chain: boost⇒more GR, cut⇒less.
4. **stereo_link cross-feed matrix** (`stereomatrix`, decorrelated L=1k burst / R=1.3k probe). Mode-independent
   on stereo; link % sets coupling: L_duck / R_duck = **0%: −22.9 / 0 · 25%: −18.3 / −10.5 · 50%: −14.8 / −14.8
   · 75%: −5.8 / −5.8 · 100%: −3.2 / −3.1**. ⇒ crossfade each channel's gain toward a shared (averaged) gain
   by link %. All 4 M/S modes identical on 2.0 stereo (degenerate; differ only on surround).
5. **True lookahead pre-duck = NONE offline** (`lookahead`). At max_LA Off..20 ms: pre-duck −0.01 dB,
   begins=nan, **peak-shift = 0 samples**, reported latency 0. ⇒ pedalboard's offline path does not negotiate
   PDC, so the look-ahead delay line is bypassed — no pre-attenuation realizable offline. **HOST-BLOCKED**
   (real pre-duck needs a DAW honoring PDC).

## HOST-BLOCKED (documented from enums; no fabricated numbers)
- **stereo_link_mode M/S differentiation** — `HOST-BLOCKED: needs surround bus`. Mid/Side/M→S/S→M only diverge
  on multichannel layouts (+ `stereo_link_center/surrounds/tops/lfe` inclusion flags); on 2.0 stereo all
  measured identical (matrix in §4).
- **external side-chain** (`side_chain_input=External`) — `HOST-BLOCKED: needs 2nd audio bus`. Uses the **same
  RMS detector law (§1)**, just sourced from the external bus instead of the internal program; SC-EQ + level
  apply identically.
- **host-sync / MIDI trigger** (`side_chain_input=Host Sync|MIDI`, `host_trigger_*`) — `HOST-BLOCKED: needs
  transport/MIDI`. Deterministic semantics: `host_trigger_sync` = gate PERIOD as a note value vs host tempo
  (Whole/½/¼/⅛/1/16); `host_trigger_offset` 50..200 % = gate phase/position within the bar; `host_trigger_length`
  0..100 % = gate-open DUTY of that period. Internal detector still RMS; trigger only re-keys when the gate opens.

## To implement (CLEAN path for product — ES-L)
Feed-forward, log-domain compressor — build entirely from these CLEAN measurements + public literature:
- **Gain computer**: Giannoulis, Massberg & Reiss, *"Digital Dynamic Range Compressor Design — A Tutorial and
  Analysis"*, JAES 60(6), 2012 — soft-knee piecewise (their eq. 4) with `knee` dB = full width; match the
  measured IO/ratio/knee tables. `range` = clamp GR ≤ range. Detector = smoothed level/RMS (not peak).
- **Ballistics**: branching peak/RMS detector with separate attack/release one-poles (Zölzer, *DAFX* 2nd ed.,
  dynamics ch.); map knob→τ from the measured raw→ms tables. `auto_release` = 2-stage / level-adaptive release
  (longer τ for sustained GR) to reproduce the 20 ms→200 ms burst spread.
- **Per-style voicing** (own): pick detector type (peak vs RMS), attack/release scaling, knee width, and a
  light static nonlinearity to hit each style's measured (atk, rel, H2/H3, knee, GR-depth) row — Upward style =
  invert the gain computer (boost below thr). All targets are CLEAN tables above.
- **character**: input-level-keyed soft clipper per mode — Tube = gentle symmetric `tanh`; Diode = odd-only
  diode soft-clip (match H3 ladder); Bright = asymmetric shaper for even harmonics. Oversample ≥ 8× + antiderivative
  anti-aliasing (Zölzer DAFX; Yeh/Pakarinen VA clipper). Pre/Post routing = order vs the compressor.
- **auto_gain** = 0.358·|thr|·(1−1/R) dB (recovered constant). **mix** = scale applied GR-in-dB (not a wet/dry
  buffer sum). **stereo_link** = crossfade each channel's gain toward a shared (averaged) gain by link %
  (measured matrix in Resolved §4; mode-independent on stereo). **detector = RMS** (Resolved §1).
- **SC-EQ**: 6 bands feeding the RMS detector; freq LOG (Hz=10·3000^raw); 10 shapes = standard biquad family
  (Resolved §3) — Bell/shelves/cuts/notch/bandpass/tilt/allpass. Build the side-chain EQ from RBJ cookbook
  biquads, place it pre-detector. **release** = per-style 1-pole, with a 2-stage / program-dependent option for
  Opto/Pumping-type voicings (Resolved §2). **lookahead** = delay-line + pre-duck (host-PDC; not exercised offline).
- Re-measure / null against `Tools/proc3_sysid.py`. Build only from the CLEAN path above + public DSP; never reference the quarantine folder from product code.

## Topology (REF — reference only, do NOT ship-cite; coeffs in quarantine)
Ghidra exact-mode pass done 2026-06-22 (arm64 VST3 thin, imageBase=0x0). RTTI intact → full
`ProCCompressor` / `TransferCurveProcessor` / `Detector` / `CharacterSaturator` class graph + 14-style
`CompressorStyle` enum recovered. Realtime gain math (NEON-density hot zone) decompiled by address.
Exact gain computer (REF) = **dB/log2-domain feed-forward with a soft (Giannoulis) knee**: Cephes
`logf`→dB converter is *byte-identical to Pro-L 2*; compressor adds the inverse Cephes `expf`/`exp2`
= `10^(GR/20)` linear gain; `Character` = a separate Cephes-`atanf` (+ Tube/Triode/DivAbs/… family)
parametric-bias waveshaper. Soft-knee spline, ratio mapping `(1/R−1)`, and all coeff ladders are
quarantined in `_quarantine_disasm/Pro-C3/` (REF). NOTE: the CLEAN-measured auto-gain makeup constant
was NOT found inline in the audio kernel (computed in the param layer) — REF inconclusive there.

---
Provenance tags: **CLEAN** = black-box measurement (`proc3_sysid.py`) / public DSP / own voicing (product-safe).
**REF** = Ghidra static decompile, quarantined in `_quarantine_disasm/Pro-C3/` — reference/education only,
EULA clean-room, NEVER cited from product/ES-L/BuildSpec or any CLEAN section above.
