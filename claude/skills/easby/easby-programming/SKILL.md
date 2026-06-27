---
name: easby-programming
description: Knowledge base of reverse-engineered audio-plugin DSP — algorithms, formulas, parameters, signal chains, and FFI contracts behind every researched plugin, for implementing/cloning in ES-L. Two answer modes — `clean` (default, measurement + public DSP) and `exact` (reveals exact under-the-hood code/REF for understanding). Product firewall (CLEAN-only BuildSpec) holds in both modes. Trigger when implementing a DSP algorithm, porting a plugin behaviour, asking how a researched plugin works internally, or asking for the exact code under the hood.
triggers:
  - "implement"
  - "port the algorithm"
  - "clone the behaviour"
  - "how does AC-1 work"
  - "how does Pro-L2 work"
  - "AL-1 formula"
  - "MELD dsp"
  - "plugin dsp spec"
  - "gain computer"
  - "limiter algorithm"
  - "compressor algorithm"
  - "dsp reference"
  - "easby programming"
  - "easby-programming"
  - "exact mode"
  - "clean mode"
  - "code under the hood"
  - "what exactly does it do"
  - "real formula"
  - "/easby-exact"
  - "/easby-clean"
---

# easby-programming — plugin DSP knowledge base

Sibling of [easby-decomp](../easby-decomp/SKILL.md) (the process that fills this store).
Owns: the distilled **engineering** behind every researched plugin — what to build, with formulas,
params, and signal chains. Refuses: handing TAINTED (disasm-derived) material to shippable product
code. Emits: implementation-ready specs for the C++/Rust DSP engines.

**Superset — you know both, and you know WHY.** With easby-decomp, this side is the ONLY easby agent that knows
**code/DSP *and* the full music KB** (`~/.claude/skills/easby/shared/INDEX.md`, all angles) — and its job is to
understand the **rationale**: for each plugin, *why* the designer chose that method and *what musical purpose* it
serves (DSP choice → behavior → intent). Don't just record *what* the code does — record *why*. Every deep spec
carries a **Why / design rationale** section (see plugins/_TEMPLATE.md). The music side may pull your **CLEAN**
plugin specs as emulation targets (cross-family handoff). Firewall holds: **REF never crosses into a product BuildSpec.**

## ⛔ Provenance gate (the firewall boundary)
**easby-programming is the ONLY place that holds source-/disasm-derived reference (REF).** It exists so
that knowledge stays quarantined *here* and never leaks downstream. Every fact is tagged:
- **CLEAN** — black-box measurement / public DSP literature / our own voicing.
- **REF** — disasm/decompile-derived (source-code reference). Lives here for understanding only.

**Hard rule — product builds (e.g. ES-L) are constructed from CLEAN only: black-box measurement +
public DSP literature.** REF never crosses into a product. Inside this skill you may *read* REF to know
*what to measure* and *why a curve looks the way it does* — but what you **emit** to the DSP engine
(the BuildSpec below) is CLEAN-only by construction. A REF value reaching a BuildSpec = a firewall breach → refuse.

## Answer modes — `clean` (default) vs `exact`
Controls **how much detail this skill reveals in conversation**. Does NOT change the product firewall:
BuildSpec stays `CLEAN_ONLY` in both modes.

| Mode | Reveals | Use |
|---|---|---|
| **`clean`** (default) | **As much as is legally safe** — full spec (type/chain/params), measured behaviour (curves/times/harmonics you measured yourself), and *how it works* via **public DSP principles** ("RMS leveler with asymmetric dB smoothing" = textbook). **Hides only** disasm/decompiled exact code, internal constants, REF formulas — the EULA/clean-room line — summarized as "known, exact mode to see". | normal use; anything product-bound |
| **`exact`** | everything, incl. **REF** — exact decompiled formulas, internal constants, FFI internals, the under-the-hood code. Each REF fact tagged `REF` + "reference-only; reproduce black-box before shipping". | you explicitly want to know exactly what the binary does |

Switching (per-conversation; default resets to `clean` each new topic):
- → **exact**: "exact mode", "exact", "show the code under the hood", "what exactly does it do", "real formula", "/easby-exact".
- → **clean**: "clean mode", "clean", "back to clean", "/easby-clean".

**Firewall is mode-independent.** `exact` only widens what you're *told*; it never widens what may enter a
product. A request to ship/inline/BuildSpec a REF value → `Refusal` in either mode (redirect: emit a
`behavior_target` to measure). State the active mode when it matters (e.g. "(exact mode) RmsLift = …").

