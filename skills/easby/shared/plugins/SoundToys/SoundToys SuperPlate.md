# SoundToys SuperPlate — SoundToys (plate reverb)

| | |
|---|---|
| Vendor / ver | SoundToys · v5.4 (manual; plugin v5.x) |
| Type | Reverb — electromechanical plate reverb (5 modeled plates + analog preamp emulation) |
| Format | VST3 / AU / AAX (Mac & Windows; iLok authorized) |
| Source | manual: `SoundToys SuperPlate/SoundToys SuperPlate.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
SuperPlate models five classic electromechanical plate reverbs (EMT 140, EMT 240, Audicon, EcoPlate III, Stocktronics RX4000) — not convolution IRs, but parametric models, so they support things no physical plate can: infinite decay, modulation, dynamic decay, and full EQ. On top of the plate you pick one of three input "preamp" colorations — Tube (EMT V54), Solid-State (EMT 162, with built-in compressor), or Clean (no coloration). Distinctive features beyond a normal plate: true stereo in/out (vs Little Plate's mono-summed input), built-in pre-delay, an expanded modulation engine (depth + rate), a two-band post EQ plus pre-reverb low/high-cut filters with selectable slopes, and **Auto-Decay** — a "ducking-like" circuit that dynamically *shortens decay time* (not level) when input exceeds a threshold, so you can play into long tails without buildup. The grown-up version of Little Plate (which is bundled).

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Decay** (main knob) | ~0.5 s → 32 s → ∞ (RT60 @ 500 Hz; red zone = extended; max non-∞ ≈ 1 min) | Reverb tail length. Short = tight/room-like; long = cavernous/boomy. Frequency-dependent, damper-modeled per plate. | The primary tone shaper. Short on drums/vocals for room; long for ambient. |
| **Infinite Decay** | knob fully CW (∞) | Tail never fades; sound keeps darkening/evolving, new input keeps feeding it. | Drones, pads, "hold" effects, live composition. **Watch levels — energy builds up.** |
| **Low** (Low Cut filter) | 20 Hz – 1 kHz, **pre-reverb** | High-pass on signal *entering* the reverb. Removes bass/mud (and up to most of the mids at extreme). | Stop low-end buildup in the tail; clean up muddy/boomy reverbs; extreme = only highs into reverb (effect). |
| **Low Cut Slope** (Tweak / EQ display) | 6 / 12 / 24 dB/oct | Steepness of the low cut. 6 = gentle, 24 = aggressive, 12 = common middle. | Click orange (L) icon at far left of EQ display, or drag it; set how hard the low cut bites. |
| **High** (High Cut filter) | 1 kHz – 20 kHz, **pre-reverb** (affects reverb input only, not dry) | Low-pass on reverb input. Darkens/smooths the tail; helps it sit under the source. | Tame sizzle, blend reverb naturally, separate reverb from source for clarity. |
| **High Cut Slope** (Tweak / EQ display) | 6 / 12 / 24 dB/oct | Steepness of the high cut. | Click orange (H) icon at far right of EQ display; set darkness aggressiveness. |
| **Pre-Delay** | 0 – 250 ms | Delays source before it hits the reverb. Adds perceived size/depth; separates source from tail for clarity. | Short = rhythmic/dynamic sources; long = big ambient spaces / special FX. |
| **Modulation** (depth) | 0 – 100% | Depth of pitch modulation in the tail. Small = smoother tail, fewer resonances; large = chorus/vibrato-like, dramatic. | Smooth resonances on keys/guitar/vocals (keep low for realism); high for synth/ambient FX. |
| **Modulation Rate** (Tweak menu) | 0.2 Hz – 8 Hz | Speed of the modulation LFO/engine (more than a plain LFO — designed to avoid warble). | Slow rates pair with higher depth for lush; faster = vibrato character. |
| **Mix** | Dry ↔ Wet (0–100%) | Blends dry + reverb. Special curve: 0→~70% mostly raises wet (dry steady, "aux-send" feel); past ~70% dry drops to zero at 100%. | Insert use: dial to taste. Aux/bus use: 100% wet (recommended). Use Parameter Lock to hold while auditioning presets. |
| **Input** | gain into preamp | Level into the selected preamp + reverb (LED meter). With **Solid-State**/**Tube** it doubles as a **drive** control (overdrive + compression / tube saturation). | Keep "in the green" for clean; push for grit/compression into the reverb (reverb signal itself stays clean, but takes on the driven character). |
| **Output** | post-reverb level (meter shows ±24) | Overall output level of the composite (wet+dry) signal. | Gain-match into the mix after in-line or aux use. |
| **Plate Style** (selector) | Classic 140 / Goldfoil 240 / Audicon / E. Plate III / Stocktronics | Chooses the modeled plate (its tonal signature + decay character). | See plate notes below — pick the color/brightness/length you want. |
| **Analog Style** (input model) | Tube / Solid-State / Clean | Preamp coloration on the way in (combinable with any plate). Tube=harmonic/saturation; Solid-State=transistor drive + fixed compressor; Clean=no coloration. | Tube for warmth/spice; Solid-State to tame transients (compression) or transistor grit; Clean for pure plate. |
| **Tweak** (button) | toggle | Opens/closes the drop-down panel housing the less-used params (Mod Rate, Auto-Decay, Stereo, EQ slopes). | Access advanced controls without cluttering the main panel. |
| **Auto-Decay: Threshold** | compressor-style threshold (red ring = input VU) | Level above which decay starts shortening. Low = constant reduction (always shorter); high = never engages. | Set around/just below peak level so the tail shortens on hits — clears room for transients. |
| **Auto-Decay: Target** | max decay-time reduction | How much the decay shortens once past threshold (the shortest target time, hit only at loudest peaks). Interacts heavily with Threshold. | Dial how aggressively peaks duck the tail length. One-way: decay only reduced, never increased. |
| **Auto-Decay: Recovery** | 1 ms – 500 ms | How fast decay returns to its normal (long) setting after input drops. | Fast = max dynamic "jump back" on punchy/dense sources; slow = ring-out tail as sparse notes fade. |
| **Stereo: Width** | mono ↔ full stereo | Stereo spread of the reverb. Max = wide (even from mono input); min = collapse to mono. True-stereo: source pan position maps to reverb position. | Narrow/mono to push reverb "back" and keep source localization; wide for big stereo wash. |
| **Stereo: Balance** | pan (L ↔ R; extremes force mono) | Pans the whole reverb image left/right; extreme settings collapse to mono. | Place a collapsed/narrow reverb at the same spot as a panned source (e.g. guitar mid-right) to preserve its location + depth. |
| **Parametric EQ Band 1** | freq + gain + Q, **post-reverb**, full-range | First parametric band on the wet signal (typical: lows/mids). | Tame mid resonances, shape the tail's body. |
| **Parametric EQ Band 2** | freq + gain + Q, **post-reverb**, full-range | Second parametric band (typical: mids/highs). | Add high-frequency sheen or surgical cut/boost on the tail. |
| **EQ Bandwidth (Q)** | wide → very narrow | Q of each parametric band. | Ctrl+scroll (Mac) / Alt+scroll (Win) on the band node — wide for musical, narrow for surgical. |
| **Output EQ On/Off** | toggle (upper-right of EQ display) | Bypasses the two **parametric** bands only; Low/High Cut filters stay active. | A/B the EQ'd vs un-EQ'd reverb. |

## Use by lens
- **Producer (create):** Pick a plate for vibe — Classic 140 (warm, the "default" plate sound) or Goldfoil 240 (darker, tighter) on vocals/keys; Stocktronics (zingy, ultra-bright 0.3 mm steel) or E. Plate III (bright, spacious — the MJ/Quincy Jones EcoPlate) on drums/percussion/brass; Audicon (punchy, sparkly) as a between option. Drive the **Tube** input for harmonic spice, push **Input** high for distorted-into-reverb character. Use **Infinite Decay + Modulation** as a sound-design/compositional tool (play into it live; automate ∞ on/off to "hold" passages). Pre-Delay long + big plate = ambient pads.
- **Mixing (balance):** Recommended workflow is an **aux/bus at 100% Mix (Wet)** — send multiple sources to one plate so they share a space, ride the return fader. Always set the **pre-reverb Low Cut** to stop bass buildup and a **High Cut** so the tail tucks under the source. **Auto-Decay** is the standout mix tool: on busy/dynamic sources (drums, plucked/strummed, lead vocal) set Threshold near the peaks so the tail ducks out of the way on hits and rings out in the gaps — keeps the mix clear without a separate ducker. Use **Width/Balance** to place a narrowed reverb at the source's pan position for localization + depth. Two **post EQ** bands to carve resonances or add air. Modulation low for natural vocal/acoustic reverb.
- **Mastering (finalize):** Not a mastering tool (it's a send/insert effect reverb). If used at all on a bus, keep **Mix** very low, **Clean** input (no added saturation/compression), modest Width, aggressive Low Cut, and conservative decay — but this is unconventional; it lives on tracks/buses, not the 2-bus.

## Notes / gotchas
- **Filter routing matters:** Low Cut + High Cut are **pre-reverb** (shape what enters the plate); the two parametric bands are **post-reverb**. The EQ display is labeled "Output" but the L/H cut nodes are shown there for convenience even though they act on the input.
- **Mix knob is non-standard:** 0→~70% behaves like an aux send (raises wet, dry steady); only past ~70% does dry fall away to silent at 100%. Most factory presets are ~100% wet.
- **Parameter Lock** (all Soundtoys plugins): Ctrl+Option (Mac) / Ctrl+Alt (Win) on a control locks it (turns red) so it won't change when switching presets — handy for holding Mix while auditioning. Not saved with preset/session.
- **Solid-State input has a fixed, non-adjustable compressor** (modeled EMT 162) that kicks in harder with louder/transient input — useful for evening out the feed into the reverb. Tube input distorts more readily than Solid-State.
- **Auto-Decay is a one-way street:** it only ever *reduces* decay time, never increases it; visual ring around Threshold shows input VU, ring around Decay shows the live reduction.
- **True stereo in/out** (unlike Little Plate's mono-summed input) — preserves stereo placement of the source through the reverb.
- **Little Plate is bundled** with SuperPlate (EMT 140 sound with infinite decay, mod, low cut — fast/simple). Little Plate owners can upgrade.
- iLok-authorized (machine/USB iLok). No oversampling/latency or CPU figures stated in the manual.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
