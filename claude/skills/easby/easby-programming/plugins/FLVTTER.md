# FLVTTER — Zef Parisoto (sidechain amplitude-modulator / clipper)

| | |
|---|---|
| Vendor / ver | Zef Parisoto (`com.zefparisoto.FLVTTER`) · v1.1.6 · **no DRM** |
| Type | Sidechain-driven **amplitude modulator (AM)** + **sidechain-coupled hard clipper** (2 modes), optional linear-phase FFT sidechain LP. NOT a leveler/limiter — a creative ducker/clipper. |
| Tech | **Pure JUCE C++** (no FFI). Class `FirstAudioPluginAudioProcessor` (JUCE template default name). DSP via Apple **vDSP** (`vDSP_fft_zrip/zop`, `vDSP_vclr`) behind `juce::dsp::FFT` (AppleFFT). UI = native JUCE (`ClickGraph`/`ClickFilter` draggable visualizer). |
| Binary | universal Mach-O bundle (x86_64+arm64), **not stripped** (~12k syms, methods demangle cleanly), 10 MB; no leaked dev paths |
| Provenance | **CLEAN** = clipper curve/harmonics, gain laws, FFT latency, buffer/tension nulls, bypass (pedalboard) **+ AM-ducking & tension-depth scaling (REAPER aux-bus freeze)**. **REF** = exact AM/SC-clip/tension/FFT formulas (Ghidra `decomp/`). |
| Measured on | v1.1.6 · SR 48000 · pedalboard 0.9.17 · arm64 · 2026-06-22 |
| Source | `private-research/FLVTTER/` — `Tools/flvtter_sysid.py`, `docs/clean-measurements.md`, `decomp/{algorithm-REF.md,flvtter_dsp.c,NOTICE.md}` |

## Signal chain
```
main  (stereo) ─┐                                          mode=1 CLIP:  clamp(main, ±ceil) [± sidechain-subtract]
                ├─► per-sample dispatch on `mode` ──────►  mode=0 AM:    main × (ceil − tension(SC))/ceil × makeup
sidechain(aux) ─┘   SC detect = (scL+scR)/2 · scGain                                           ↑
        │                                                                                       │
        └─ activate_fft_options? ─► linear-phase Hann-windowed LP (FFT overlap-add) ── filtered SC ┘  (latency = fft_size)
                                    cutoff=lowpass_cut_off, width=lowpass_band_width
tension: p = −sign(T)·(T/7)²  ;  getTenseValue(SC, p) = power-curve waveshaper of the sidechain
```
Two input buses: main = **stereo (required)**, sidechain = **optional stereo aux** (`isBusesLayoutSupported`: SC disabled or stereo). Output stereo. **pedalboard feeds only the main bus** → AM collapses to unity, Clip → plain symmetric clipper (the measurable subset below).

## Per-stage formula  (tag each CLEAN or REF)
- **Clip mode, no/colocated SC** (CLEAN): `out = clamp(in·mainLin, −ceil, +ceil) · outLin/mainLin`. HARD knee, symmetric, **not oversampled**. ceil=`clip_ceiling`∈[0,1]; ceil=0 → mute.
- **Clip mode, live SC** (REF @0x2267d8): `s=getTenseValue(SC·scLin,p); sum=in·mainLin+s; out = |sum|≤ceil ? sum(−s if |s|>ceil) : (|s|<ceil ? ±ceil−s : 0)`, then `·outLin/mainLin`. → clips the SUM to ceiling but subtracts the sidechain back ("clip together without affecting the secondary").
- **AM mode** (REF @0x2269b8, needs SC): `t=getTenseValue(SC·scLin,p); dist = (0≤t<ceil)?ceil−t : (t<−ceil)?|−t−ceil| : 0; out = in·dist·(env·volComp/100 + 1)/ceil · outLin`. env = ~96-sample slewed makeup follower. main_input_gain NOT applied in AM.
- **tension map** (REF): `p = −sign(T)·(T/7)²`, T=`sidechain_signal_tension`∈[−50,50] → p∈[−51,+51]; T=0→p=0→identity. **getTenseValue(x,p)** = `|x|>1 ? x : (x<0 ? −f(−x) : (p>0 ? x^(p+1) : 1−(1−x)^(1−p)))` (odd-symmetric bipolar power curve).
- **FFT lowpass** (REF @0x2261d4): **Hann window** `0.5(1−cos(2πn/(N−1)))` × freq-domain brick mask → FFT overlap-add (2/3 norm) on the **sidechain only**. **Latency = fft_size** (CLEAN: reported = {256…16384} exactly). FFT off → 0 latency.
- **gains** (CLEAN): main/sidechain/output = `10^(dB/20)`, exact (err 0.00 dB), gated to −∞ below −100 dB.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| main_input_gain | dB | −30..30 | into the clipper only; cancels below ceiling; **off in AM** |
| sidechain_input_gain | dB | −30..30 | scales SC before tension/detection |
| output_gain | dB | −30..30 | final makeup, exact 10^(dB/20) (CLEAN) |
| clip_ceiling | linear | 0..1 (def 1) | clip threshold (Clip) / duck reference (AM); 0 = mute (CLEAN) |
| volume_compensation | % | 0..200 (def 100) | AM makeup depth (env-driven); **AM-only**, inert without SC |
| sidechain_signal_tension | — | −50..50 (def 0) | power-curve shaper of SC; p=−sign(T)(T/7)²; inert without SC (CLEAN null −231 dB) |
| lowpass_cut_off | Hz | 20..22000 | linear-phase SC lowpass (FFT mode) |
| lowpass_band_width | % | 1..100 | SC lowpass transition width; sharper at higher fft_size |
| buffer_size | — | 64..2048 | **visualizer window only — audio no-op** (CLEAN null −233 dB) |
| mode | enum | {0=AM, 1=Clip} | Amplitude-Modulation vs Clip |
| activate_fft_options | bool | — | enable linear-phase SC LP; **latency = fft_size** (CLEAN) |
| fft_size | enum | {256…16384 pow2} | FFT length = exact reported latency (CLEAN) |
| bypass | bool | — | exact unity passthrough (CLEAN) |