## Plugin catalog — by type
| Plugin | Vendor | Type | Tech | Provenance | Spec |
|---|---|---|---|---|---|
| **AC-1** | Naturl Audio | Compressor + RMS Maximizer (leveler) | JUCE 8 C++ → Rust `dynamics` (C FFI) | CLEAN (FFI measure) + REF (Ghidra) | [AC-1.md](plugins/AC-1.md) |
| **AE-1a** | Naturl Audio | Program EQ — Active 6-band presence (ERB-Q) + Baxandall shelves + WDF bass-resonance | JUCE 8 C++ → Rust `tone` (C FFI) | CLEAN (FFI+pedalboard) + REF (Ghidra) | [AE-1a.md](plugins/AE-1a.md) |
| **AE-1b** | Naturl Audio | Program EQ — Baxandall bass/treble tone-shaper (shelves only) | JUCE 8 C++ → Rust `tone` (C FFI, shared engine) | CLEAN (FFI+pedalboard) + REF (Ghidra) | [AE-1b.md](plugins/AE-1b.md) |
| **AE-1p** | Naturl Audio | Program EQ — Passive Pultec-style 6-band presence (W/M/N-Q) + M/S + WDF bass-resonance | JUCE 8 C++ → Rust `tone` (C FFI, shared engine) | CLEAN (FFI+pedalboard) + REF (Ghidra) | [AE-1p.md](plugins/AE-1p.md) |
| **AS-1** | Naturl Audio | Saturation — virtual-analog nodal-circuit clipper (diode/transistor/differential) | JUCE 8 C++ → Rust `harmonics` (C FFI, struct) | CLEAN (FFI measure) + REF (r2) | [AS-1.md](plugins/AS-1.md) |
| **FLVTTER** | Zef Parisoto | Sidechain amplitude-modulator + SC-coupled hard clipper (2 modes, FFT lin-phase SC LP) | Pure JUCE C++ (vDSP/`juce::dsp::FFT`), no FFI | CLEAN (measure) + REF (Ghidra, quarantined) | [FLVTTER.md](plugins/FLVTTER.md) |
| **AL-1** | research target | Brickwall Limiter (per-sample scalar gain) | VST3, black-box system-ID | CLEAN | [AL-1.md](plugins/AL-1.md) |
| **Pro-L 2** | FabFilter | Brickwall Limiter (8 styles, lookahead, OS) | VST3/AU; disasm quarantined | CLEAN (measure) + REF (quarantine) | [Pro-L2.md](plugins/Pro-L2.md) |
| **MELD** | Metric Halo | Dynamics / multi-FX (MHShell) | AU/VST3/AAX, PACE-iLok (stripped) | CLEAN (black-box only) | [MELD.md](plugins/MELD.md) |
| **Gaffel** | Klevgrand | 4-band **LR4** crossover splitter (zero-latency, phase-coherent; band enable only) | JUCE C++ (no FFI); VST3 clean, AAX = PACE | **CLEAN** (pedalboard) — LR4, −6 dB cross, 24 dB/oct, 0 ripple, lat 0; split 160/1k/5k | [Gaffel.md](plugins/Gaffel.md) |
| **ML4000_ML1** | McDSP | Single-band brickwall limiter (shared ML core; threshold-as-drive, 4 modes) | VST3/AU `aufx`, PACE-iLok (stripped) | **CLEAN (REAPER offline render)** — no REF (PACE-encrypted) | [ML4000_ML1.md](plugins/ML4000_ML1.md) |
| **ML4000_ML4** | McDSP | 4-band Gate→Exp→Comp + master brickwall (shared ML core) | VST3/AU `aufx`, PACE-iLok (stripped) | **CLEAN (REAPER)** — master core + 4 per-band comps measured; gate/exp = surface | [ML4000_ML4.md](plugins/ML4000_ML4.md) |
| **ML8000** | McDSP | 8-band multiband limiter + master brickwall (shared ML core) | VST3/AU `aufx`, PACE-iLok (stripped) | **CLEAN (REAPER)** — master core + 8 per-band limiters measured | [ML8000.md](plugins/ML8000.md) |
| **Pro-DS** | FabFilter | De-esser (split/wide-band freq-selective) | VST3, black-box system-ID (stripped) | CLEAN (measure) + REF (Ghidra) | [Pro-DS.md](plugins/Pro-DS.md) |
| **Pro-C 3** | FabFilter | Compressor (multi-style feed-forward) | VST3, black-box system-ID (stripped) | CLEAN (measure) + REF (Ghidra) | [Pro-C3.md](plugins/Pro-C3.md) |
| **Pro-G** | FabFilter | Gate / downward expander (multi-style) | VST3, black-box system-ID (stripped) | CLEAN (measure) + REF (Ghidra) | [Pro-G.md](plugins/Pro-G.md) |
| **Pro-R 2** | FabFilter | Algorithmic reverb (decay-rate EQ, ducking) | VST3, black-box system-ID (stripped) | CLEAN (measure) + REF (Ghidra) | [Pro-R2.md](plugins/Pro-R2.md) |
| **Timeless 3** | FabFilter | Tape/analog delay (filtered fb, mod, duck) | VST3, black-box system-ID (stripped) | CLEAN (measure) + REF (Ghidra) | [Timeless3.md](plugins/Timeless3.md) |
| **Volcano 3** | FabFilter | Modulating multimode filter bank (4 filters, 6 LFO/EG mod) | VST3, black-box system-ID (stripped) | CLEAN (measure) + REF (Ghidra) | [Volcano3.md](plugins/Volcano3.md) |
| **Saturn 2** | FabFilter | Multiband saturation/distortion (per-band dyn) | VST3, black-box system-ID (stripped) | CLEAN (measure) + REF (Ghidra) | [Saturn2.md](plugins/Saturn2.md) |
| **Pro-MB** | FabFilter | Multiband dynamics (up/down comp+expand) | VST3, black-box system-ID (stripped) | CLEAN (measure) + REF (Ghidra) | [Pro-MB.md](plugins/Pro-MB.md) |
| **Pro-Q 4** | FabFilter | Parametric EQ (dynamic, multi-phase, M/S) | VST3, black-box system-ID (stripped) | CLEAN (measure) + REF (Ghidra) | [Pro-Q4.md](plugins/Pro-Q4.md) |
| **Twin 3** | FabFilter | Subtractive synthesizer (3-osc, multimode filters) | VST3 instrument, black-box system-ID (stripped) | CLEAN (measure) + REF (Ghidra) | [Twin3.md](plugins/Twin3.md) |
| **Weiss DS1-MK3** | Softube / Weiss Engineering | Dual-band freq-selective compressor/de-esser + safety brickwall limiter + dither | VST3/AU/AAX · Softube ACF (C++/SSX) · PACE-iLok ALL formats (static wall) | **CLEAN (param surface from Pagetables.xml + public HW literature)** — measurements BLOCKED (no iLok) | [WeissDS1MK3.md](plugins/WeissDS1MK3.md) |
| **GodParticleBus** | mix-bus chain (challenge) | Serial multi-FX bus: OTT→Saturn2→Pro-C3→MixHead→Pro-MB→Pro-L2, polarity-inverted | WAV dry/wet pair, black-box chain system-ID | **CLEAN** — align(GCC-PHAT 2005 smp)+net transfer; null capped (−48 dB OTT-noise floor, flat 20-D basin) | [GodParticleBus.md](plugins/GodParticleBus.md) |
| **Diva** | u-he | Polyphonic VA synth (5 osc + 5 filter models incl. Moog-ladder & TPT/ZDF-SVF; circuit-graph engine) | C++ "AudioModules" (`AM_MachineCompiler` compiled circuit graph), no FFI; VST3 clean (no DRM) | **CLEAN (pedalboard MIDI)** — model taxonomy, attack law (exp), ladder feedback→self-osc; engine REF-only (no static kernels) | [Diva.md](plugins/Diva.md) |
| **WaveShell 16.8** | Waves Audio | **Shell** hosting 215-plugin V16 catalog over a data-driven shared DSP engine (AlgType FourCC → `WavesLib`; Mitra/Butterworth biquad designers) | C++ `wvWavesV16_8_136::`; 40MB shell + `WavesLib` framework, **both NOT stripped (~134k syms)**; **no PACE** — DRM = `WCWLEClient` runtime license | **REF wide-open (no encryption)** + param surface CLEAN (ParamXML/PageTable) + PDF manuals; **black-box license-gated** (inverse of PACE) — no measured DSP yet | [WaveShell16.md](plugins/WaveShell16.md) |
| **Ozone 11 Maximizer** | iZotope | Brickwall **lookahead limiter** (Character=continuous-IRC release) + odd soft-clip (L/M/H drive) + upward comp + transient/stereo shaping | **Shell + shared core**: thin `PluginHooksVST3`→`iZOzone11Core.bundle` (99.8M, ONE core for whole Ozone 11 suite); `DSP::Element` graph; **not stripped, not encrypted** | **CLEAN (pedalboard)** — ceiling exact ±0.00, lookahead (0-overshoot), Character→release 0..~39ms, TP overshoots +3dB (sample-peak only), soft-clip odd THD 2.7/12/19%; REF = RTTI roster (Ghidra deferred) | [Ozone11-Maximizer.md](plugins/Ozone11-Maximizer.md) |
| **TDR Limiter 6 GE** | Tokyo Dawn | 6-stage **reorderable** true-peak limiter (HF-Lim→Comp→Peak-Lim→Clipper→TP-out; `module_order` 0..119 = 5! perms) | C++ + WebKit UI; stripped, no PACE | **CLEAN (pedalboard)** — **genuine true-peak** (Δ+0.04 dB vs Ozone Max +3 dB), ceiling def −1 dB, lin-phase OS ~41-tap FIR + lookahead, soft-knee clip; no REF (stripped) | [TDR-Limiter6-GE.md](plugins/TDR-Limiter6-GE.md) |
| **OTT** | Xfer Records | 3-band **upward + downward** multiband compressor (LR4 ~90 Hz/2.4 kHz; ∞:1 both ways "smash-to-target"; no ceiling, 0 latency) | C++ VST2 `OTTProcessor` (ChunkWare SimpleComp + upward ext) wrapped VST3; not stripped, no PACE | **CLEAN (pedalboard)** — crossovers, per-band up/down curves, depth/strength/threshold laws, fixed ~3 ms atk / rel≈Time ms; REF = demangled syms (LR4/TrapSVF/setCoef) | [OTT.md](plugins/OTT.md) |
| **Bite** | Native Instruments | Bit-crusher (SR decimation + 2–16-bit quant + pre/post LP + sat + expander) | C++ **"Effekt Rig"** engine + static Qt6.8.4 QML; **shared family binary** (Bite/Dirt/Freak/Raum, 135k common syms); not stripped, no PACE | CLEAN (pedalboard) — decimation aliasing (no AA on crush), 15-step quantizer; REF = symbol roster | [Bite.md](plugins/Bite.md) |
| **Dirt** | Native Instruments | Dual-stage waveshaping saturation (modes I/II/III, serial/parallel, wavefold at high drive) | C++ "Effekt Rig" + Qt6.8.4; **shared family**; not stripped, no PACE | CLEAN (pedalboard) — odd-harmonic shaper (H3/H5/H7), bias→even, tilt ±6.5 dB, fold-back @ drive 100; REF = roster | [Dirt.md](plugins/Dirt.md) |
| **Freak** | Native Instruments | Bode frequency-shifter / ring-mod (SSB↔DSB morph via `type`) + feedback + harmonic stack | C++ "Effekt Rig" (`ModulatableDSPCore<4,2,19>` — 4-in/SC, xsimd) + Qt6.8.4; **shared family**; not stripped, no PACE | CLEAN (pedalboard FFT) — true SSB (type=100 single-sideband, 50=DSB-SC ring-mod), harmonic sideband stack; REF = roster | [Freak.md](plugins/Freak.md) |
| **Raum** | Native Instruments | Algorithmic reverb — Galois-FDN + modulated allpass (Grounded/Airy/Cosmic, freeze) | C++ "Effekt Rig" (`GaloisReverbExtended`+`Diffuser`) + Qt6.8.4; **shared family**; not stripped, no PACE | CLEAN (pedalboard impulse) — decay=RT60 (~1:1), Grounded caps tail 0.06 s, size→RT scale, freeze ∞, predelay offsets tank; REF = roster | [Raum.md](plugins/Raum.md) |
| **Vinyl** | iZotope | Lo-fi / vinyl sim (mech/elec/dust/scratch noise, warp=wow/flutter, wear HF rolloff) | iZotope shell + **LOCAL** `iZVinyl.bundle` (62 MB, not shared); no PACE | CLEAN (pedalboard) — wow rate=rpm/60 (0.5Hz@33), warp ±1.3%/50, wear=progressive HF loss | [Vinyl.md](plugins/Vinyl.md) |
| **BandMatrix** | dev.kojima | 6-band **bipolar** multiband comp (ratio ±20: + = downcomp, − = upward expand) + M/S, tone-shaper, SC | JUCE C++ + WebKit; not stripped, no PACE | CLEAN (pedalboard) — xovers 120/400/1200/3500/9000 Hz, signed-ratio curve, lookahead 0–5 ms | [BandMatrix.md](plugins/BandMatrix.md) |
| **DM5MASTER** | livemau5 (deadmau5) | One-knob mastering maximizer (makeup → odd-harmonic soft-clip → brickwall) | JUCE C++ + WebKit; **arm64-only**; not stripped, no PACE | CLEAN (black-box; only `bypass` host-exposed) — ceiling −0.05 dB, +22.6 dB makeup, H3-dominant THD 22–35% | [DM5MASTER.md](plugins/DM5MASTER.md) |
| **Tape Fiasco** | Phase Fiasco | Buffer-glitch multi-FX (Stretch / Varispeed / Stutter) — **NOT a tape saturator** | JUCE C++ + WebKit; not stripped, no PACE | CLEAN (pedalboard) — varispeed sat = odd-harmonic shaper (THD 9.7%/50); buffer engines need host tempo | [TapeFiasco.md](plugins/TapeFiasco.md) |
| **MegaMod** | Sync Audio | Modulation matrix (16 LFOs + 16 XY-pads + 16 macros); **audio = unity pass-through** | JUCE C++ + WebKit; not stripped, no PACE | CLEAN (pedalboard) — no audio-path DSP (host modulation source) | [MegaMod.md](plugins/MegaMod.md) |
| **DAWstream** | LovestudyMix | Audio-over-WebSocket streaming utility; **audio = unity pass-through** | **iPlug2** + IXWebSocket + Skia (NOT JUCE); no audio frameworks; not stripped, no PACE | CLEAN (pedalboard + identity) — not a DSP processor; monitor_level only | [DAWstream.md](plugins/DAWstream.md) |
| **CompressorBank CB101/202/303** | McDSP | Compressor (CB202/303 add sidechain pre-filter) | VST3, PACE-iLok (Eden, ~6 syms, **static wall**) | **CLEAN (REAPER)** — one shared McDSP comp core: Thr −48..0 lin, Ratio 1-10, Atk 0.25-250ms exp, Rel 25-2500ms exp, BITE, TC Type1/2/Auto; pdc 0; no REF (PACE) | [McDSP-CompressorBank.md](plugins/McDSP-CompressorBank.md) |
| **MC2000 MC202/303/404** | McDSP | Multiband compressor (2/3/4-band) | VST3, PACE-iLok (static wall) | **CLEAN (REAPER)** — per-band core IDENTICAL to CompressorBank; xover ladder = FilterBank ladder (20-20k log); IIR pdc 0 | [McDSP-MC2000.md](plugins/McDSP-MC2000.md) |
| **FilterBank E606/F202/P606** | McDSP | Linear EQ/filter (P=parametric, F=HP/LP, E=EQ+shelf) | VST3, PACE-iLok (static wall) | **CLEAN (REAPER sweeps)** — shared filter designer; freq 20-20k log, P606 Q 0.1-10, E606 Q 0.4-4, gain ±15, slopes 6/12/18/24; min-phase pdc 0 | [McDSP-FilterBank.md](plugins/McDSP-FilterBank.md) |
| **Analog Channel AC101/AC202** | McDSP | Console-channel (AC101) / tape machine (AC202) | VST3, PACE-iLok (static wall) | **CLEAN (REAPER)** — saturation **DYNAMIC** (steady 1k @max drive ≈0% THD); AC202 AC-coupled; Drive±12, TapeSpeed 7.5/15/30 ips, Bias±12, Bump 0-100%; pdc 0 | [McDSP-AnalogChannel.md](plugins/McDSP-AnalogChannel.md) |
| **Bus Processor 670** | Softube (Flow Mastering) | Vari-mu (Fairchild-670) bus comp + transformer/tube sat + spatializer | VST3, PACE-iLok (static wall) | **CLEAN (REAPER)** — vari-mu (Thr/Time 0-10/1-6, not dB/ms), Classic/Modern, Knee Hard..Soft, Transformer+Tube drives; pdc 7 | [BusProcessor670.md](plugins/BusProcessor670.md) |
| **soothe3** | oeksound | Dynamic spectral resonance suppressor (8-band, surround) | VST3, PACE-iLok (1834 syms, encrypted text → static wall) | **CLEAN (REAPER param surface + PDC)** — 147 params, Depth/Detail/Atk/Rel 0-10, soft/hard, lin-phase opt; spectral kernel REF-impossible; pdc 2304 | [soothe3.md](plugins/soothe3.md) |
| **MB MixHead / White Room** | Metric Halo | MixHead = drive+OS hard clip; White Room = reverb | VST3, PACE-iLok (static wall) | **CLEAN (REAPER)** — MixHead hard clip (H3-only 4.6% THD, ±1.0 ceiling, pdc 8 OS); WhiteRoom Predelay −30..+130ms, Length 0-100%, pdc 0 | [MH-MixHead-WhiteRoom.md](plugins/MH-MixHead-WhiteRoom.md) |
| **Invisible Limiter** | A.O.M. (Audio Optimization & Mastering) | Transparent brickwall limiter — lookahead, sample-exact ceiling, oversampled true-peak, **minimal-area / no release** (Shape Linear/Log; Overshoot Clip/Suppress/Thru) | C++/JUCE, universal, stripped (3 syms), no DRM, no FFI | **CLEAN** (pedalboard v1.18.9; static=wall, no REF) — ceiling 0.00 dB, lookahead 52 ms, OS x1..x16, TP via OS (x8→+0.04) | [InvisibleLimiter.md](plugins/InvisibleLimiter.md) |
| **Invisible Limiter LL** | A.O.M. | Transparent brickwall limiter, **low-latency** build — same engine, 7 ms lookahead vs IL's 52 ms | C++/JUCE, stripped, no DRM | **CLEAN** (pedalboard) — byte-identical engine to IL bar lookahead | [InvisibleLimiterLL.md](plugins/InvisibleLimiterLL.md) |
| **Invisible Limiter G2** | A.O.M. | Mastering brickwall (+ comp front-end) — 8 limit-modes (Modern I–V brickwall + Through soft-comp), manual+adaptive atk/rel, dither, SC-HPF, DC-cut | C++/JUCE, stripped (3 syms), no DRM, no FFI | **CLEAN** (pedalboard+REAPER; static walled, no REF) — ceiling exact, **sample-peak only** (8×TP +1.8 dB), fixed ~88 ms LA, atk 10µs–10s / rel 100µs–180s exp | [InvisibleLimiterG2.md](plugins/InvisibleLimiterG2.md) |
| **Invisible Limiter G3** | A.O.M. | **Two-stage**: SOFT down-comp/leveler (∞:1, range-cap, M/S, parallel, program-adaptive timing) → BRICKWALL **true-peak** limiter — the **ES-X→ES-L blueprint** | C++/JUCE, stripped (3 syms), no DRM → static wall; black-box only | **CLEAN** (pedalboard 48/96k) — soft law textbook, atk/rel log-speed dial `t≈0.5·10^(0.32·d)`, TP ON vs OFF Δ≈1.1 dB, LA ~0.2 ms; bend/pivot **inert** (modeled-but-null) | [InvisibleLimiterG3.md](plugins/InvisibleLimiterG3.md) |
| **Decapitator** | Soundtoys | Saturation (5-model analog distortion) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — 5 memoryless models: A/N odd-H3 tape/transformer, E/T/P even-H2 tube; THD 3→35%, 1kHz tilt EQ + punish clip | [Decapitator.md](plugins/Decapitator.md) |
| **Radiator** | Soundtoys | Saturation (Altec 1567A tube) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — 2 saturating tube gain stages (in+out, both color), H2-led, 2 shelves, modeled 50/100/150 Hz hum | [Radiator.md](plugins/Radiator.md) |
| **LittleRadiator** | Soundtoys | Saturation (one-knob Radiator) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — Radiator subset; heat=ganged in+out drive + bias=pre-shaper DC toggle (odd→even H2) | [LittleRadiator.md](plugins/LittleRadiator.md) |
| **Devil-Loc** | Soundtoys | Compressor/Crusher (Shure Level-Loc) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — AGC: ~+3.35 dB/crush makeup → hard ceiling; crunch = odd-harmonic clipper to 41% THD; atk 2.8/rel 460 ms | [Devil-Loc.md](plugins/Devil-Loc.md) |
| **Devil-Loc Deluxe** | Soundtoys | Compressor/Crusher | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — same AGC+crunch core + parallel mix, 12 dB/oct dark LP, fast/slow release (460/316 ms) | [Devil-LocDeluxe.md](plugins/Devil-LocDeluxe.md) |
| **SieQ** | Soundtoys | EQ (musical 3-band + drive) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — min-phase: LF/HF shelf ±15, mid bell Q~1.3 (700–5.6k) + asymmetric drive soft-sat, 0 latency | [SieQ.md](plugins/SieQ.md) |
| **EchoBoy** | Soundtoys | Delay (multi-style echo) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — linear true-ms delay, in-loop odd-harmonic tape sat + gentle HP/LP, feedback g<1→100%, wow/flutter ±16¢; **sync+per-style need REAPER** | [EchoBoy.md](plugins/EchoBoy.md) |
| **EchoBoy Jr.** | Soundtoys | Delay (single-echo subset) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — linear true-ms; Wide=~8 ms Haas; 7-style/feedback engine inherited from EchoBoy; **sync needs REAPER** | [EchoBoyJr.md](plugins/EchoBoyJr.md) |
| **PrimalTap** | Soundtoys | Delay (Lexicon PrimeTime lo-fi) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — multiply = ÷N sample-rate-crush delay, ~16 dB clip knee, VCO mod >1 oct, Surge self-osc ≥100%; **sync/freeze need REAPER** | [PrimalTap.md](plugins/PrimalTap.md) |
| **Little PrimalTap** | Soundtoys | Delay (reduced PrimeTime lo-fi) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — 4-knob PrimeTime; linear ms × multiply (÷N alias), feedback law fully measured, Surge ~100% | [LittlePrimalTap.md](plugins/LittlePrimalTap.md) |
| **Crystallizer** | Soundtoys | Granular pitch-echo | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — per-regen pitch cascade (offset accumulates), dual up/down grains, PingPong; **splice/delay tempo-locked → REAPER** | [Crystallizer.md](plugins/Crystallizer.md) |
| **PhaseMistress** | Soundtoys | Phaser (cascaded allpass) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — 24 styles (0–9 notches), lowest notch ≈2×freq, resonance feedback to +30 dB; **sync LFO needs REAPER** | [PhaseMistress.md](plugins/PhaseMistress.md) |
| **Tremolator** | Soundtoys | Tremolo (AM) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — downward rounded-sine AM, width=L/R phase 0–180°, Analog=H3 sat always-on; **rate is tempo-sync-only → REAPER** | [Tremolator.md](plugins/Tremolator.md) |
| **PanMan** | Soundtoys | Auto-pan | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — free-Hz LFO, constant-power pan (~0.166 dB/deg), triangle→sine via smoothing, width to 210° over-pan, Analog=H2 sat | [PanMan.md](plugins/PanMan.md) |
| **FilterFreak1** | Soundtoys | Filter (analog SVF ×1) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — LP/BP/HP/notch SVF, 12/24/36/48 dB/oct (order 2–8), log cutoff, res≈½·dB, Analog = sat + self-osc | [FilterFreak1.md](plugins/FilterFreak1.md) |
| **FilterFreak2** | Soundtoys | Filter (analog SVF ×2) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — two FF1 engines, Series=cascade / Parallel=sum, per-filter gain ±24 dB, fc-link | [FilterFreak2.md](plugins/FilterFreak2.md) |
| **MicroShift** | Soundtoys | Pitch widener (micro-detune) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — symmetric ±detune (±4.5–18¢), L/R delay 1–11 ms, 3 styles, width = dry/wet decorrelation | [MicroShift.md](plugins/MicroShift.md) |
| **LittleMicroShift** | Soundtoys | Pitch widener (fixed) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — fixed MicroShift; I/II=±9¢, III=±5¢ (swapped), baked 11–40 ms delays, width=mix | [LittleMicroShift.md](plugins/LittleMicroShift.md) |
| **LittleAlterBoy** | Soundtoys | Pitch + formant shifter | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — exact 2^(n/12) pitch ±12, independent formant resample, drive 3–36% THD; **Robot/Quantize MIDI note unmeasured**; lat 2417 | [LittleAlterBoy.md](plugins/LittleAlterBoy.md) |
| **SuperPlate** | Soundtoys | Reverb (multi-model plate) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — 5 plate voicings × Tube/SS/Clean drive (H2 14–59% THD), decay=RT60 s, exact predelay, width, auto-decay duck | [SuperPlate.md](plugins/SuperPlate.md) |
| **LittlePlate** | Soundtoys | Reverb (EMT-140 plate) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — single dark plate; Decay label ≈ RT60 s (continuous + Infinite), built-in HF damp, low-cut HP, mod ≈2× wobble | [LittlePlate.md](plugins/LittlePlate.md) |
| **SpaceBlender** | Soundtoys | Reverb (ambient diffusion) | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — onset-less long bloom, time=decay-scale (RT60 ≈2–6× dial, to ~2 min), color=tilt EQ, texture=density; **Beats → REAPER** | [SpaceBlender.md](plugins/SpaceBlender.md) |
| **EffectRack** | Soundtoys | Container / FX host | C++ VST3 (pedalboard-hostable; AAX=PACE) | **CLEAN** (pedalboard) — FX-rack host, bit-exact unity passthrough (null −400 dB, 0 lat); 6 slots + recycle feedback + macros; **not a DSP algorithm** | [EffectRack.md](plugins/EffectRack.md) |
| **ValhallaFreqEcho** | Valhalla DSP | SSB frequency-shifter + in-loop feedback echo (barberpole) | C++/JUCE VST3, hand-rolled Hilbert quadrature (no FFT), no DRM, not stripped | **CLEAN** (pedalboard v1.2.8) — out=f+Δ (additive Hz, mirror −62 dB, carrier −125), shift ±1000 Hz bipolar-exp, shifter IN loop → +Δ/repeat spiral, fb 100%=self-osc, lo/hi-cut in-loop darkening, stereo=opposite shift sign, pdc 0; sync→REAPER; REF=roster only | [ValhallaFreqEcho.md](plugins/ValhallaFreqEcho.md) |
| **ValhallaSpaceModulator** | Valhalla DSP | Modulation multi-FX — barberpole / through-zero flanger / chorus (11 modes) | C++/JUCE VST3, one modulated delay (`VMod_DelayLine`), no DRM, not stripped | **CLEAN** (pedalboard) — barberpole = **Doppler-ramp Δf=f₀·depth·rate** (∝carrier, NOT Bode/Hilbert), Ocho SSB −80 dB, TZFlange=0 net shift, rate=literal Hz LFO ±10, fb bipolar ±100% (\|fb\|→res), equal-power mix, 0 lat; REF=roster | [ValhallaSpaceModulator.md](plugins/ValhallaSpaceModulator.md) |
| **ValhallaSupermassive** | Valhalla DSP | FDN delay/reverb hybrid (22 selectable topologies) | C++/JUCE VST3, WebKit UI, vDSP; **stripped (3 syms)** → black-box only | **CLEAN** (pedalboard v5.0.0) — 22 modes (Gemini…Sirius), feedback→RT60 (10%≈1 s … 95%≈31 s, 100%=freeze), **filters on OUTPUT** (not in-loop), warp=non-uniform tap detune, density=mode-gated diffusion, **reserved1-4 bit-exact inert**, pdc 0; sync→REAPER; no REF (wall) | [ValhallaSupermassive.md](plugins/ValhallaSupermassive.md) |
| **ValhallaVintageVerb** | Valhalla DSP | Algorithmic reverb (allpass diffuser → damped FDN tank; 22 modes × 3 era colors) | C++/JUCE VST3, native editor, vDSP; no PACE, DSP kernel local-stripped | **CLEAN** (pedalboard v4.0.5) — 22 reverbmodes + color seventies/eighties/now (70s=34 dB darker + alias), RT60≈1.35×decay label, bassmult=LF RT60 ×0.25–4, highshelf=HF-damping decay-EQ, predelay +9.06 ms intrinsic, pdc 0; REF=roster | [ValhallaVintageVerb.md](plugins/ValhallaVintageVerb.md) |
| **ValhallaFutureVerb** | Valhalla DSP | Serial echo + reverb multi-FX (12 echo modes incl. reverse/octave pitch, 8 reverb algos) | C++/JUCE VST3, no DRM, **stripped (3 syms)** → black-box only | **CLEAN** (pedalboard v1.0.2) — echo↔reverb serial (routing swaps order), 12 echomodes / 8 reverbmodes / 4 color, echodrive=odd soft-clip 0.01→0.33% THD, detune ±30c, decay≈RT60, loweqfreq=HP + higheqfreq=LP tail, **reserved1-8 bit-exact inert**, pdc 0; reverse/octave + tempo-sync→REAPER; no REF (wall) | [ValhallaFutureVerb.md](plugins/ValhallaFutureVerb.md) |
| **ValhallaPlate** | Valhalla DSP | Plate reverb (12 "material" algos, dense diffusion, no early reflections) | C++/JUCE, no DRM, not stripped (`VPlug_Plate` + `VMod_*`) | **CLEAN** (pedalboard v1.6.8) — 12 types (Chrome…Lithium; centroid 3.0–7.7 kHz), decay→RT60 ≈1:1, **EQ=static output shelves (NOT decay-EQ)** + baked HF damping, predelay +21.3 ms, size=early density, width=M/S to 200%, mix linear, pdc 0; REF=roster (12 `processBlock*Plate` + 2× OS siblings) | [ValhallaPlate.md](plugins/ValhallaPlate.md) |
| **ValhallaRoom** | Valhalla DSP | Algorithmic room/hall (separate ER engine + modulated tank; 3-band RT60) | C++/JUCE, no DRM, not stripped (`VPlug_Room` 12 topology kernels + `VMod_*`) | **CLEAN** (pedalboard v2.0.5) — 12 types (incl. Nostromo/Sulaco/LV-426), decay→mid RT60 1:1 (0.1–100 s), **3-band RT60: rtbass ×0.5–2 @ rtxover + rthigh ×0.1–1 @ rthighxover**, ER+late split (earlylatemix), space=size scaler, diffusion=allpass density, hi/locut tank filters, mix linear, pdc 0; REF=roster | [ValhallaRoom.md](plugins/ValhallaRoom.md) |
| **ValhallaShimmer** | Valhalla DSP | Pitch-shifted feedback reverb ("shimmer") | C++/JUCE, no DRM, not stripped; H949-style shifter inside reverb feedback loop | **CLEAN** (pedalboard v1.3.0) — shift law st=24.19·raw−12.33 (±12 st, raw.51=unison), 5 shiftmodes, **cascade f·2^k** (fb.5=−6.5 dB/oct, fb.95≈flat 6-oct tower, fb0=no regen ⇒ shifter in loop), RT60→~19 s freeze, 4 reverbmodes / 2 color, lo/hi-cut in-loop, equal-power mix, pdc 0; REF=roster (`VMod_PitchShiftH949`) | [ValhallaShimmer.md](plugins/ValhallaShimmer.md) |
| **ValhallaUberMod** | Valhalla DSP | Multi-tap modulated delay (chorus/flanger/ensemble/echo/Dimension-D superset) | C++/JUCE+WebKit, no DRM, not stripped; `VPlug_Chorus` over shared `VMod_DelayLine` | **CLEAN** (pedalboard v1.2.8) — **type 0-24 but only 0-9 active** (10-24 bit-exact dry = NULL trap), tap ladder 1·1·2·3·3·3·4·8·8·16, detune=dual ±pitch (±37c@2k, Δf∝carrier), overmod 100×→±1083 Hz (through-zero), drive=odd soft-clip THD 1.1→30%, feedbackrotate 0=mono/50=mix/100=pingpong, lo/hi-cut in-loop, pdc 0; delaysync→REAPER; REF=roster | [ValhallaUberMod.md](plugins/ValhallaUberMod.md) |

