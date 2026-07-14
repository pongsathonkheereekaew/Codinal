# MH ChannelStrip 4 — Metric Halo (channel strip: gate/expander + compressor + 6-band EQ + limiter + delay)

| | |
|---|---|
| Vendor / ver | Metric Halo · v4.0.2 (manual rev 4.0.2, Apr 2024) |
| Type | All-in-one channel strip — phase invert, input gain, expander/gate, compressor, 6-band parametric EQ, channel delay, limiter |
| Format | AAX (Pro Tools, Native only), AU, VST2, VST3 · macOS 10.9+ (Intel/Apple Silicon), Win 10+ · 64-bit · iLok |
| Source | manual: `MH ChannelStrip 4/MH ChannelStrip 4.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
ChannelStrip is the classic "console channel" in a plug-in — the tool Metric Halo built its reputation on across 25+ years of hit records (Serban Ghenea uses nothing else). One window gives you the full chain a mixing-console strip provides: phase invert → input gain → delay → expander/gate (with filtered sidechain) → compressor (4 characters incl. the MIO algorithm, with filtered sidechain) → fully-parametric 6-band EQ → master gain → brickwall limiter. What sets it apart: the **compressor and EQ order is switchable on the fly** (Post EQ button) so you can audition pre-vs-post-EQ compression without stopping transport; each dynamics block has a **single-band sidechain EQ** (turning the gate into a frequency-conditional trigger and the compressor into a de-esser/ducker); the EQ filters are unusually low-ring (minimal time smearing); and the whole strip carries SpectraFoo metering — input RMS/peak meters, dynamics knee graphs with bouncing-ball, gain-reduction meters, an EQ transfer-function display with overlaid realtime spectrograph, and Peak/RMS/VU output metering.

## Controls (every param → musical effect)

### Header / global (shared MH chrome)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Master Enables | per-section on/off (ø Inv, Gate, Comp, EQ, Limit) | toggle each processing block; section order in the row follows Post-EQ state | bypass a stage while keeping its settings |
| A / B snapshot registers | 2 registers + Blend | hold two full settings; Blend morphs between A and B | compare two treatments, interpolate between them |
| Undo / Redo | — | step plug-in parameter history | back out of an experiment |
| Compare | toggle | A/B against the state when you opened the plug-in | check you actually improved it |
| Soft Bypass | toggle | click-free bypass of the whole plug-in | true vs processed reference |
| Graph Visible selector | show/hide | open/close EQ + dynamics graph displays | shrink UI when graphs not needed |
| UI Size selector | % scale | resize the whole interface | fit your screen / retina |
| Preset menu + step buttons | factory/user presets | recall, step through (audition-on-select) | starting points; de-esser presets noted |

### Input conditioning
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| ø Inv (Phase Invert) | on/off | flips polarity; cross-faded so no click | multi-mic phase, stereo issues |
| In Gain | −24 dB … +24 dB (Plus/Minus knob, 12 o'clock = unity) | trims level into the strip; note: pad is *after* input, won't tame pre-strip/AD clipping | drive the dynamics/EQ hotter or pad a hot source |

### Gate / Expander (filtered sidechain)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Gate Enable | on/off (Master Enables) | engages the gate | — |
| Thresh | dBFS (Swept knob; also red slider on input meter) | level where gate opens/closes; below threshold gain reduced at fixed **1:2 expansion ratio** | set just under the wanted signal floor |
| Attack | Auto or 0–100 ms | how fast gain returns to 0 dB when signal crosses threshold; **Auto** scales attack by how far above threshold; manual delays trigger / removes initial transient | Auto for natural gating; manual when using gate as trigger |
| Release | 5 ms … 5 s | how fast gate closes after signal drops below threshold; below ~90 ms can chatter | longer for smooth tails, short for tight gating |
| Sidechain Routing (C / SC) | C = internal / SC = external key | C keys off the channel; SC keys off DAW sidechain bus (silence = never opens) | acoustic triggers, keyed gating |
| Sidechain Listen (speaker) | on/off | monitor the post-filter detector signal | dial in the sidechain filter by ear |
| SC Ena (sidechain filter) | on/off | inserts the 1-band sidechain EQ into the detector path | make gate frequency-sensitive |
| SC Filter Type | 6 types (see EQ filter shapes) | shape of the single sidechain band | bandpass to gate on a narrow strong band |
| SC dB | peaking ±24 dB / shelf +12/−24 dB (ignored on cut/bandpass) | gain of sidechain filter band | accentuate the trigger frequency |
| SC Hz | 20 Hz … 20 kHz | center/knee/3 dB point of sidechain filter | tune to the trigger's frequency |
| SC BW | 0.1 … 2.5 oct (peaking/shelf/bandpass only; **small = narrow**) | bandwidth of sidechain filter | narrow to isolate the trigger |

### Compressor (filtered sidechain; order switchable)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Comp Enable | on/off (Master Enables) | engages the compressor | — |
| Post EQ | on/off | moves compressor **after** the EQ in the chain (default = comp first / pre-EQ) | EQ-then-compress vs compress-then-EQ, auditioned live |
| Compressor Character | Smooth / Warm / Fast / MIO | sets time-constant algorithm. **Smooth**: very clean, few artifacts, limited transient control (mixes/non-transient sources). **Warm**: most versatile, balances transient control + audibility (harmonic instruments w/ big transients, e.g. plucked bass). **Fast**: heavy transient control, adds distortion, supports ~1-sample attacks (impulsive material). **MIO**: the MIOStrip algorithm — gain reduction driven directly from detector, supports adjustable Knee, can act as limiter/leveler; factory default | pick the vibe: clean→Smooth, all-round→Warm, snappy→Fast, flexible/knee→MIO |
| Thresh | dBFS (Swept knob, **sweeps right→left**; red slider on meter) | level where gain reduction begins; soft knee by default | set to taste against program peaks |
| Ratio | up to 1000:1 ('terminal' ratio; 1000:1 ≈ tube-style soft-knee limiter) | amount of reduction once knee hardens | gentle leveling vs hard limiting |
| Attack | 0 … 500 ms (8-sample look-ahead enables "instant" attack at 0) | speed of gain reduction onset | fast to catch transients, slow to let them through |
| Release | 5 ms … 5 s | speed gain returns after signal drops; below ~40 ms can distort; keep ≥ attack | longer = transparent, short = pumping/energy |
| Knee | knee shape (**MIO mode only**; hidden in other modes) | 0 = hard knee; →1 softens toward soft-knee; negative (e.g. −0.5) adds a "kink" at threshold (good on percussion) | shape the compression onset character |
| Auto Gain | on/off | auto makeup so 0 dB input ≈ unity (≈7 dB static comp for 0 dBFS w/ default times); O Gain then becomes a trim (only ~1–2 dB headroom when on) | hands-off level matching |
| O Gain (Manual Make-Up) | makeup gain (up to +30 dB readout) | makeup applied after gain reduction; standalone when Auto Gain off, trim when on | restore level post-compression |
| Sidechain Routing (C / SC) | C = internal / SC = external | as gate; SC keys off DAW sidechain bus | ducking, keyed compression |
| Sidechain Listen (speaker) | on/off | monitor post-filter detector signal | dial in de-ess/duck filter by ear |
| SC Ena + Type / dB / Hz / BW | same as gate sidechain (6 filter types, ±24/+12−24 dB, 20 Hz–20 kHz, 0.1–2.5 oct) | 1-band EQ on the compressor detector | de-essing (bandpass on "ess"), frequency-dependent comp |

### 6-Band Parametric EQ (each band identical)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| EQ Master Enable | on/off (Master Enables) | engages EQ section; order follows Post-EQ | — |
| Band Enable (×6) | on/off per band | turns each band in/out (signal passes unchanged when off) | A/B a single move |
| Filter Type (×6) | Peaking/Parametric · Low Shelf · High Shelf · High Cut · Low Cut · Bandpass | shape per band (see filter-shape notes) | any tonal task |
| Gain "dB" (×6) | peaking: ±24 dB · low shelf: ±24 dB · high shelf: +12 / −24 dB · ignored on cuts/bandpass | boost/cut amount; **>+15 dB peaking gets aggressive/resonant** | surgical cut, broad tone shaping, resonance reconstruction |
| Freq "Hz" (×6) | 20 Hz … 20 kHz | center (peak/bandpass), 3 dB point (cuts), or transition (shelves) | place the move |
| BW "Oct" (×6) | 0.1 … 2.5 oct (peaking/shelf/bandpass; **small number = narrow**, not Q) | bandwidth; on shelves controls dip/peak + slope (0.1 = max dip/slope, 2.5 = classic 1st-order ~1-decade shelf) | narrow surgical vs wide musical |
| Band Color swatch | OS color picker | recolor band dots/knobs (mirrors prefs) | visual organization |

Filter-shape notes: **Peaking** = 2nd-order bell, resonant above +15 dB. **Low/High Shelf** = shelving; BW sets end-of-transition dip/peak. **High Cut / Low Cut** = 12 dB/oct, adjustable −3 dB point 20 Hz–20 kHz. **Bandpass** = 6 dB/oct skirts, width 0.1–2.5 oct.

### Output stage
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Master Gain (the one Fader) | −160 dB … +10 dB | master output trim **before** the limiter | gain-stage into the limiter / match levels |
| Delay | 0 … 255 samples | channel delay on output | time-align tracks, slip, automated flanging |
| Limit (Limiter Enable) | on/off (Master Enables) | engages brickwall limiter (final block) | catch EQ-boost peaks; safe mix-bus output |
| Lim Thresh | 0 … −12 dB (Limiter knob; ring shows GR right→left, full-left = 12 dB GR) | limiter threshold; **applies complementary autogain** (lower threshold → output raised) | loudness / overshoot protection |

### Metering (read-only, all SpectraFoo)
- **Gate/Comp input meters:** RMS bar (green→yellow −18→orange/red −6), floating Peak pip, 2 s Peak-Hold, white detector pip (post-sidechain-filter), red threshold slider (draggable). Top segment = clip (Option/Alt-click any meter to reset all clips). Stereo shows higher of two channels.
- **Gain Reduction meter:** orange, grows down from 0 dB; right-click to set scale 54/24/12/6/3 dB.
- **Dynamics Knee graph** (gate + comp): static transfer curve + red "bouncing-ball" showing live in/out level.
- **EQ Transfer Function:** white master curve + colored band-handle dots (drag = freq/gain; ⌘/dbl-click = toggle band; smaller dots or Option-drag = Q/BW; ⌘⌥-click = cycle filter type). Right-click → scale ±3…±36 dB, Auto-Enable-on-change, Show Live Readout, scrollwheel-BW option.
- **Spectrograph** (SpectraFoo icon, top-right of TF): white=L instant, red=R instant, yellow=L avg, blue=R avg; **post-filter** (shows EQ effect). L-only by default; L/R toggles in stereo.
- **Output meter:** Peak + Peak-Hold (2 s) + RMS (PPM ballistics) + VU (300 ms IEEE), digital OVER indicator.

## Use by lens
- **Producer (create):** One window = whole console strip while tracking ideas. Use **In Gain** + **ø Inv** for quick conditioning, the **gate** to clean up bleed (Auto attack), **Warm** compressor for character on bass/guitars, and the EQ's resonant >+15 dB peaking to *rebuild* a missing body frequency (e.g. narrow +24 dB at 60–80 Hz for kick "belly"). **Delay automation** on a duplicate = controllable flanger. A/B snapshots + Blend to explore two sounds.
- **Mixing (balance):** The core job. Per-channel gate→comp→EQ→limit with **Post-EQ** to find whether to compress before or after EQ — auditioned live. **MIO** compressor + Knee for flexible glue; **Fast** for drum transients; sidechain EQ to **de-ess** (bandpass on the "ess" into the comp detector) or **duck** (external SC key). Low-ring EQ filters cut surgically without smearing. Watch the knee bouncing-ball + GR meter to set times.
- **Mastering (finalize):** Runs clean on the mix bus — gentle broad EQ moves, **Smooth** or high-ratio (→1000:1) compressor for transparent leveling, **Master Gain** to set into the **limiter** (autogain) for overshoot-safe output. Output Peak/RMS/VU + OVER metering gives mastering-grade readout; spectrograph for tonal balance reference.

## Notes / gotchas
- **Signal order is switchable:** default is Compressor *before* EQ; the **Post EQ** button moves the compressor after EQ. The Master-Enables row reorders to reflect this. (Two block diagrams in manual: "Compressor Pre-EQ" / "Post-EQ".)
- **Compressor threshold knob sweeps right→left** (opposite the other Swept knobs) — by design.
- **BW is bandwidth in octaves, not Q** — small numbers = narrow filters (backwards from Q-based EQs).
- **High-shelf boost asymmetry:** +12 dB max boost but −24 dB cut (reflected in TF display); peaking is symmetric ±24 dB.
- **Auto Gain limitation:** with Auto Gain on, manual O Gain only adds ~1–2 dB even though readout goes to +30 dB (internal compressor limitation).
- **Sidechain "SC" with nothing routed = silence** → gate never opens / comp never compresses. Use "C" for internal keying.
- **Input pad caveat:** the −24 dB In Gain is applied *inside* ChannelStrip, after the input — it cannot undo clipping that happened in the AD converter or an earlier plug-in.
- **Clip lights ≠ plug-in clipping** — they mean DSP level is over 0 dBFS; lower level to avoid clipping a downstream processor/DAC. Option/Alt-click a meter resets all clips.
- **MIO-only Knee:** the Knee knob does nothing (and is hidden) unless Compressor Character = MIO.
- **AAX is Native-only** (no HDX/Carbon DSP); v4 installs alongside v3, settings/preset compatible, v3↔v4 switchable.
- **Latency:** compressor uses an 8-sample look-ahead; channel delay adds 0–255 samples when used. (No oversampling control exposed.)
- Part of the MH Production Bundle (shares chrome with SuperGate, Multiband Dynamics, Precision DeEsser, Sonic EQ, Character, etc.).

## Deep spec (Programmer only)
not reverse-engineered — capability only.
