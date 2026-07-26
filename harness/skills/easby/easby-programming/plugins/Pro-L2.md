# Pro-L 2 — FabFilter (Brickwall Limiter)

| | |
|---|---|
| Vendor | FabFilter · brickwall limiter, 8 styles, lookahead, oversampling, true-peak |
| Type | Limiter — symmetric-lookahead (OPPOSITE topology to AL-1's reshaper) |
| Provenance | **CLEAN** = black-box style fingerprints (`docs/`) + param table (plugin's own metadata via pedalboard) · **REF** = r2 disasm (`_quarantine_disasm/Pro-L2/`, NEVER cite from product) |
| Measured on | **Pro-L 2 v2.26 (2.2.6.0)** · VST3 (`Fx\|Dynamics`) · SR 96 kHz · `private-research/Pro-L2/Tools/prol2_sysid.py` (pedalboard 0.9.17, black-box) · 2026-06-22 |
| Binary | universal Mach-O bundle (x86_64+arm64), **STRIPPED** (6 exports = VST3 factory only) → black-box ONLY; static is a wall |
| Source | `private-research/Pro-L2/` — `docs/{style-behavior,attack-release,oversampling,style-map}.md`, `Tools/prol2_sysid.py` |

## CLEAN behavioural fingerprint (8 styles, SR 96k, lookahead 1 ms)
Probe A = lone peak in bed, +18 dB, measures **pre-duck** (lookahead pre-attenuation, samples before peak),
**deepest cut**, **recover** time. Probe B = 1 kHz +12 dB → odd-harmonic dBc (waveshaping vs pure gain-ride).
| style | pre-duck | deepest | recover | H3 dBc | character |
|---|---|---|---|---|---|
| 0 | 83 | 0.139 | 83 | −26.8 | moderate soft-clip |
| 1 | 84 | 0.139 | 999 | −41.8 | clean gain-ride, slow recover |
| 2 | 83 | 0.140 | 65 | −28.9 | fast recover + clip |
| … | | | | | (full table in docs/style-behavior.md) |
Strong H3/H5 ⇒ waveshaping/soft-clip styles; near-floor ⇒ pure gain-ride. ~96 samp = 1 ms.
Re-verified at **v2.26** (2026-06-22): styles 0/1/7 deepest-cut + H3/H5/H7 reproduce the table **exactly** ⇒ fingerprint stands; `style` enum order below confirms idx→name.

### Per-style attack/release step-response shape (CLEAN — measured 2026-06-22; `Tools/prol2_atkrel_perstyle.py`, full → docs/attack-release-findings.md)
Complements the pre-duck/recover fingerprint above. Gain-reduction **step response** for all 8 styles at a **fixed release dial raw=0.5 (857 ms label)** so the *shape* (not the dial) is what differs (lookahead=0, OS Off, TP Off, +18 dB drive). **Attack edge** = samples from a below→above-ceiling onset to reach 95% of the cut; *gain@onset* = how much lookahead pre-attenuation has already ducked the gain at the first over-ceiling sample (low ⇒ the "attack" is the lookahead pre-duck, not an edge slew). **Release shape** = single smooth TC vs dual/delayed (held then released), from the dB recovery curve + single-exponential fit R². **Prog-dep** = same dial, time-to-half-recover after a **5 ms** vs **300 ms** burst (×ratio): >1 ⇒ adaptive/program-dependent; ≈1 ⇒ fixed time-constant.
| idx | style | attack edge | gain@onset | release shape | single-exp R² | %recov @10/50 ms | prog-dep t₅→t₃₀₀ ms | verdict |
|---|---|---|---|---|---|---|---|---|
| 0 | Transparent | 14 smp (0.15 ms) | 1.00 | **single** smooth TC | 0.993 | 9 / 30 % | 123→123 (×1.0) | **program-independent** |
| 1 | Punchy | 14 smp (0.15 ms) | 1.00 | **dual/delayed** (hold) | 0.957 | 1 / 6 % | 148→324 (×2.2) | program-dependent |
| 2 | Dynamic | 14 smp (0.15 ms) | 1.00 | **single** smooth TC | 0.990 | 14 / 48 % | 59→53 (×0.9) | **program-independent** |
| 3 | Allround | 14 smp (0.15 ms) | 1.00 | **dual/delayed** (hold) | 0.990 | 0 / 0 % | 221→522 (×2.4) | program-dependent |
| 4 | Aggressive | 14 smp (0.15 ms) | 0.48 | **dual/delayed** (hold) | 0.975 | 7 / 7 % | 1→341 (×big) | program-dependent |
| 5 | Modern | 14 smp (0.15 ms) | 1.00 | **dual/delayed** (hold) | 1.000 | 1 / 15 % | 141→362 (×2.6) | program-dependent |
| 6 | Bus | 14 smp (0.15 ms) | 0.81 | **dual/delayed** (hold) | 1.000 | 0 / 8 % | 165→300 (×1.8) | program-dependent |
| 7 | Safe | 1 smp (0.01 ms) | 0.21 | **single** smooth TC | 0.996 | 20 / 39 % | 8→144 (×18.7) | program-dependent |

**Attack:** every style clamps a sustained over-ceiling step in **≤ ~0.2 ms** (brickwall edge, dial-independent — generalises the style-0 result); what differs is how much is lookahead pre-duck (gain@onset — heavy styles Aggressive/Bus/Safe pre-duck before the peak). **Release:** two families — *Transparent/Dynamic/Safe* recover as a **single smooth TC**, while *Punchy/Allround/Aggressive/Modern/Bus* **hold then release** (dual/delayed). **Program-dependence:** *Transparent + Dynamic* release in the **same** time regardless of burst length (fixed TC); the other six release much slower after a long burst than a short transient (adaptive auto-release). The dial sets rate; the **style sets the curve shape + adaptivity**. *Caveat:* 1 kHz ratio-of-peaks envelope has ~1 ms lag ⇒ sub-ms attack-edge numbers are resolution-limited (reported "≤ ~0.2 ms"); release/prog-dep times are well clear of that floor.

## Parameters (CLEAN — all values self-reported by the plugin via pedalboard: `valid_values`, `units`, `string_value`)
37 exposed params. The DSP-relevant set (the rest are meter/UI/MIDI display state, listed after). Enum option strings are the plugin's own ordered label arrays. Run `prol2_sysid.py paramfull` / `enumsweep <name>` to re-dump.

### Core limiter (audio-affecting)
| param | unit | range / enum (plugin's own labels) | default | type | notes |
|---|---|---|---|---|---|
| `gain` | dB | 0 .. +30 (linear, raw×30) | 0.00 dB | float | input/makeup gain into the limiter |
| `style` | enum | **Transparent · Punchy · Dynamic · Allround · Aggressive · Modern · Bus · Safe** (idx 0..7, raw=idx/7) | Modern (idx 5) | enum(8) | the 8 limiter algorithms; per-style fingerprints above |
| `lookahead` | ms | 0 .. 5 ms (**linear**, raw×5) | 0.180 ms | float | symmetric lookahead pre-attenuation window |
| `attack` | ms | 0 ms .. **10.0 sec** (**exponential** raw map: 0.1→1 ms, 0.5→625 ms, 0.75→3.16 s) | 275 ms | float | label flips ms→sec; max_value≈997.6 |
| `release` | ms | 0 ms .. **10.0 sec** (**exponential**: 0.1→6.9 ms, 0.5→857 ms) | 400 ms | float | program-dependent per style; max_value≈998.2 |
| `output_level` | **dBTP** | −30 .. 0 (linear) | 0.00 dBTP | float | output ceiling, expressed in true-peak dB |
| `true_peak_limiting` | bool | Off / On | **On** | bool | ISP/true-peak limiting (verified below) |
| `oversampling` | enum | **Off · 2x · 4x · 8x · 16x · 32x** | Off | enum(6) | internal OS for limiter + TP detection (32× is top) |
| `unity_gain` | bool | Off / On | Off | bool | gain-match bypass (compensate makeup for A/B) |
| `dithering` | enum | **Off · 16 / 18 / 20 / 22 / 24 Bits** | Off | enum(6) | output dither bit-depth |
| `noise_shaping` | enum | **None · Basic · Optimized · Weighted** | Optimized | enum(4) | dither noise-shaping curve |
| `filter_dc_offset` | bool | Off / On | Off | bool | DC-blocking filter at output |
| `channel_link_transients` | % | 0 .. 100 % (raw×200, clamps ≥0.5) | 75 % | float | stereo-link amount for transient grab |
| `channel_link_release` | % | 0 .. 100 % | 100 % | float | stereo-link amount for release |
| `channel_link_center` | enum | Excluded / Included | Excluded | enum(2) | surround: link the Center channel |
| `channel_link_lfe` | enum | Excluded / Included | Excluded | enum(2) | surround: link the LFE channel |
| `side_chain_triggering` | bool | Off / On | Off | bool | external side-chain key input |
| `audition_limiting` | bool | Off / On | Off | bool | monitor only the gain-reduction delta (audition) |
| `bypass` / `host_bypass` | enum | Not Bypassed / Bypassed | Not Bypassed | enum(2) | plugin + host-driven bypass |

### Meter / display / MIDI (no audio effect — UI state)
`lock_output` (Unlocked/Locked) · `receive_midi` (bool) · `show_advanced` (Hide/Show) · `true_peak_metering` (Show Sample Peaks / Show True Peaks) · `display_mode` (Slow Down/Fast/Slow/Infinite/Off) · `meter_scale` (−16 dB/−32 dB/−48 dB/K-12/K-14/K-20/Loudness) · `loudness_time_scale` (Momentary/Short Term/Integrated) · `loudness_meter_scale` (Target +9/+18) · `loudness_meter_origin` (Absolute/Relative) · `loudness_meter_target` (−60..0, default −14, i.e. LUFS target) · `loudness_integrated_peak_time_scale` (Max Momentary/Max Short Term) · `loudness_recording` (Paused/Recording) · `loudness_auto_reset` (bool) · `internal`,`midi_cc`,`pitch_bend`,`channel_pressure` (placeholders, value `-`).

### True-peak verification (CLEAN — measured 2026-06-22, style Transparent, gain +18, ceiling −1.0 dBTP, OS Off)
Fed a dual-tone inter-sample-peak stress signal (0.48 + 0.49·SR, +0.50 dB ISP head over sample peak). Output true-peak estimated by 32× FFT-upsampling. Directional result confirms TP limiting is real:
| `true_peak_limiting` | out sample-pk | out true-pk (est) |
|---|---|---|
| Off | −1.00 dBTP (at ceiling) | **+0.68 dBTP** (ISP leaks ~1.7 dB over ceiling) |
| On | −1.04 dBTP (under ceiling) | +0.52 dBTP (true-pk pulled down, sample-pk gains margin) |

TP=On lowers the inter-sample peak and increases the sample-peak headroom; with **OS≥8×** the limiter catches the ISPs and output true-peak lands well under ceiling (8× run: −5.7 dBTP for the same hot input). Residual overshoot at OS=Off for tones this close to Nyquist is expected — true-peak detection needs oversampling headroom. The load-bearing CLEAN facts are the **on/off delta + the OS≥8× clamp**, not the absolute dBTP.

#### Resolved (2026-06-22): the f≈0.49·SR over-read is a near-Nyquist *metering* artifact, not a limiter failure (`prol2_sysid.py tpartifact`)
The plugin exposes **no machine-readable output-TP value** (`true_peak_metering` is only a display-mode toggle; `output_level` is the ceiling setpoint), so the claim is settled by independent estimators on the plugin's own output audio + a synthesized ground truth. A **pure unit sine has a true analog peak of exactly 0.00 dB at every frequency** (Whittaker–Shannon; confirmed by 512× direct synthesis). Measuring that known-0 dB sine:
| f / SR | FFT-upsample(16×) est. | ITU-R BS.1770 FIR(4×) est. | truth |
|---|---|---|---|
| 0.40 | +0.34 dB | +0.20 dB | 0.00 dB |
| 0.48 | +1.86 dB | +2.05 dB | 0.00 dB |
| 0.49 | **+2.68 dB** | +1.31 dB | 0.00 dB |
| 0.499 | **+3.53 dB** | +0.01 dB | 0.00 dB |

Both standardized-style estimators **over-read near Nyquist** (an estimation artifact: the finite FIR transition band / FFT-window leakage cannot reconstruct a crest that close to fs/2 — this is the documented BS.1770 TP tolerance). The FFT method's over-read is additionally **FFT-length-dependent** at f=0.49·SR (+2.68 dB @N=8192 → +0.97 dB @N=131072), proving it is a property of the *measurement*, not the signal. **Plugin tie-in** (near-Nyquist tone, +18 dB, ceiling −1.0 dBTP): the **output sample peak stays at/under the ceiling in every case** (OS Off −1.00/−1.04; OS=8× −6.96/−7.02 dBTP) — the limiter never fails; and an **ITU-FIR estimate of the actual output reads −1.00 dBTP at OS=Off** (at ceiling, no real overshoot) and **−6.96 at OS=8×**. ⇒ the earlier "+0.68 dBTP over-read" was the FFT estimator's near-Nyquist artifact; a proper ITU-grade 4× FIR estimate shows no real overshoot, and the on/off + OS≥8× facts hold. *Remaining caveat:* exact dBTP within ~1–2% of Nyquist is method-dependent for ANY finite-rate TP meter (including the plugin's) — never quote an absolute near-Nyquist dBTP without naming the oversampling factor.

## Topology (REF — reference only, do NOT ship-cite)
Symmetric lookahead limiter; dB-domain 4-wide vectorized gain kernel (exp2/log2), lookahead mixer, true-peak
+ oversampling FIR. Opposite to AL-1's asymmetric reshaper. Details quarantined.
Exact gain law (Ghidra, REF): dB-domain `−(20/ln10)·ln|1−x|` clamped — a 4-wide-NEON Cephes `logf`→dB
converter (not exp2/pow); per-style soft-clip = `(2/π)·atan(x·π/2)`. Coeffs/pseudocode in quarantine, REF only.

## To implement (CLEAN path only)
Match the per-style pre-duck/recover/harmonic targets from `docs/` using public limiter literature + own
voicing. Use `Tools/prol2_sysid.py` to re-measure. Never reference the quarantine folder from product code.