Type taxonomy: **Limiter** (Pro-L2, AL-1, ML4000_ML1, ML8000, **Ozone 11 Maximizer**) · **Compressor/Leveler** (AC-1, Pro-C 3) · **Compressor/Crusher** (Devil-Loc, Devil-Loc Deluxe) · **Gate/Expander** (Pro-G) · **De-esser** (Pro-DS) · **Dual-band dynamics/de-esser** (Weiss DS1-MK3) · **Program EQ** (AE-1a/b/p) · **Parametric EQ** (Pro-Q 4) · **Musical EQ** (SieQ) · **Reverb** (Pro-R 2, **SuperPlate / LittlePlate** — plate, **SpaceBlender** — ambient, **ValhallaVintageVerb** — algorithmic 22-mode, **ValhallaSupermassive** — FDN delay/reverb, **ValhallaPlate** — plate 12-algo, **ValhallaRoom** — room/hall 3-band-RT60, **ValhallaShimmer** — pitch-shift shimmer, **ValhallaFutureVerb** — echo+reverb) · **Delay** (Timeless 3, **EchoBoy / EchoBoy Jr.** — multi-style echo, **PrimalTap / Little PrimalTap** — lo-fi, **Crystallizer** — granular pitch-echo) · **Frequency shifter** (**ValhallaFreqEcho** — SSB Hilbert + barberpole echo) · **Flanger / barberpole / multi-tap modulation** (**ValhallaSpaceModulator** — Doppler-ramp, **ValhallaUberMod** — multi-tap modulated delay/chorus) · **Phaser** (PhaseMistress) · **Tremolo / Auto-pan** (Tremolator, PanMan) · **Modulating filter** (Volcano 3, **FilterFreak1/2** — analog SVF) · **Pitch / formant** (MicroShift, LittleMicroShift — widener; **LittleAlterBoy** — pitch+formant) · **Saturation/Distortion** (AS-1, Saturn 2, **Decapitator** — 5-model, **Radiator / LittleRadiator** — Altec tube) · **Clipper / sidechain-FX** (FLVTTER) · **Multiband dynamics** (Pro-MB, ML4000_ML4) · **Multi-FX dynamics** (MELD) · **Multiband splitter/router** (Gaffel) · **Container / FX host** (Soundtoys **EffectRack**) · **Synthesizer/instrument** (Twin 3, **Diva** — polyphonic VA) · **Shell / shared DSP engine** (Waves WaveShell 16.8 — 215-plugin host, AlgType-dispatched).

