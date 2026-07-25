# Pro-DS — FabFilter (De-esser)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-DS v1.32 · VST3 (Fx\|Dynamics) · no DRM |
| Type | **De-esser** — frequency-selective downward compressor with a tunable **band-pass sidechain detector**; two audio-path modes: **Wide Band** (broadband ducking keyed by HF) and **Split Band** (only the high band attenuated). Lookahead, 2 voicing modes, oversampling, stereo-link, sidechain audition |
| Tech | VST3 (FabFilter), C++ (FabFilter framework). **Stripped, black-box only** — no symbols to harness |
| Binary | universal Mach-O bundle (x86_64 + arm64), **stripped of fn-name symbols** — 6 ext syms (`_GetPluginFactory _VSTPluginMain _FFPluginMain _bundleEntry _bundleExit _main_macho`); **no PACE/iLok** (otool -L clean). **RTTI/vtables intact** → a static Ghidra pass IS possible (done as REF, quarantined); measurement remains the product route |
| Provenance | The CLEAN spec below = **ALL CLEAN** (black-box `prods_sysid.py`, pedalboard host). A separate **REF** Ghidra pass exists (2026-06-22, quarantined under `_quarantine_disasm/Pro-DS/`) that *corroborates* but is never cited from the CLEAN spec — see "REF note" at the bottom |
| Measured on | Pro-DS v1.32 · SR 48 kHz (+96/192 k for attack) · `private-research/Pro-DS/Tools/prods_sysid.py` (pedalboard; probes: params/detband/curve/times/lookahead + pass-2 attack192/detlaw/stereolink) · 2026-06-22 |
| Source | `private-research/Pro-DS/` — `Tools/prods_sysid.py`, `docs/measurements.md` |

## Signal chain (CLEAN behaviour)
```
in (stereo)
  → [Input gain / pan]
  → split into AUDIO path  ──────────────────────────────────────────────┐
       and DETECTION path:                                                │
         sidechain src = Normal input | External                         │
         → band-pass detector  = 2nd-order HPF (corner=high_pass_freq)    │
                                + 2nd-order LPF (corner=low_pass_freq)    │
                                (≈12 dB/oct each, default 7 k…14 k)       │
         → level detect (PEAK/envelope, not RMS) → static curve:         │
                          threshold, ratio≈2.5:1,                         │
                          knee (Single Vocal=hard / Allround=soft),       │
                          GR clamped to `range` (max attenuation dB)      │
         → ballistics: smooth attack τ≈10.6ms (10→90%≈12.3ms, fixed)     │
                       + ~22 ms release (no user A/R)                     │
         → stereo-link: 0%→100% = indep→common GR; linked detector keys  │
            on Mid=(L+R)/2 or Side=(L−R)/2; ">100% Mid-only" k% =         │
            Mid→Side detector-source crossfade (active only mode=Side)    │
         → lookahead delay (audio path delayed; detector pre-empts) ──────┤
                                                                          ▼
  AUDIO path, two modes:                                       gain reduction g(t) ≤ 0 dB
    • Wide Band : multiply WHOLE signal by g(t)  (broadband duck, keyed by HF)
    • Split Band: split at the detection band; attenuate ONLY the high band by g(t),
                  pass the low band unchanged → recombine
  → [Output gain / pan]  → out
audition_triggering = defeat de-essing / hear signal being acted on (trigger preview)
audition_side_chain = SOLO the band-pass detection signal (monitor what the detector hears)
oversampling (Off/2x/4x) wraps the audio-path filtering; +0/62/68 samp latency
```
Key insight (CLEAN): the detector is a **band-pass-filtered sidechain** (HPF+LPF corners = the two
frequency knobs), NOT a fixed HF shelf. `audition_side_chain` confirms it — soloing the sidechain
kills a 300 Hz tone (−121 dB) and passes only the 9 kHz band. Wide vs Split is the *audio-path action*
(broadband VCA vs split-band attenuation), independent of the (shared) detector.

## Per-stage formula (all CLEAN)
- **Detection band-pass** (CLEAN): 2nd-order HP @ `high_pass_frequency` + 2nd-order LP @ `low_pass_frequency`,
  ≈12 dB/oct skirts, −3 dB points at the knob values. Threshold-crossing trace (HPF7k/LPF14k): passband
  ~9–11 kHz, +3.8 dB @7 k, +3.7 dB @14 k, +8.5 dB @6 k, +14.7 dB @5 k, +34 dB @3 k. Widest (2 k…20 k) is
  flat 2 k→18 k. (See docs for full table.)
- **Static curve** (CLEAN): below threshold → 0 GR. Above → **ratio ≈ 2.5:1** (dOut/dIn = 0.400 in the band),
  GR hard-clamped at `range` dB (range N → max GR exactly −N dB, linear 0/3/6/12/18/24 → 0/−3/−6/−12/−18/−24).
