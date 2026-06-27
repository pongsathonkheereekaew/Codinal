# MBS MELD — Make Believe Studios (channel strip / immersive glue)

| | |
|---|---|
| Vendor / ver | Make Believe Studios (w/ Metric Halo) · v4.0.86 (manual rev) |
| Type | Channel strip: EQ + MixHead saturation + Compressor + Loudness + Limiter, with cross-instance group linking |
| Format | AU / VST3 / AAX (Mac & Windows) |
| Source | manual: `MB MELD/MBS MELD.pdf` · deep spec: `easby-programming/plugins/MELD.md` (RE'd) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
MELD is a channel-strip plug-in built for immersive (Atmos) mixing: it bundles the EQ, Compressor and Limiter from Metric Halo ChannelStrip plus Make Believe Studios MixHead (tape saturation), and adds a new **Loudness** density processor. Its distinctive trick is cross-instance grouping: you insert MELD on every track that used to feed a stereo submix, assign those tracks to a MELD **group (A–Z)**, and every instance applies *identical* processing without any bus routing — so the tracks stay discrete and can be panned freely through the immersive field while still sharing the "glue" of a submix. **Shared Sidechain Support** (CSC/LSC) links the comp/limiter detectors across the group so they all react to the loudest track, emulating bus compression while keeping each track's articulation. It works equally well as a normal mixing/mastering strip on stereo material.

## Controls (every param → musical effect)

### Input / Output strips (group-wide)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Input Fader | +20 dB → −∞ | input gain into the processing chain, applied to all tracks in group (always on unless master bypass) | drive into comp/sat or trim level |
| Polarity | on/off | inverts input polarity for whole group (yellow = on) | phase fixes against other mics/stems |
| DC Block | on/off | 1 Hz high-pass (−∞ at 0 Hz), applied after input gain/polarity | kill DC offset / subsonic rumble |
| Output Fader | +20 dB → −∞ | post-chain group output level (always on unless master bypass) | final make-up / gain-stage to next plug-in |

### EQ block (12-band parametric)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| EQ Block Enable | on/off | bypass the whole EQ (lit = active) | A/B the EQ |
| Band Enable (×12) | on/off | enable each filter band individually | turn bands in/out |
| Frequency | 20 Hz–20 kHz | center freq (peak/bandpass), −3 dB point (cuts), or shelf transition point | place the band |
| Gain / Boost-Cut | peak ±24 dB; shelves +12 / −24 dB | boost/cut for peak & shelf types (ignored on cut/bandpass); >+15 dB peak gets resonant | tonal shaping, resonance reconstruction |
| Bandwidth (BW) | 0.1–2.5 octaves | filter width in **octaves** (small = narrow); on shelves sets the dip/peak at transition (0.1 = max, 2.5 = 1st-order shelf) | surgical vs broad; note: inverse of "Q" |
| Filter Type | Peak / Low Shelf / High Shelf / High Cut / Low Cut / Bandpass | per-band response. Cuts = 12 dB/oct; Bandpass = 6 dB/oct skirts | choose band behavior |
| EQ display scale | ±3 / ±6 / ±12 / ±24 / ±36 dB | vertical zoom of transfer graph (right-click) | read fine vs large moves |
| Auto Enable Bands | pref on/off | auto-enables a band when you touch its params | quick build vs deliberate |
| Spectragraph (SpectraFoo) | on/off | post-filter realtime analyzer overlaid on EQ curve (L/R instant + average traces) | see what you're EQ'ing |

*Note: loads MH ChannelStrip EQ presets into the first 6 of the 12 bands.*

### MixHead block (tape saturation)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| MixHead Block Enable | on/off | bypass MixHead | A/B the saturation |
| Input Gain | −12.0 to +12.0 dB (0.1 steps) | pre-process "line-in to tape" level; interacts heavily with Drive | set how hard you hit the virtual tape |
| Drive | −7 to +14 (0 = +7 dB-to-tape ref) | amount of harmonic distortion/saturation (non-linear, needs output comp); high = serious breakup | grit, glue, harmonic density |
| HF-Adjust | −6 (max cut) to +6 (max boost) | high-freq cut/boost independent of Drive; automatable | tame/boost top; low-drive boost = vintage exciter |
| Output Gain | −12.0 to +12.0 dB (0.1 steps) | post-process make-up; Ctrl-Shift-drag inverse-links to Input Gain | loudness compensation, avoid clipping next stage |
| Tape Speed | 15 / 30 / 3.75 ips | model select: 15 = default + subtle stereo widen; 30 = lower distortion, more headroom (no 40–70 Hz bass dip); 3.75 = 1950s Webcor, big headbump + more distortion | choose tape character |

*Note (as MELD block): no hard clip on output (passes >0 dBFS to next stage); standalone MixHead "Advanced Parameters" not included.*

### Compressor block
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Comp Block Enable | on/off | bypass compressor | A/B |
| Character | Smooth / Warm / Fast / **MIO** (default) | algorithm voicing — Smooth: transparent (full mixes); Warm: versatile balance; Fast: max transient control (+distortion, 1-sample attacks); MIO: detector-driven, can act as comp/limiter/leveler, most flexible | match program / transient content |
| Threshold | dB (e.g. down to ~−60) | level where gain reduction starts; soft knee, ratio rises with overshoot (white ∇ in graph) | how much of signal gets compressed |
| Ratio | up to 1000:1 | terminal ratio; at 1000:1 acts as soft-knee tube limiter (white O handle) | gentle leveling vs limiting |
| Knee | −0.5 to +1 (**MIO only**) | shape: 0 = hard, →1 = soft, negative = "kink" at threshold (good on percussive/FX) | fine-tune knee feel |
| Auto Gain | on/off | auto make-up (~7 dB for 0 dB GR); manual Gain then becomes a trim (only ~1–2 dB at low thresholds) | hands-off level match |
| Attack | 0–500 ms | gain-reduction onset; 8-sample lookahead gives "instant attack" at 0 (in MIO drives the detector) | catch vs let-through transients |
| Release | 5 ms–5 s | recovery; <~40 ms can sound abrupt; avoid faster than attack | pumping vs smooth |
| Gain (make-up) | dB | manual make-up after GR (or trim on internal auto-gain when Auto Gain on) | restore level |
| GR meter scale | 0–54 / 24 / 12 / 6 / 3 dB | gain-reduction meter range (right-click) | read small vs large GR |

*Note: loads MH ChannelStrip compressor presets.*

### Loudness block (density processor)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Loudness Block Enable | on/off | bypass Loudness | A/B |
| Threshold | 0 to −12 dB | how far below peak the processor reaches to raise average level / apparent loudness while leaving peaks alone (white ∇) | even out quiet moments, push perceived loudness in the Atmos LUFS range |

*Distinct from the limiter — raises density, not a brickwall. Great for smoothing vocal/acoustic performance dynamics.*

### Limiter block (brickwall)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Limiter Block Enable | on/off | bypass limiter | A/B |
| Threshold | 0 to −12 dB | ceiling where limiting begins; auto make-up keeps max output at 0 dB (complementary gain as you lower it) | catch peaks / push level |
| GR meter scale | (right-click) | gain-reduction meter range | read limiting amount |

### Group / Track List & advanced
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Processor tab Enable (×5) | on/off | per-block bypass (EQ/Comp/MixHead/Loudness/Limiter); Overview master Enable = whole-plugin bypass | quick block toggles |
| Tab order (drag) | — | click-drag tabs to re-sequence the 5 blocks in the signal chain | reorder processing |
| Group assign (A–Z) | 26 groups | Track Selector column / A·B·C shortcut buttons assign tracks to a group; all instances in a group share settings | build immersive submix groups |
| Ena (per group) | on/off | enable/disable MELD processing per group (bypass) | mute group processing |
| S / M | on/off | group Solo / Mute | monitor / silence group |
| Trim(I) / Trim(O) | dB | **un-linked** per-track input/output trims (independent of group) | balance individual tracks within group |
| **Shared Sidechain — CSC** | on/off | links all group compressor detectors to highest peak in group ("glue" of a stereo bus) | bus-style comp glue across panned tracks |
| **Shared Sidechain — LSC** | on/off | links all group limiter detectors to highest group peak | unified limiting across group |
| Reference (R) | on/off | mark track as reference → Short/Long LUFS + True Peak readout in LUFS Bar | metering vs a reference |
| A/B/C snapshot + Blend | — | header snapshot registers with morph/blend between them | compare settings |
| Oversampling | multiplier | header oversampling selector | reduce aliasing on heavy sat/limiting |
| Soft Bypass | on/off | header bypass | true compare |

## Use by lens
- **Producer (create):** Reach for it as an all-in-one strip — MixHead for tape grit/glue, EQ to shape, MIO comp + Loudness to even out a vocal or DI. The A/B/C group shortcuts make building harmonized BGV/guitar-stack groups fast: one instance per track, assign to a group, dial once → applies to all. Drag tabs to put saturation before/after EQ for different colors.
- **Mixing (balance):** This is its home turf. Replace aux/folder/sub-master buses: insert on the feeding tracks, group them, and your "submix" processing prints with the stems while tracks stay independently pannable. Use per-track Trim(I)/Trim(O) to balance within the group, CSC for bus-style comp glue without losing localization, Reference tracks + LUFS Bar to hit targets. Use Loudness to smooth performance dynamics before the limiter.
- **Mastering (finalize):** On a stereo master, classic chain order — EQ → comp (MIO, gentle ratio / high ratio for limiting) → Loudness (density) → brickwall Limiter to ceiling. MixHead at low Drive for analog cohesion / parallel high-passed crunch. Oversample for clean limiting. Loudness is tuned for the immersive/broadcast LUFS range; the limiter auto-gains to 0 dBFS.

## Notes / gotchas
- **BW is in octaves, not Q** — small numbers = narrow (inverse of Q-based EQs).
- **MIO is the default comp** and the only mode with a usable Knee; ratio 1000:1 turns the comp into a tube-style limiter.
- **Auto Gain caps manual make-up** to ~1–2 dB at low thresholds (internal limitation) even though the knob reads up to +30.
- **Shared Sidechain (CSC/LSC)** is the key immersive feature — bigger the subgroup, bigger the glue benefit. Off by default; toggled via the Advanced Parameters button.
- **MixHead in MELD never hard-clips** its output (feeds the next high-res stage) and omits the standalone MixHead Advanced Parameters.
- Loadable presets: EQ/Comp accept MH **ChannelStrip** presets (EQ → first 6 bands only); MixHead accepts MB **MixHead** presets.
- All instances in a group track one master instance; automate one → automates the whole group. Up to **26 groups (A–Z)**; 7.1.4 instance shows 12 PPM channels.
- Designed to be **light on CPU** (intended at the end of an already-loaded mix-bus chain) and version-stable (old sessions not broken by updates).

## Deep spec (Programmer only)
`easby-programming/plugins/MELD.md` — measured DSP: MixHead = odd-order symmetric soft-clip (`y = x − k·x³` / `tanh(g·x)/g`, drive-dependent); MIO comp curve + normalized Frequency/Ratio param map; Loudness = soft-clip density maximizer distinct from the true-brickwall Limiter. CLEAN render-based (DRM blocks static).
