# Diva — u-he (Polyphonic Virtual-Analog Synth)

| | |
|---|---|
| Vendor / ver | u-he Diva **1.4.8** (Heckmann Audio GmbH) |
| Type | **Polyphonic VA synthesizer** (instrument) — *new DSP class for this catalog; every other entry is an effect* |
| Tech | Pure **C++**, no Rust/FFI. u-he **"AudioModules" engine** = patch compiled to a circuit-graph "machine" at load (`AM_MachineCompiler`). Accelerate/vDSP. Cocoa UI. |
| Binary | Mach-O universal (x86_64+arm64), 25 MB, **no DRM**. Partially stripped (865 syms; RTTI + shell only, DSP fns anonymous). Leaked build path `/Users/u-he/Jenkins-agent/workspace/Mac_Plugins/source/…` |
| Provenance | **CLEAN** = pedalboard render driven by **MIDI CC** (cutoff/res/models/ADSR) + param surface. **REF** = RTTI/strings/source-paths + **Ghidra decompile of the filter-tuning builder `FUN_005d58dc`** (per-SR coeff tables → SVF12Table). See `_quarantine_disasm/Diva/`. |
| Measured on | Diva 1.4.8 · VST3 · SR 48 kHz · pedalboard 0.9.17 + mido · 2026-06-22 |
| Source | `private-research/Diva/Tools/{diva_paramdump,diva_sysid,diva_cc}.py` (`diva_cc.py` = the MIDI-CC harness) |

## Signal chain (per voice)
```
MIDI note → Osc panel(model) → HPF → VCF panel(model) → VCA(Env1/Gate) → VoiceMixer
                  ↑ Env1/Env2, LFO1/2, mod-matrix          → global FX(1 slot) → out
2–16 voices, voice_stack 1–6 (unison), per-voice "slop" (random detune/cutoff/PW spread)
```