## CLEAN measurements
- **Clip transfer** (ceil sweep): out_peak=ceil; slope_below=1.000; |out|=ceil above; ceil=0→mute. Hard knee.
- **Harmonics** 1 kHz@0.9: H2≈−181 dBc (symmetric, no even); H3 grows −20→−10 dBc as ceil 0.7→0.3; H5/H7 present; **aliasing present (no OS)**.
- **output_gain** 10^(dB/20) exact over −30..+30 (0.00 dB err). **main_gain** cancels below ceiling.
- **FFT latency** = fft_size exactly {256→256 … 16384→16384}; FFT off = 0. Main path passes undelayed-to-itself (FFT filters SC only).
- **buffer_size** −233 dB null (no audio effect). **tension** −231 dB null w/o SC. **bypass** unity. **AM** unity w/o SC.

## CLEAN sidechain — MEASURED (REAPER aux bus, freeze)  [confirms the REF AM/tension]
Reached the aux sidechain in REAPER (track2 send → FX-track ch3/4, freeze captures the receive). Main = 997 Hz −12 dB; SC = 200 Hz bursts at −24/−12/−6/0 dBFS. **AM mode ducks the main as a function of SC level, and Sidechain Tension scales the duck depth** — confirms `main×(ceil−tension(SC))/ceil` behaviorally:
| SC level → | −24 dB | −12 | −6 | 0 dB |
|---|---|---|---|---|
| duck @ tension 0 | −0.4 | −4.8 | −4.2 | −13.2 dB |
| duck @ tension 50 | −4.5 | −8.3 | −5.1 | −17.9 dB |
| duck @ tension 100 | −18.9 | −12.6 | −5.7 | −23.0 dB |
Tension 0 = gentle/late ducking; tension 100 = aggressive (deep duck even at low SC) — matches the odd-power tension map. `Mode` changes gain structure (mode-max peak −12 vs −6). Tool: `FLVTTER/Tools/flvtter_sc_probe.lua` (freeze-based SC harness).

## To implement (CLEAN path only)
Reusable CLEAN blocks: symmetric **hard clipper** `clamp(x,±ceil)` with gain-in/gain-out cancellation (add OS for anti-alias if cleaner clip wanted — FLVTTER does NOT oversample); exact dB→lin (`10^(dB/20)`); linear-phase FFT lowpass (Hann-windowed brick, overlap-add, latency=N) on a sidechain. The AM ducker (`main×(ceil−tension(SC))/ceil` with a ~96-smp makeup env), the bipolar power-curve `getTenseValue`, and the sidechain-subtract clip are **REF** for the *exact formula* — but the **AM-ducking + tension-depth behavior is now CLEAN-measured** (REAPER aux freeze, table above): build to match those duck-vs-SC curves and cite the measurement. Re-measure with `Tools/flvtter_sc_probe.lua` (SC) or `flvtter_sysid.py` (main path).

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reference only — reproduce black-box before shipping).