**Cross-plugin finding (Soundtoys, 2026-06-26):** all 23 V5.5 plugins statically link ONE shared **"Soundtoys" framework** (dup ObjC classes `SoundtoysCocoaView`/`AuxWindow`/`LEGACY_SYNC_*` across binaries) — the **static-linked-shared-engine archetype** (cf. NI "Effekt Rig"): load one plugin per process. AAX = PACE-wrapped, but **VST3 is pedalboard-hostable** (no headless SIGKILL) → black-box CLEAN. **Harness gotchas:** (a) mode/style enums latch **one block late** → warmup-render (`st_sysid.render_settled`); (b) a few *structural* params (EchoBoy `style`, EchoBoyJr/PrimalTap `feedback`, PrimalTap `freeze`) and **all tempo-sync/rhythm** modes need a host suspend/resume or transport pedalboard can't issue → **deferred to REAPER** (ReaScript Apply-FX/Freeze, see easby-decomp DRM playbook). Harness: `private-research/Soundtoys/Tools/st_sysid.py` (+ per-type `*_probe.py`).
**Cross-plugin finding (Valhalla DSP, 2026-06-27 — 9 plugins, 2 batches):** FreqEcho, SpaceModulator, Supermassive, VintageVerb (batch 1) + FutureVerb, Plate, Room, Shimmer, UberMod (batch 2). All JUCE VST3, universal, **no PACE/DRM** → pedalboard black-box CLEAN. **Archetype = shared SOURCE toolkit, NOT a shared binary/bundle** (distinct from FabFilter-core / Waves-shell / iZotope-monolith / NI-static-link): a vendor C++ library **`VMod_*`** (`DelayLine` w/ allpass/linear fractional interp, `Biquad`, `TriOsc` LFO, `Rotate` stereo matrix, `Up/Downsample`+`IIRPolyphase` OS, specialized `PitchShiftH949` (Eventide-style, Shimmer), `DiffChorus`/`DiffChorus2` (Shimmer/UberMod)) is **statically compiled into each plugin** under a per-plugin `VPlug_<Name>` engine with hidden visibility → **0 *exported*-symbol overlap** (each binary self-contained) but the **`VMod_*`/`VPlug_*` class names recur in every non-stripped roster** (the tell). Strip state: FreqEcho/SpaceMod/VintageVerb/Plate/Room/Shimmer/UberMod NOT stripped (REF roster ~8–11k syms; VVV kernel *local*-stripped) → architecture-name REF only; **Supermassive + FutureVerb fully stripped (3 syms) = static wall, black-box only**. **Recurring CLEAN patterns:** (a) **inert "reserved" params** ship in the UI but are bit-exact dead — Supermassive `reserved1-4`, FutureVerb `reserved1-8`, and UberMod's **`type` 0-24 where only 0-9 are live DSP (10-24 = bit-exact dry)** — always null-test param tails. (b) **enum counts are routinely undercounted by an 11-pt taper** — re-enumerate at `--taper-n 96` (FutureVerb 12 echo/8 reverb not 6/4; Plate 12 not 6; Room 12 not 10). **Harness gotcha (FreqEcho only):** wet Hilbert/SSB path intermittently NaNs on cold start (~10%), sticky per-process (2nd render corrupts state) → harness renders **once per process** + auto-reexecs a fresh subprocess on non-finite; all others stable. **ES-X/ES-L KB notes:** (1) "barberpole" = **Doppler-ramp pitch-shift** (Δf ∝ carrier, modulated delay; SpaceMod + UberMod `overmod`→through-zero), distinct from FreqEcho's true constant-Hz **Bode/Hilbert SSB**. (2) **Pitch-shift-in-feedback-loop = shimmer** (Shimmer: f·2^k octave cascade; fb→tower flatness). (3) **Frequency-dependent RT60** is the room-realism blueprint — VintageVerb (`bassmult`+`highshelf`) and esp. **Room's 3-band model** (`rtbass ×0.5-2` + `rthigh ×0.1-1` about two crossovers). (4) Valhalla reverbs **decay≈RT60 ~1:1** (VVV is the exception at 1.35×); EQ may be **static output** (Plate) vs **decay-rate** (VVV) — measure which. Off-axis from ES-L dynamics (mix/master FX, like Diva). Harness: `private-research/Valhalla/Tools/valhalla_sysid.py`.
(ES-L is built FROM these references — not a KB entry; it consumes BuildSpec, never stores REF.)

