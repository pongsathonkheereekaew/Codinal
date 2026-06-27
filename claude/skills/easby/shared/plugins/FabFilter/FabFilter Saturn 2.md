# FabFilter Saturn 2 — FabFilter (multiband saturation / distortion)

| | |
|---|---|
| Vendor / ver | FabFilter · Saturn 2 |
| Type | Multiband saturation / distortion (+ deep modulation matrix) |
| Format | VST, VST3, CLAP, AU (macOS), AAX Native, AudioSuite. macOS 10.13+, Intel or Apple Silicon |
| Source | manual: `FabFilter Saturn 2/FabFilter Saturn 2.pdf` · deep spec: `easby-programming/plugins/Saturn2.md` (RE'd, CLEAN black-box) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Multiband distortion/saturation: splits the signal into up to **6 frequency bands** and runs each through its own selectable distortion model (28 styles spanning tube, tape, guitar amp, transformer, plus creative FX: Smudge, Breakdown, Foldback, Rectify, Destroy). Per band you control drive, program-dependent dynamics (gate↔compress the drive), resonant feedback, a 4-band post-distortion tone stack, level, pan and dry/wet mix. What sets Saturn 2 apart is the combination of that multiband engine with a **huge drag-and-drop modulation matrix** (XLFOs, envelope generators, envelope followers, MIDI, XY controllers → almost any parameter, visualized in real-time), plus **Linear Phase** processing and a **Superb** oversampling mode that make it usable from subtle mastering warmth all the way to destructive sound-mangling.

## Controls (every param → musical effect)

### Per band (controls apply to all currently selected bands; up to 6 bands)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Style** | 28 distortion models (see list) | the distortion curve/algorithm for the band | the core tonal character — pick tube/tape/amp/transformer/FX |
| **Drive** | 0–100 % | input gain into the clipping/saturation stage; output auto-trimmed to stay sane. 0 % is *not* bypass (every style has baseline grit) | the main "how much" knob — more drive = more harmonics + compression |
| **Drive Pan** (ring around Drive) | L↔R (or M↔S) | balances drive amount between the two channels | asymmetric stereo grit; pairs well with Breakdown |
| **Dynamics** | gate ←→ compress | program-dependent drive: right = pumping compression of the saturation, left = gate/expansion (preserve transients, less low-level grit) | tame or pump the saturation by signal level; sustain vs punch |
| **Feedback Amount** | 0–100 % | feeds processed band output back into its input — ringing/howl, like amp feedback | amp-style howl, resonant grit; high settings self-oscillate toward Feedback Freq |
| **Feedback Frequency** | ringing pitch | tunes the feedback ringing frequency (think mic-to-speaker distance) | dial the pitch of the feedback tone |
| **Tone — Bass / Mid / Treble / Presence** | shelves + bell, post-distortion | EQs the *already-distorted* band signal (boosting amplifies generated harmonics) | shape brightness/body of the distortion without changing the curve |
| **Level** | −∞ to +36 dB | output level of the band | rebalance bands after distortion changes their loudness |
| **Pan** (ring around Level) | L↔R (or M↔S) | relative L/R (or mid/side) level of the band output | place/widen a band in the stereo field |
| **Mix** | 0–100 % | dry/wet for *this band* (parallel blend of clean vs distorted) | parallel saturation per band; back off harshness |
| **Enabled** | on/off | bypasses the band (passes dry input straight through) | A/B a band quickly |
| **Solo / Mute** (per band, in display) | — | solo = hear one band; mute = hear all others. Multiple allowed; automatable | isolate a band to set its drive/crossover |
| **Band Presets** | save/load | save/restore the selected band's settings (section presets) | reuse a favourite band setup |
| **Remove** | — | deletes the selected band(s) | reduce band count |

**Style list (28):** Tube — *Subtle / Clean / Warm / Broken*; Tape — *Subtle / Clean / Warm / Old*; Amp — *American Tweed / American Plexi / British Rock / British Pop / Smooth / Crunchy / Lead / Screaming / Power*; Saturation — *Subtle / Gentle / Heavy*; Transformer — *Subtle / Gentle / Warm*; FX — *Smudge* (stretch/blur), *Breakdown* (downpitch + aggressive distortion), *Foldback* (digital wavefolder), *Rectify* (rectified + DC removal + soft clip), *Destroy* (bit-crush + sample-rate reduction + clip).

### Interactive multiband display (top section, also a real-time analyzer)
| control | what it does | when to reach for it |
|---|---|---|
| **+ (add band)** | splits the current band at the mouse frequency; new band inherits settings | create a new crossover region |
| **Crossover frequency** | drag a vertical split (or drag a level button horizontally) to move the band boundary | aim distortion at a frequency range |
| **Crossover slope** | 6 / 12 / 24 / 48 dB/oct (per split) | gentle vs surgical band separation |
| **Level button (drag vertical)** | sets band Level directly; multi-select keeps relative offsets | quick balance from the display |
| Alt+drag on display | adjusts **Drive** instead of Level | drive a band straight from the analyzer |
| drag rectangle | selects adjacent bands together | edit several bands at once |
| Tip | almost everything in the display (incl. crossover splits) is a **modulation target** | modulate crossover for movement |

### Modulation sources (drag the source's drag-dot → any target; 50+ slots)
| source | key controls | what it does |
|---|---|---|
| **XLFO** (×6) | Frequency (0.02–500 Hz free, or host-synced 16→1/64 with Offset multiplier), Balance (first/last-half time skew), MIDI sync (Retrigger / Legato), Snap (arpeggiator — snaps steps to a 2-octave keyboard), Glide (global + per-step), Phase offset; per-step Value / Curve (Linear/Sqr/Sqrt/Sine) / Glide / Random | LFO on steroids — also a 16-step sequencer; steps freely added/removed |
| **Envelope Generator** (×6) | Delay, Attack, Decay, Sustain, Hold, Release + per-segment **slope** (lin/log/exp); Trigger Input (main / external SC / a band input / MIDI), Threshold (with level meter), Range (Normal 0..1 or Neutral Sustain centered on 0), Audition | ADSR envelope, triggered by MIDI note or audio level |
| **Envelope Follower** (×4) | Attack, Release; Mode (Envelope / **Transient** detector); Trigger Input (main / external SC / band); Audition | follow loudness or detect transients to drive a target |
| **MIDI source** (×10) | MIDI Input (velocity / pitch-bend / mod-wheel / …) or Controller number (any CC), Response curve (lin/exp/log/sqr/sqrt/sine) | turn MIDI data into modulation (no per-note aftertouch in VST3) |
| **XY controller / Slider** (×6) | Mode (XY = 2-D, Slider = 1-D vertical), Range (bipolar −1..1 / unipolar 0..1); X and Y drag-dots | hands-on macro control; MIDI-Learnable |
| modulation slot | Level (amount), Invert (+/−), on/off (bypass), source/target dropdowns | per-connection depth and polarity |

### Global / input-output (bottom bar + output panel)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Linear Phase** | Min Phase / Linear Phase | makes crossover filtering *and* HQ oversampling linear-phase (no phase smearing). Does **not** change the distortion styles themselves | mastering / parallel use where phase coherence matters (costs latency) |
| **High Quality (HQ)** | Off / Good (8× OS) / Superb (32× OS) | oversamples the distortion to suppress digital aliasing; more drive ⇒ more aliasing ⇒ want higher HQ | turn up when driving hard or on bright material; Superb for final renders (more CPU) |
| **Global Bypass** | on/off | latency-compensated, click-free soft bypass of the whole plug-in; analyzer freezes | clean A/B against bypassed |
| **Unrestricted Feedback (FB)** | on/off | lets feedback self-oscillate endlessly even with no input. Default OFF (feedback auto-reduced when input goes silent) | drone/howl sound design |
| **Channel Mode** | Stereo (L/R) / Mid-Side (M/S) | whether bands process L/R or Mid/Side; enables M/S distortion | widen, or saturate only the sides / only the mid |
| **Input level / pan** | −36..+36 dB | input gain + pan into the plug-in (both modulation targets) | drive harder, or trim before processing |
| **Output level / pan** | −36..+36 dB | output gain + pan (both modulation targets); pair with input gain to overdrive then trim | gain-staging / makeup |
| **Mix** (global) | 0–100 % | dry/wet of the whole plug-in (modulation target) | global parallel distortion |
| **Audition signal** | Output / Side-chain / Band 1..6 | what the solo tap listens to | check the SC or a single band |

## Use by lens
- **Producer (create):** the playground — multiband per-band styles + XLFO step-sequencer + EG/EF modulation = rhythmic, evolving distortion. Use FX styles (Foldback, Breakdown, Rectify, Destroy) and Feedback for sound design; modulate crossover splits or Drive with an XLFO for movement; Drive-Pan + M/S mode for width. Start from factory presets (Harmonic section in hosts).
- **Mixing (balance):** carve a band over the harsh range and add controlled grit (Warm Tube / Warm Tape), or saturate only the low band for weight. Per-band **Mix** + **Dynamics** (compress) for parallel "glue" saturation; envelope-follower-driven drive for level-dependent color. M/S mode to thicken the mid bass while keeping sides clean. Tone stack to brighten/darken the harmonics post-distortion.
- **Mastering (finalize):** enable **Linear Phase** + **HQ Superb**, use the **Subtle** Tube/Tape/Saturation styles and low drive for transparent warmth/harmonic density. Keep band Mix modest, use gentle crossover slopes, watch the output trim (factory output default is −1 dB). Avoid Tone EQ / amp / cabinet-flavour styles if phase-purity is the goal (those stay non-linear-phase by design).

## Notes / gotchas
- **Drive 0 % ≠ clean** — every style applies a baseline nonlinearity; for truly clean, lower band Mix or disable the band.
- **Heavy amp styles apply large internal gain compensation** (−17 to −26 dB) to keep output sane; rebalance with band Level.
- **Curve families:** Tube/Amp/Warm-Transformer = asymmetric (even harmonics, H2); Tape/Saturation/Subtle-Transformer = symmetric (pure odd). Foldback = wavefolder, Rectify = full-wave rectifier (frequency-doubles, fundamental vanishes), Destroy = bit-crush/decimator. (Deep spec has per-style THD/harmonic fingerprints.)
- **Distortion is frequency-independent within a band** (memoryless waveshaper) — any time-varying behaviour comes from the Dynamics knob or modulation, not the curve.
- **Latency:** Linear Phase and HQ oversampling add latency (Global Bypass compensates). Superb HQ costs noticeable CPU, scaling with band count.
- **External side-chain** can trigger EGs/EFs (per-host setup in manual p.41); use the Audition button to confirm the SC routing.
- **Knob tips:** double-click = type value (accepts `1k`, `A4`, `C#3+13`, `2x`, `50%`); Cmd/Ctrl-click = reset; Shift-drag = fine-tune; Alt-drag linked knobs (e.g. input vs output) move oppositely. Mouse-wheel works on any knob.
- All continuous band params are modulation targets; discrete params (Style, HQ) set all selected bands to the same value.

## Deep spec (Programmer only)
`~/.claude/skills/easby/easby-programming/plugins/Saturn2.md` — CLEAN black-box RE (pedalboard/`saturn2_sysid.py`): full 956-param automation surface, per-style harmonic fingerprints (THD%, H2/H3/H5, even/odd ratio, gain), Drive→THD curves, crossover/oversampling behaviour, signal chain. No disassembly, no REF.