## Architecture (CLEAN behaviour; engine internals REF)
- **Modular panel-swap synth.** Osc / HPF / VCF / Env / LFO are swappable **models**. The model
  selector is **structural, not a host parameter** (`AM_ModuleSwitch` rebuilds the compiled graph) →
  to measure a non-default model you must load a preset that uses it (host sees the *union* of all
  models' params at once).
- **Voicing:** `voices` ∈ {2,3,4,5,6,8,12,16}; `voice_stack` 1–6 = unison; `mode` poly/mono/legato/duo/poly2.
- **"Slop" = analog imperfection** (CLEAN params): `tuneslop` `cutoffslop` `glideslop` `pwslop`
  `envrateslop` + `drift` — per-voice random spread of tune/cutoff/PW/env-rate → the живой analog stack feel.

## Models (enumerated CLEAN from param enums + REF strings)
- **Oscillator:** Triple VCO (default: 3 osc × {triangle,saw,pulse/pwm} + sub-osc shapes + ring-mod + FM),
  Dual VCO, Dual VCO Eco (`ecowave1/2`), DCO, **Digital** (`digitaltype` = Multisaw/TriWrap/Noise/Feedback/Pulse/Saw/Triangle, `digitalshape` morph + `digitalantialias`).
- **VCF (5 models):** **Ladder** (Moog; `laddermode` 24/12 dB, `laddercolor` clean/rough = *simple/complex moog* REF),
  **Multimode/SVF** (`svfmode` LP24/LP12/HP/BP — **TPT/ZDF**, `SVF12Table` REF), **Cascade**, **Uhbie** (Oberheim-SEM SV, `uhbiebandpass`), **Feedback** (`feedback`+`filterfm`).
- **Envelope (`model`):** ADS (no release stage), **Analogue**, **Digital**. ADSR + `curve`, `velocity`, `keyfollow`, `quantise`.
- **Global FX (1 slot, `module`):** Chorus (`type` Classic/Dramatic/Ensemble), Phaser, Plate (reverb), Delay, Rotary.
- **Accuracy / oversampling (`accuracy`):** draft / fast / great / divine (↑ oversampling; **great = OS×4** per load log `qlty 2 OS 4`). `offlineacc` same/best for bounce.

## Why / design rationale (music ↔ code)
- **ZDF/TPT filters (SVF + ladder)** → stable at extreme resonance + true analog **self-oscillation**;
  the topology that lets a digital Moog ladder sing without blowing up. Method is **public** — it's u-he's
  own *Zavalishin, The Art of VA Filter Design*. → use for any future VA filter/character stage.
- **Circuit-graph compiler (`AM_MachineCompiler`/`AM_Circuit`)** → one engine runs many analog *circuits*
  (each filter/osc is a circuit definition, not hand-coded) → modular models + true ZDF nodal solving →
  the CPU cost Diva is famous for. Trade: no static kernel to lift; behaviour is the spec.
- **Accuracy modes** → user trades alias rejection vs CPU; "divine" oversamples hardest for clean HF.
- **"Slop" + drift** → deliberate per-voice randomness → defeats the static, phasey sound of identical
  digital voices → the analog "wide unison" character. Cheap, high musical payoff — **portable idea**.
- **Feedback = resonance on the ladder** → emphasises the cutoff, then self-oscillates → classic acid/Moog voice.

## Parameters (191 DSP params; +2080 `cc_*_ch_*` MIDI-map slots — ignore)
| group | key params | notes |
|---|---|---|
| Global | `output`(0–200 master), `voices`, `voice_stack`, `mode`, `glide/glidemode`, `accuracy`, `offlineacc`, `multicore` | enums CLEAN |
| Slop | `tuneslop`,`cutoffslop`,`glideslop`,`pwslop`,`envrateslop`,`drift` | 0–100 / drift 0–200 |
| Osc (Triple VCO) | `tune1-3`,`volume1-3`,`shape1-3`,`saw/triangle/pulse/pwm{1,2}on`,`suboscshape`,`ringmodpulse`,`fm`,`oscmix` | shape 1–9 |
| Filter | `frequency`(cutoff 30–150),`resonance`,`feedback`(res/self-osc),`filterfm`,`laddermode`,`laddercolor`,`svfmode`,`uhbiebandpass`,`freqmod{,2}{src,depth}` | see measurements |
| Env (ADSR) | `attack`,`decay`,`sustain`,`release`,`release_on`,`model`,`curve`,`velocity`,`keyfollow` | 0–100 |
| FX | `module`,`type`,`wet/dry`,`depth`,`rate`,`predelay`,`size`,`damp`,`diffusion`… | per-FX |

## CLEAN measurements (via MIDI CC — see method note below)
- **Filter cutoff law** (CC35 = VCF1:Freq, the *real* cutoff): `log2(Fc) ≈ 0.085·CC + 7.84`
  → **exponential / ~V-oct** control, **~11.7 CC-units per octave**, Fc ≈ 229 Hz at CC0,
  sweeping ~230 Hz → ~6 kHz over the lower half of the range. (Analog-style exp cutoff.)
- **VCF models** (CC91 = VCF1:Model): **6 selectable models**, two clear pole-count classes —
  **steep ~−13…−15 dB/oct** (idx0-3, very tonal output: Ladder/Cascade/Multimode-class, 4-pole/24 dB) and
  **gentle ~−7 dB/oct** (idx4-5, 2-pole/12 dB class). Absolute slope noise-floor-compressed; the
  two-tier split + the switch itself are solid. All 6 are **resonant** — a peak emerges at the cutoff
  as resonance rises. (24/12 dB and the model names are public Zavalishin lit.)
- **Resonance / self-osc** (CC36 = VCF1:Res, or `feedback`): a narrow peak emerges at Fc, spectral
  flatness drops (→ tonal); on the Ladder, `feedback` 0→100 gave **+21 dB** gain, flatness 0.65→0.34,
  self-oscillation near the top → classic Moog behaviour.
- **OSC models** (CC17 = OSC:Model): **~5–6 models**, harmonic fingerprints —
  saw (−6 dB/oct, all harmonics), **odd-only/square-class** (evens −28 dB), **triangle** (−15 dB/oct, odd),
  digital (−8 dB/oct). Confirms the Triple/Dual-VCO/DCO/Digital taxonomy by spectrum.
- **Envelope** (CC67/68 = Atk/Dec): **attack** 0→max ≈ sub-ms → ~1.1 s; **decay** 10→120 ≈ 11→1123 ms —
  both **exponential**; attack-curve t90/t50 ratio **3.84 = exponential shape** (lin would be ~1.8).
- **Voicing/level:** `output` (CC7) clean master gain (0 = silence).

### Still-walled — confirmed root cause: structural routings aren't MIDI-assignable
Tested the midiassign-edit hypothesis directly (backed up, edited, reloaded, restored): you **can
remap an existing assignable control to a free CC** (proved: moved ENV1:RelOn 70→102, it responded),
but **invented assign-names are ignored** (LFO2:Rate / VCF1:FMSrc / FX1:Type all inert) — only the
~60 controls Diva registers as MIDI-assignable are reachable. The mod-matrix **sources**, the **VCA
source** (Gate vs Env1), and the **FX-slot type** are *structural* (mod-graph / module selections),
not assignable controls. So these stay walled headless:
- **Release time** — even with RelOn isolated on its own CC, release stayed pinned (~70 ms): the
  **VCA-source selector isn't MIDI-assignable**, so amplitude can't be forced to track Env1's release stage.
- **LFO→target routing** — mod-source selectors aren't assignable; LFO1 isn't audibly routed in a bare
  patch and LFO2:Rate isn't an assignable name → can't drive an audible LFO sweep.
- **FX type** (Chorus/Phaser/Plate/Delay/Rotary) — `#cm=`/Module structural selection, no CC. Default slot = Chorus.
- These need **GUI automation** (computer-use on Diva in a DAW) or **authoring the u-he-encoded patch state**.
- **Per-model exact dB/oct** — bounded by noise-excitation dynamic range (two-tier steep/gentle is solid).

## Harness gotchas (hard-won, Diva-specific)
- **⭐ DRIVE DIVA BY MIDI CC, NOT VST3 PARAM AUTOMATION.** The load log says `0 automatable parameters`:
  pedalboard's `setattr(p, name, v)` reaches only a *subset* of the engine — `output/volume/feedback/
  laddermode/attack/decay/mod-depths` work, but **`frequency`, `resonance`, `release`, every osc-wave
  toggle, and all model/source selectors are inert via params.** Diva's engine *does* listen to **MIDI CC**
  (mapped in `~/Library/Application Support/u-he/com.u-he.Diva.midiassign.txt`, plaintext, editable).
  Send `mido.Message('control_change', control=CC, value=v)` ahead of the note → reaches the DSP.
  The default map exposes the real controls: **CC35 cutoff, CC36 res, CC91 VCF-model, CC17 OSC-model,
  CC67/68/69/70 ADSR, CC37/42 LFO, CC38/39 FX-slots, CC72 feedback.** This is THE unlock — it converts
  Diva from "only the default patch is measurable" to "every model/cutoff/env is drivable headless."
  Harness: `Diva/Tools/diva_cc.py`. (Reading your own `midiassign.txt`/`publicparams.txt` is CLEAN.)
- **CC value→control:** 0–127 maps across the control's range; for an N-way selector, index ≈ round(v/127·(N-1)).
  Note the default map **shares CCs** across model-dependent controls (e.g. CC74 = Shape1 *or* Tri1 *or* SawShp).
- **`p.reset()` before every render** — else hung voices → every *other* render is silent.
- **C-level `printf` spam** (`NKS logging…`) bypasses Python stdout → redirect **fd 1/2** (`os.dup2`), `grep -av`.
- **Filter magnitude from noise:** put cutoff LOW and fit slope *well above* the corner over several octaves
  — measuring inside the passband reads ~flat; the saw's own 1/k rolloff must be divided out (wide-open ref).
- **Accuracy/oversampling not observable offline** — pedalboard offline render used fixed quality.

## To implement / relevance to ES-L
**Synth — does NOT feed ES-L (a limiter).** No shippable lineage. Value = reference + portable CLEAN ideas:
- **TPT/ZDF SVF** (Zavalishin, public) → drop-in for any future VA filter / filtered-saturation / character EQ.
- **Per-voice "slop"/drift** → a general "analog spread" device (random micro-detune/cutoff) for any voiced/character processor.
- Self-oscillating resonant filter as a tone generator / exciter.

---
Provenance: **CLEAN** = black-box measurement / public DSP (Zavalishin VA filter book is u-he's own) / own voicing.
**REF** = RTTI/strings/source-paths in `_quarantine_disasm/Diva/` — reference only, never cite from product.