## How to use for implementation
1. Open the plugin's spec; read the **signal chain** + per-stage **formula** (CLEAN rows only for product).
2. Map params (units! seconds vs ms, normalized vs dB) — see each spec's param table.
3. Reuse shared building blocks across plugins (e.g. AC-1's `RmsLift` = one gain computer used for both
   comp + maximizer; many limiters share a dB-domain smoother + true-peak ceiling).
4. For ES-L specifically: build from CLEAN measurement + public literature + ES-L voicing. Never cite REF.

## Output contracts (structured JSON for the C++/Rust DSP engine)
Like Producer→Mixing→Mastering, this skill emits structured JSON. Two artifacts, one firewall between them.

### 1. `PluginSpec` — internal, full knowledge (CLEAN + REF). Never handed to a product.
```json
{
  "type": "PluginSpec",
  "plugin": "AC-1", "vendor": "Naturl Audio",
  "category": "compressor_leveler",            // limiter | compressor_leveler | multifx_dynamics | saturation
  "signal_chain": ["detector","gain_computer","link_smoother","maximizer","true_peak_ceiling"],
  "stages": [
    { "id": "gain_computer", "name": "RmsLift",
      "provenance": "REF",                     // disasm-derived → stays internal
      "formula": "g=min(10^(svf2(svf1(max(0,target-rms_db)))/20), max_gain, ceiling)",
      "constants": {"deadband": 1e-9},
      "params": [{"id":"ratio","unit":"ratio","range":[1,20],"note":"ratio-insensitive (leveler)"}] }
  ],
  "measurements": [                            // CLEAN — always allowed downstream
    {"probe":"static_curve","provenance":"CLEAN","data":{"thr_db":-30,"r4":{"-12":-3.8,"0":-5.2}}} ],
  "ffi": {"create":"create(sample_rate:f64)->handle","process":"process(h,in*,out*,len)"}  // REF/diagnostic
}
```

