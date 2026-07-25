# Blue Cat's PatchWork — Blue Cat Audio (plug-in host / virtual patchbay)

| | |
|---|---|
| Vendor / ver | Blue Cat Audio · v2.6x (manual references 2.65+, MIDI preset loading v1.63, macros v2.6) |
| Type | Universal plug-in host / multi-FX rack / virtual patchbay (utility) |
| Format | VST, VST3, AU (+ AU MIDI Effect for Logic), AAX · effect + instrument versions · standalone app |
| Source | manual: `Blue Cat's PatchWork/Blue Cat's PatchWork.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A universal plug-in patchbay and multi-FX host that loads up to **64 VST / VST3 / AU or built-in plug-ins** inside a single instance in any DAW, with **serial and parallel routing**. Signal flows through a PRE serial chain → up to **8 parallel chains** (each with its own pre/post gain, phase flip, solo, and bypass) → a POST serial chain, with a global dry/wet mix. It does the job of a flexible channel strip, parallel-processing rack, effects chainer, virtual buss, or multi-synth host — and lets you save whole chains (including layouts and third-party plug-in state) as presets that recall instantly and are **shared across DAWs** (any plug-in format → AAX, AU, etc.). Distinct features: built-in internal MIDI routing between hosted plug-ins, per-slot audio I/O remapping, per-slot oversampling, macro controls mapping multiple sub-params to one knob, multicore parallel processing, latency compensation, and 30 bundled built-in effects.

## Controls (every param → musical effect)
Note: PatchWork hosts *other* plug-ins, so most "controls" are routing/host structures rather than DSP knobs. The global, mappable, and per-slot controls are below.

### Global controls (main toolbar + rack)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Main Bypass (power) | on/off | Smoothly bypass the whole PatchWork instance | A/B the entire rack against dry |
| Mix (dry/wet) | 0–100% | Blends original input with the processed (wet) signal. Split happens at input; mix stage is at output | Parallel/NY compression, blending any wet chain back |
| Input Gain | dB (+ lock) | Trim feeding the PRE chain; metered right after this stage. Lock = unchanged on preset load | Gain-stage into level-dependent plug-ins |
| Output Gain | dB (+ lock) | Trim after all processing, before mix stage; output metered after mix. Lock = unchanged on preset load | Make-up / final trim |
| Link Pre/Post Gains | on/off | Global + per-chain: pre-gain changes are compensated by post-gain (drive without louder output) | Push saturation/comp without volume bias |
| Slots size | small / medium / large | Visual size of plug-in slots | UI ergonomics |
| Columns | count | Number of matrix columns; **≤2 columns disables parallel chains** | Switch between channel-strip vs parallel rack |
| Rows | count | Number of matrix rows; **single row = no parallel processing** | Add/remove parallel chains |
| Level meters | show/hide | Input/output (+ aux/side-chain) peak meters | Monitoring |
| Multicore | on/off (per preset) | Spreads parallel-chain processing across CPU cores | Many heavy parallel plug-ins; test vs off for low-CPU racks |
| CPU / Workload meter | % (avg / peak) | Real-time workload; orange→red as peak grows; >100% too long = dropouts | Watch headroom |
| Summing Mode | Average / Sum | **Average** = parallel chains averaged (gain-compensated, avoids buildup when adding chains, best for FX). **Sum** = chains summed like console busses, no compensation (best for mixing multiple synths so muting a chain doesn't change others' level) | Average for effects; Sum for multi-synth |
| Transport / Tempo | — | Play/record/tempo (standalone app only) | Standalone use, recording |
| Audio Recorder / ARM | — | Record output to WAV with BWF timestamp (standalone only) | Capture in standalone |
| Window Opacity | 0–100% | Transparency of the plug-in window | UI overlay convenience |

### Per parallel chain (×8)
| control | what it does | when to reach for it |
|---|---|---|
| Chain activate | Enable/disable the whole chain | Turn a parallel path on/off |
| Pre-gain | Input trim for that chain | Balance parallel paths |
| Post-gain | Output trim for that chain | Balance / make-up per chain |
| Phase Flip | Reverses polarity of the chain (×-1) | Fix phase issues; compute A−B difference (null testing an FX) |
| Solo | Mutes all other non-soloed chains | Audition one chain |
| Exclusive Solo (A) | Only one chain can be soloed at a time | Quick chain A/B comparison |

### Per plug-in slot (right-click menu)
| control | what it does | when to reach for it |
|---|---|---|
| Bypass (power) | Toggle bypass for that slot | Mute one effect in a chain |
| Show/Hide / Center Editor | Open, close, or recenter the hosted plug-in's UI | Tweak a hosted plug-in |
| Load VST / VST3 / AU · Select (favorites) · Paste / Paste with Map · Relocate | Insert/replace/recall a plug-in (Relocate re-links a "Missing Plug-in" while keeping its saved state) | Build the chain; restore sessions on other machines |
| Cut / Copy / Remove / Rename / Set Color | Manage the slot (copy carries full plug-in state across instances/apps) | Reorganize the rack; label by routing |
| Presets | Access hosted plug-in's native presets (fxb/fxp/vstpreset/aupreset) | Recall sub-plug-in patches |
| **Params Map** | Map sub-plug-in params to PatchWork's Control 01–40 (Map All / Learn / Learn Once / per-param toggle) | Expose buried params to host automation/MIDI/control surface |
| **MIDI Input / Output** | Route slot MIDI: **Host** (default) or virtual **Port A–P**; input channel-filterable (All/1–16) | Internal MIDI chaining (arp→synth, env-follower→filter) |
| **Audio I/O** | Per-slot input/output channel mapping (Automatic, or manual N-in/N-out with per-channel assign + "Mute unused channels") | Multi-mono, aux sends, side-chain feeds, surround subsets |
| **Oversampling** | None / 2× / 4× / 8× / 16× · Fast / Normal / Best quality | Tame aliasing on non-linear sub-plug-ins; smoother EQ highs |
| Track Undo | Toggle whether slot changes enter PatchWork's undo history | Disable for MIDI-controlled plug-ins (avoids undo spam / CPU) |

### Macro / assignable controls (Params Map Editor)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Control 01–40 | up to 40 knobs/buttons | Each maps one or many sub-plug-in params (across multiple plug-ins) into a single host-exposed control | Build macro knobs / automate buried params |
| Per-assignment Min / Max | param range | Scales (and inverts, if Min>Max) each mapped param's range | Sculpt macro response, reverse direction |
| Control Type | Knob / Button | Control style; right/alt-click sets default/neutral value | Switch / continuous behavior |
| Controls Style | Small / Modern Silver/Black / Vintage / Chicken / Stove / Skirted / Silver Top | Visual skin of the assignable knobs | Cosmetic |
| Response curve / MIDI CC | per control | Mapped controls have full Blue Cat param options: response curve, MIDI learn/CC, automation enable | Wrap a non-MIDI plug-in for MIDI control |

## Use by lens
- **Producer (create):** Use the **instrument** version to stack multiple synths — one synth per parallel chain, all played from one MIDI track (use **Sum** mode so muting a chain doesn't change levels). Add MIDI arpeggiators/effects in PRE slots and route them via internal **Port A–P** to drive different synths from one keyboard. Build a custom "instrument" by collapsing a deep chain into a few **macro** knobs, save as a preset. Route an instrument's aux outs to specific channels for per-voice processing.
- **Mixing (balance):** As a **custom channel strip** (single column, serial chain: EQ → comp → saturator → meter), or as a **parallel-processing rack** (parallel comp / Motown bus, multiband-style splits via I/O routing). Drop any plug-in with a side-chain in and feed it via per-slot Audio I/O. **Phase-flip A−B null** to hear exactly what an effect adds (empty dry chain B flipped vs processed chain A). A/B competing chains with **Exclusive Solo**.
- **Mastering (finalize):** Serial mastering chain hosted in one instance with global pre/post gain **Link** for drive-without-volume; use **Average** summing for any parallel work. Enable per-slot **Oversampling** on non-linear masters (clipper/saturator/limiter) to reduce aliasing. Share the exact chain across DAWs/formats via preset (e.g. build in VST3, recall in AAX/Pro Tools). Mind reported latency on parallel chains (some hosts need transport restart).

## Notes / gotchas
- **Two versions:** effect version adds an **external side-chain input**; instrument version adds **multiple aux outputs (up to 16 ch)**. AU also ships an **MFX** (MIDI Effect) variant for Logic. Pick instrument if hosting VSTi/MIDI FX, effect otherwise.
- **Side-chain & aux are passed *dry* by default** and are **unaffected by mix/phase/gain** controls — they follow the signal flow but bypass processing unless you manually re-route them with per-slot Audio I/O.
- **Multichannel:** up to 8 ch (surround). A plug-in that processes fewer channels passes the rest through to the next slot. **Mono plug-ins** in auto mode process ch 1 and copy the wet mono to all main-bus channels — use manual Audio I/O to constrain.
- **VST path:** set the VST2 plug-ins directory in **Preferences** before loading VST2 (used for load dialog default *and* as the relative root for portable preset recall). Does **not** affect VST3 paths. 64-bit host loads only 64-bit plug-ins (and vice-versa) without bridging.
- **Latency compensation** is per-chain and reported to the host, but some hosts (Cubase, Sonar, Studio One, Pro Tools ≤10) may need plug-in re-activation or transport restart. Latency is also compensated on unprocessed channels, but only at the *end* of each chain — be careful with heavy I/O remapping + latent plug-ins.
- **Oversampling warning:** some third-party plug-ins misbehave at higher sample rates — save before enabling. High-quality resampling adds latency + CPU. Tip: to oversample a whole chain, host the **built-in PatchWork** in a slot and oversample that.
- **Track Undo:** disable per-slot when a plug-in is fed by MIDI CC generators (e.g. Blue Cat DP Meter Pro / Remote Control) to avoid undo-history flooding and extra CPU; some plug-ins also don't restore correctly with it on.
- **Presets:** factory categories — Channel Strips, Delays, Modulation, Other FX, Pitch, Reverbs; notable: *Chains Compare*, *Chains Diff*, *Default*, *Default – No Undo*, *C-Strip*. MIDI preset loading (Bank Select + Program Change) since v1.63. Presets store window layout + each hosted plug-in's editor position.
- **Drag & drop:** plug-ins between slots (copy with Alt/Mac, Ctrl/Win), drop-before-to-insert, and drop `.vst/.vst3/.component/.dll` or saved `.plgnfo` files from Finder/Explorer onto slots.
- **30 built-in effects** (use without third-party deps): Bit Crusher, Chorus, Comb Filters, Compressor, Ducker, Echo, Multitap Delay, EQ, Multimode Filter, Flanger, Frequency Shifter, Gain, Gate, Stereo Pan, Phase Shifter, Phaser, Pitch Shifter, Stereo Strip, Sweep Filter, Tremolo, Waveshaper (+ more). PatchWork itself is loadable as a built-in (Utility) → "Patchwork of Patchworks" for modular reuse.
- **MIDI routing limits:** no feedback loops; a slot can only receive MIDI from plug-ins *earlier* in the audio flow (or in parallel chains above it) — guarantees causality/zero-latency MIDI.
- **Demo:** 5 instances per session; effect bypassed 0.5 s every minute.

## Deep spec (Programmer only)
not reverse-engineered — capability only. (PatchWork is a plug-in host/router, not a measured DSP plugin; no `easby-programming/plugins/` entry exists or is warranted.)