- **Knee** (CLEAN): **Single Vocal** = hard/late (0 GR until ~2 dB above threshold, ~2 dB knee);
  **Allround** = soft (GR begins at threshold, ~4–6 dB knee). Same 2.5:1 slope above the knee.
- **Detector law** (CLEAN): **PEAK / envelope-following, NOT RMS**. Matched-peak sine vs 50%-duty burst →
  equal GR (ΔGR 0.07 dB) despite 3 dB lower burst RMS; matched-RMS → burst gets +1.9 dB more GR (its peak is
  higher). GR tracks peak, not RMS.
- **Ballistics** (CLEAN): smooth attack **10→90% ≈ 12.3 ms, single-pole τ ≈ 10.6 ms** — confirmed a *real*
  fixed time constant (invariant across SR 48/96/192 k, drive, and both modes; NOT resolution-bound, measured
  via Hilbert envelope on a 9 k step @192 k). **release ≈22 ms→90%, ≈34 ms→99%**, smooth/program-dependent.
  No exposed attack/release controls. **Lookahead** pre-empts the ess: with LA on, GR onset at 0 ms, 90% by ~6 ms.
- **Gain application** (CLEAN): Wide Band multiplies the whole signal by g(t); Split Band attenuates only the
  high band. Gain modulation is smooth → **no aliasing > −54 dB even at OS=Off**.

## Parameters (CLEAN — pedalboard param table; enum options self-reported by binary)
| param | unit | range / options | notes |
|---|---|---|---|
| mode | enum | **Single Vocal** \| Allround | voicing/knee: SingleVocal=hard-knee surgical, Allround=soft-knee gentle (defaults identical) |
| band_processing | enum | **Wide Band** \| Split Band | audio-path action: broadband duck vs split-band HF attenuation |
| threshold | dB | −inf … 0 (dflt −36) | de-ess threshold on the detector level |
| range | dB | 0 … 24 (dflt 6) | **max gain reduction** (hard clamp; linear: N dB → −N dB max GR) |
| high_pass_frequency | Hz | 2000 … 20000 (dflt 7000) | detector band-pass **HP corner** (−3 dB), 2nd-order |
| low_pass_frequency | Hz | 2000 … 20000 (dflt 14000) | detector band-pass **LP corner** (−3 dB), 2nd-order |
| lookahead | ms | 0 … 15 (dflt 12) | audio-path delay so detector pre-empts esses |
| lookahead_enabled | bool | dflt **On** | on → reported latency fixed 720 samp = 15 ms @48k (worst-case), regardless of ms |
| stereo_link | enum | **202 vals**: `0%`..`100%` then `100%, k% Mid-only` (k 0..100), dflt 100% | `0%`→`100%` = independent L/R GR → common (linked) GR. The `…Mid-only` half pins link at 100% and (only when mode=Side) crossfades the linked detector's keying from the sum→difference — see stereo_link_mode |
| stereo_link_mode | enum | **Mid** \| Side | the **summing component** that drives the *linked* detector: Mid=(L+R)/2, Side=(L−R)/2 (verified: pure-Mid sig triggers only in Mid domain, pure-Side only in Side). At link `100%` (k=0) both modes key on the sum; the `Mid-only` k% then blends source toward Side under mode=Side (inert under mode=Mid) |
| side_chain_input_signal | enum | **Normal input** \| External | detector source (self vs external sidechain bus) |
| audition_triggering | bool | dflt Off | defeat de-essing / preview the signal being acted on |
| audition_side_chain | bool | dflt Off | **solo the band-pass detection sidechain** (monitor) |
| oversampling | enum | **Off** \| 2x \| 4x | audio-path OS; +0/62/68 samp latency; little aliasing impact |
| input_level | dB | −inf … +36 | input trim |
| input_pan | − | −1 … +1 | input pan |
| output_level | dB | −inf … +36 | output trim |
| output_pan | − | −1 … +1 | output pan |
| bypass / host_bypass | enum | Not Bypassed \| Bypassed | |
| midi_state, internal, midi_cc, pitch_bend, channel_pressure | — | — | MIDI/host plumbing, not DSP |