### 2. `BuildSpec` — product-facing emission. **CLEAN-only by construction.**
```json
{
  "type": "BuildSpec",
  "target_product": "ES-L",
  "source_plugin": "AL-1",
  "provenance_gate": "CLEAN_ONLY",
  "stages": [
    { "id": "limiter_core",
      "behavior_targets": [                    // CLEAN measurements only — the spec to MATCH
        {"probe":"gain_law","ceil":0.9886,"knee":"hard","release_db_per_sample":0.272,
         "attack_slew_db_per_sample":2.18,"combine":"pure_max_lookahead","source":"black_box"} ],
      "literature": ["Giannoulis et al., Digital Dynamic Range Compressor Design (JAES 2012)",
                     "Zölzer, DAFX — limiters/true-peak"],
      "voicing": "product's own identity",
      "null_test": {"oracle":"ffi_harness/pedalboard", "signal":"isolated peaks+dense tone+music",
                    "metric":"peak_weighted_null_db", "threshold_db":-36, "status":"pending"},
      "excluded_ref": ["any internal asm/formula — reproduce via behavior_targets, do not import"] }
  ]
}
```
Rules for emitting a BuildSpec:
- Pull only `provenance:"CLEAN"` facts + `literature` + `voicing`. **Drop every REF stage/formula.**
- Where a behaviour is known only from REF, emit it as a `behavior_target` *to measure* (a probe to run),
  never as a literal value. Cite the measurement once obtained.
