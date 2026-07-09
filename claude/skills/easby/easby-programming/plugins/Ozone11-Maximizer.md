# Ozone 11 Maximizer — iZotope (True-peak-capable brickwall limiter / maximizer)

| | |
|---|---|
| Vendor / ver | iZotope Ozone 11 · Maximizer module `MAXIMIZER_11_3_3541NI` |
| Type | Brickwall **lookahead limiter** ("maximizer") + soft-clip + upward comp + transient/stereo shaping |
| Tech | C++ (`DSP::` namespace, modular `ElementHost`/`Element`/`DSPSet` graph). Accelerate/**vDSP**. UI = Saffron + facebook::yoga. No JUCE. |
| Binary | **Shell + shared core.** VST3 = thin `PluginHooksVST3` (1.4M) → loads `iZCore.path` → **`iZOzone11Core.bundle` (99.8M)** in `~/Library/Application Support/iZotope/Ozone Maximizer/Cores/`. arm64+x86_64. **NOT stripped of text** (31MB `__text`, RTTI intact), **NOT encrypted** (no PACE/`LC_ENCRYPTION_INFO`). |
| Provenance | Behaviour = **CLEAN** (pedalboard black-box). Architecture/class graph = **REF** (symbols/RTTI only — no kernel disasm done yet). |
| Measured on | Ozone 11 Maximizer VST3 v11.3 · SR 48k · pedalboard 0.9.17 · 2026-06-26 |
| Source | `private-research/Ozone11Max/Tools/ozmax_sysid.py` · REF `_quarantine_disasm/Ozone11Max/decomp/` |

## ⭐ Architecture finding — ONE shared core for the whole Ozone 11 suite
`iZOzone11Core.bundle` is byte-shared across **every** Ozone 11 module (Maximizer, Dynamics, Clarity,
Stabilizer, Spectral Shaper, Master Rebalance, Vintage Comp/EQ/Limiter/Tape, Dynamic EQ, Match EQ,
Impact, Exciter, Low End Focus…). RTTI confirms one binary holds **all** module DSP classes —
`DSP::OzoneMaximizer`, `DSP::OzoneDynEq`, `DSP::OzoneExciter`, `DSP::OzoneVintageTape`, … each a plug-in
**`Element`** hosted by `DSP::OzoneDSPSet`/`ElementHost` (command-pattern `DSPCommand`/`DSPSetBase`). The
per-product `.vst3` is a stub that selects which Element(s) to instantiate via `iZCore.path` indirection.
**Decode-once-reuse-suite** (like FabFilter's shared core): one Ghidra pass on the core covers the whole Ozone line.

## Signal chain (exposed Maximizer Element)
```
x → input_gain(0..20dB) → [transient shape · stereo-independent sustain/transient]
  → upward compression → lookahead brickwall limiter (Character=release) → soft-clip(opt)
  → output ceiling (sample-peak) → y
```

## Per-stage formula (tag CLEAN/REF)
- **Brickwall ceiling** (CLEAN): output **sample-peak == `max_output_level` to ±0.00 dB** at every setting
  (0/−1/−3/−6/−12 measured exact). Hard, exact, no overshoot.
- **Lookahead / attack** (CLEAN): step into a loud tone → **zero overshoot past ceiling** ⇒ true lookahead
  limiter (clamps before the peak arrives). Exact lookahead **samples = OPEN** (pedalboard auto-compensates
  the reported PDC → structural delay reads 0; get exact value from REAPER `pdc` config-parm).
- **Release = `max_character` (0..10)** (CLEAN): program-dependent ("IRC"-style) adaptive release.
  63%-recovery time after a transient, constant-carrier probe:
  | Character | 0 | 2 | 4 | 6 | 8 | 10 |
  |---|---|---|---|---|---|---|
  | release (ms) | ~0 | ~0 | 0.7 | 2.0 | 4.7 | **38.7** |
  Monotonic, strongly super-linear at the top. 0 = near-instant (aggressive/loud), 10 = slow/smooth
  (transparent). This is the **continuous modern replacement for discrete IRC I–IV** modes.
- **True-peak** (CLEAN): exposed params clamp **sample peak only**; inter-sample (true) peak overshoots
  **+2.7…+3.5 dB** above ceiling on HF tones (7k/11k). ⇒ the automatable Maximizer Element does **sample-peak**
  brickwall; true-peak limiting is **not** controlled by these params (likely a non-automatable global Ozone
  toggle, off here). State plainly: don't assume TP from the marketing name — measured TP is uncontrolled.
- **Soft clip** (CLEAN): **odd-symmetric** saturator (H2/H4 at numeric floor −144/−156 dBc ⇒ no even
  harmonics). `mode` L/M/H = increasing **internal drive**, fixed shaper asymptoting to 1.0:
  | in → out (mix 100%) | 0.1 | 0.3 | 0.5 | 0.7 | 0.9 | small-sig gain | THD@0.9 | H3 |
  |---|---|---|---|---|---|---|---|---|
  | **L** | .119 | .357 | .595 | .833 | .997 | ≈1.19× (+1.5dB) | 2.7% | −32.7 dBc |
  | **M** | .153 | .458 | .759 | .964 | 1.00 | ≈1.53× (+3.7dB) | 12.1% | −18.4 dBc |
  | **H** | .200 | .588 | .877 | .988 | 1.00 | ≈2.0× (+6dB) | 19.1% | −14.4 dBc |
  Shape (unity-ish below ~0.5, smooth knee, hard asymptote at 1.0, odd-only) ⇒ tanh/`x·(1+|x|ⁿ)^(−1/n)`-class.
- **Oversampling** (CLEAN): 18k tone hard-limited → strongest folded alias ≈ **−15 dBc @ 6 kHz** (3rd-harm
  image). Modest OS on the limiter path. REF: `iZResampler::ResamplerEngine` (polyphase FIR, `FilterParams`,
  `ComputeFilterParams(float)`) is the OS engine.
- **Transient shaping (0..200)** (CLEAN, partial): **no effect measured on an unlimited signal** (peak flat
  across 0/100/200) ⇒ operates **inside the limiter's gain envelope**, inert when limiter idle. Needs a
  limiting-active probe to characterize — OPEN.

## Why / design rationale (music ↔ code)
- **Continuous Character (not IRC I–IV buttons)** → one knob morphs release from clamp-fast to slow-adaptive →
  removes mode-hopping; producer dials "how hard vs how clean" directly. Adaptive release = loud without pumping.
- **Lookahead + exact sample-peak brickwall** → guarantees the loudness ceiling is never exceeded (sample)
  with no transient overshoot → the core "maximizer" promise (push level, never clip the converter at sample grid).
- **Soft-clip as drive-graded odd saturator before/after limiter** → adds a touch of harmonic density &
  apparent loudness without raising the limiter ceiling → "glue/grit" stage, L/M/H = taste of saturation.
- **Stereo-independent sustain/transient + link** → limit/shape L and R by their own envelopes → preserves
  stereo width that a stereo-linked limiter would collapse; link toggle when you want mono-stable bass.

## Parameters (all CLEAN — pedalboard surface)
| param | unit | range | notes |
|---|---|---|---|
| `max_input_gain_db` | dB | 0 … 20 | drive into limiter |
| `max_output_level` | dB | −20 … 0 | ceiling (sample-peak, exact) |
| `max_link_input_gain_and_output_level` | bool | | gain-up ↔ ceiling-down link |
| `max_character` | — | 0 … 10 | **release / IRC** (0=fast, 10=~39ms smooth) |
| `max_upward_compression_amt_db` | dB | 0 … 10 | lifts quiet passages |
| `max_soft_clip_on_off` | bool | | |
| `max_soft_clip_mix` | % | 0 … 100 | dry/wet of clipper |
| `max_soft_clip_mode` | enum | L / M / H | = clip drive (≈+1.5/+3.7/+6 dB) |
| `max_transient_shaping_amt` | — | 0 … 200 | acts on limiter envelope (inert idle) |
| `max_stereo_ind_sustain_amt` | % | 0 … 100 | per-channel sustain limiting |
| `max_stereo_ind_transient_amt` | % | 0 … 100 | per-channel transient limiting |
| `max_link_stereo_amounts` | bool | | link the two stereo-ind amounts |
| `gain_input_*` / `gain_output_*` (l/r, locked/unlocked) | dB | −144 … +? | trim utility (pre/post) |
| `global_bypass` / `max_bypass` | bool | | |

## REF (quarantined — `_quarantine_disasm/Ozone11Max/decomp/`, never ships)
- `dsp_rtti_roster.txt` — full `DSP::*` RTTI class roster (whole-suite Element graph).
- `dsp_symbols.txt` — exported DSP/resampler symbols.
- Kernel decompile **deferred**: binary is open (no DRM, RTTI present) → Ghidra by-address on
  `DSP::OzoneMaximizer` would recover exact gain law / release detector / clip shaper — one pass covers all
  Ozone modules. Re-derive black-box before any of it informs product.

## CLEAN open questions
1. Exact lookahead samples (REAPER `pdc`).  2. Transient-shaping law under active limiting.
3. Upward-compression curve (threshold/ratio).  4. Soft-clip exact shaper constant (fit tanh vs poly to table).
5. Is true-peak a hidden global? (only sample-peak reachable via VST3 params).

## To implement (CLEAN path for ES-L)
Reuse ES-L's limiter; graft the **Character→release ladder** (0..10 → 0..~39ms super-linear adaptive) as a
voicing option, and the **drive-graded odd soft-clip** (tanh-class, +1.5/+3.7/+6 dB grades) as a pre-ceiling
character stage. All numbers above are measured ⇒ product-safe. Do **not** reference the REF folder.

---
Provenance: **CLEAN** = black-box measurement (product-safe). **REF** = symbols/RTTI (reference only).