## CLEAN measurements (headline tables)
**Detection-filter shape (threshold-crossing dBFS, HPF7k/LPF14k, lower=passband):**
3 k −10.1 · 5 k −29.5 · 6 k −35.6 · 7 k −40.3 · 9 k −43.8 · 10 k −44.2 (peak) · 12 k −42.4 · 14 k −40.5 · 16 k −36.5 · 18 k −32.1.
**Static curve:** ratio ≈ **2.5:1**; `range` clamps max GR linearly (0/3/6/12/18/24→0/−3/−6/−12/−18/−24 dB).
**Knee:** SingleVocal hard (onset ~2 dB over thr); Allround soft (onset at thr).
**Two-tone (LF300+HF9k):** Wide → both −22.9 dB (broadband); Split → LF −0.6, HF −19.9 (HF-only).
**Detector law:** **PEAK** — matched-peak sine vs 50%-burst → equal GR (Δ0.07 dB) despite −3 dB burst RMS; matched-RMS → burst +1.9 dB GR. Not RMS.
**Attack:** **10→90% ≈ 12.3 ms, τ≈10.6 ms**, SR-/drive-/mode-invariant (Hilbert @192 k) → real Tc, not sub-ms.
**Stereo-link (decorr L9k/R11k, mode=Mid):** 0%→ΔGR 6.5 dB (indep) · 50%→3.0 · 100%→0 (common GR).
**stereo_link_mode:** linked detector keys on Mid=(L+R)/2 (mode Mid) or Side=(L−R)/2 (mode Side) — corr fires only in Mid, anti only in Side. **">100% Mid-only" k%** (mode=Side only): Mid→Side source crossfade, corr GR −22.6→0 / anti 0→−22.8 as k 0→100 (inert under mode=Mid).
**Latency:** LA-on 720 samp (15 ms); OS +0/62/68.

## FFI contract
None — binary is **stripped** (6 ext syms). No clean C ABI; host-only (pedalboard / VST3). Static is reference-blocked by design.

## To implement (CLEAN path for product — ES-L)
De-esser = **band-pass-keyed downward compressor** with selectable broadband vs split-band action:
- **Detector**: 2nd-order Butterworth HP+LP band-pass on the sidechain (corners = two freq knobs),
  **PEAK/envelope level-detect** (measured: not RMS), static GR curve with threshold, **~2.5:1 ratio**,
  selectable knee (hard "Single Vocal" / soft "Allround"), GR clamped to a `range` max-attenuation.
  Literature: Zölzer *DAFX* (dynamics, sidechain filtering), Reiss/McPherson *Audio Effects* (de-essing =
  sidechain-EQ-keyed dynamics), Giannoulis et al. "Digital Dynamic Range Compressor Design" (knee/ratio/
  ballistics, log-domain smoothing).
- **Ballistics**: smooth attack with a **fixed time constant τ≈10.6 ms (10→90%≈12.3 ms)** + ~20–35 ms
  release (peak detect + gain-smoothing); optional **lookahead** delay line on the audio path (detector
  reads ahead) — match the measured LA-on onset behaviour.
- **Audio-path action**: Wide = broadband gain g(t)·x; Split = Linkwitz-Riley/complementary crossover at the
  detection band, apply g(t) to the high band only, recombine. Smooth the gain (no waveshaping) to keep
  aliasing low → oversampling largely unnecessary for the duck itself.
- **Stereo-link**: `0%→100%` crossfade per-channel GR → one common (linked) GR. The linked detector's
  drive comes from a summed component selected by `stereo_link_mode`: Mid=(L+R)/2 or Side=(L−R)/2. The
  `">100%, k% Mid-only"` half pins link=100% and (only when mode=Side) crossfades that source Mid→Side as
  k 0→100 (≈equal-power-in-dB; inert under mode=Mid). Sidechain audition = solo the band-pass detector output.
- Build entirely from the CLEAN tables above + public literature + own voicing. Do NOT use the REF note below.
  Re-measure with `Tools/prods_sysid.py` if the build changes.

## REF note (TAINTED — reference/education ONLY; never enters product/ES-L/BuildSpec)
Static Ghidra pass (2026-06-22, VST3 arm64) corroborates the CLEAN spec; full artifacts (coeffs, raw
decompile, C-skeleton) are quarantined in `private-research/_quarantine_disasm/Pro-DS/`. Class graph = `wave::`
(`AnalogFilterPrototype`→`EQFilter`→`BiquadFilter`, `SideChainFilter`, `Detector`, `DeEssingCompressor`,
`VoicedUnvoicedDetector`, `CrossoverMultiBandModel`). Three REF take-aways (re-derive from measurement before any use):
- SC detection-band coeffs come from a **general analog-prototype IIR designer → bilinear** (Butterworth/
  Chebyshev/Elliptic/hardcoded-ladder), NOT an RBJ cookbook biquad; the measured 2nd-order ~12 dB/oct BP is its order-2 case.
- de-ess gain computer = textbook **`GR_dB = min((level−thr−knee/2)·(R−1), Range)`**, peak detector, dB↔linear via Cephes `10^(dB/20)`.
- Split vs Wide routing = `CrossoverMultiBandModel::ProcessingMode`. (All numeric coeffs live ONLY in the quarantine, never here.)

---
Provenance tags: **CLEAN** = black-box measurement (`prods_sysid.py`) / public DSP literature / own voicing
(product-safe). **REF** = static Ghidra disasm, quarantined under `_quarantine_disasm/Pro-DS/` (reference-only;
corroborates but is never cited from the CLEAN spec above).