- **Every stage carries a `null_test`** (build→verify): A/B the built stage against the reference via the
  easby-decomp harness; the residual must beat `threshold_db` before the stage is "done". `status` starts
  `pending` → `pass`/`fail`. No null_test = incomplete stage.
- Tag `provenance_gate:"CLEAN_ONLY"`; the engine rejects any BuildSpec lacking it.

### 3. `Refusal` — firewall breach
```json
{"type":"Refusal","reason":"ref_leak_to_buildspec","detail":"RmsLift formula is REF (Ghidra)",
 "redirect":"emit a behavior_target probe; measure black-box; cite the measurement"}
```
Emit when asked to put a REF value into a product/BuildSpec, or to cite the quarantine folder from product code.

## Implementation resources
- **[implementation-doctrine.md](implementation-doctrine.md)** — RT-safety + DSP-correctness checklist
  (no alloc/lock on audio thread, denormal flush, f32/f64, smoothing, latency, oversampling). Verify before commit.
- **[building-blocks/](building-blocks/README.md)** — verified public-DSP primitives (one-pole, RMS, gain
  computers, true-peak, soft-clip, biquad) that BuildSpec stages assemble. Implement once, reuse.
- **Firewall gate** — `../easby-decomp/assets/firewall_check.sh <product_src>`: CI/pre-commit check that fails
  if product code references REF/quarantine. Install hook from `../easby-decomp/assets/pre-commit.hook.tmpl`.
- **Build→verify** — every BuildSpec stage's `null_test` A/B's the clone vs reference (easby-decomp harness);
  residual must beat threshold. See AL-1.md (worst-cell −27 dB) for a worked example.

## Source folders (live research, not copied here)
`private-research/{AC-1,AL-1,MELD,Pro-L2}` — full docs/Tools/decomp. This store is the *distilled index*;
deep data stays in those folders. Quarantined disasm: `private-research/_quarantine_disasm/`.

## Adding a new plugin
Run [easby-decomp](../easby-decomp/SKILL.md), then drop a `plugins/<NAME>.md` from `plugins/_TEMPLATE.md`
and add a catalog row above.
