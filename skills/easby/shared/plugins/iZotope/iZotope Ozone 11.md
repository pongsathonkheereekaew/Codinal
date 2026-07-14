# iZotope Ozone 11 — iZotope (mastering suite / multi-effects)

| | |
|---|---|
| Vendor / ver | iZotope · Ozone 11 |
| Type | Mastering suite — modular host ("mothership") + 18 component plug-ins: EQ, dynamics, multiband limiter, saturation, imaging, adaptive/AI tone & balance, dither |
| Format | VST3 / AU / AAX (DAW/NLE plug-in; AAX implied by mastering context). AAC Codec Preview is Rosetta-only on Apple Silicon |
| Source | manual: `iZotope Ozone 11/iZotope Ozone 11.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Ozone 11 is a modular mastering environment. The **mothership** plug-in hosts a user-built signal chain of up to 18 processing modules plus AI-driven **Master Assistant**, **Referencing**, **Codec Preview**, and **Dither**; every module also ships as a standalone **component** plug-in (load just what you need to save CPU). It spans corrective and creative mastering: surgical/vintage EQ, multiband and vintage dynamics, a multiband IRC limiter (Maximizer) with upward-compression and soft-clip, multiband saturation and imaging, and a family of *adaptive/AI* modules unique to iZotope — **Clarity** (flat-noise spectral contouring), **Stabilizer** (adaptive tonal-balance EQ), **Spectral Shaper** (dynamic spectral attenuation), **Impact** (microdynamics), **Master Rebalance** (ML stem-level gain on a finished mix), and **Match EQ** (8000-band reference matching). The distinctive value is the AI workflow: Master Assistant analyzes 8s of your track and auto-builds a chain matched to genre targets (tone, vocal balance, width, dynamics, loudness), which you then dial to taste.

## Controls (every param → musical effect)

### Global / mothership host
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Stem Focus | Full Mix / Vocals / Bass / Drums | Restricts the *entire* chain to one detected stem (mothership only) | Process only vocals/bass/drums on a stereo master |
| Master Assistant | tab/button | Runs AI analysis, builds & matches a chain to a target (mothership only) | Fast starting point / second opinion |
| Presets | global (chain) or per-module | Global presets set whole chain; module presets recall one module | Audition mastering chains or single-module settings |
| Signal Chain | add/remove/reorder modules | Per-module Power, Solo, preset, Difference meter, Remove; "+" adds module | Build/reorder the mastering chain (mothership only) |
| Undo History | list + A/B/C/D snapshots | View/compare/revert recent param states; 4 toggle snapshots | A/B different processing states |
| Input / Output Gain | dB, L/R link | Trim level in/out; meters with selectable Type & Stereo/Mid-Side source | Gain-stage; feed limiter; level-match |
| I/O meter Type / Source | metering calc; Stereo or M/S | Choose loudness/peak calc and stereo vs M/S display | Match metering to delivery spec |
| Bypass | global | Disables all processing in the instance | True A/B vs unprocessed |
| Gain Match | on/off | Compensates output for processing gain changes (modern-bypass option) | Defeat "louder = better" bias |
| Sum to Mono / Swap Channels | toggle | Mono-fold output / swap L↔R (mothership & Imager component) | Mono-compatibility & channel checks |
| Reference (power + panel) | on/off | Enable reference-track playback; opens Referencing panel (mothership only) | Compare master to commercial refs |
| Codec (power + panel) | on/off | Enable Codec Preview; opens panel (mothership only) | Audition lossy-codec artifacts pre-export |
| Dither (power + panel) | on/off | Enable Dither; opens panel (mothership & Maximizer component) | Final bit-depth reduction |
| Channel Processing Mode | Stereo / Mid-Side / Left-Right / Transient-Sustain | Per-module: splits signal into two processable channels (set varies per module; T/S is unique — separates attack vs body) | M/S width tricks, L/R fixes, shape transients independently |

### Master Assistant (AI, mothership only)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Target Library | 10 genre targets + Cinematic + custom | Selects target curve (tonal balance, vocal balance, width, dynamics, loudness); custom from reference files (learns loudest 8s) | Pick a genre/reference to match toward |
| Tonal Balance (Equalizer) | 0–200% | Scales all Equalizer-1 node gains toward target; blue "tunnel" + white line meter | Push tone toward target |
| Loudness (Maximizer) | ±4 dB on Gain; Full Scale / Streaming | Sets Maximizer Gain to hit target LUFS; Full Scale = −0.1 dB out, TP off / Streaming = −1 dB out, TP on | Hit a loudness destination |
| Vocal Balance (Level) | gain on Master Rebalance (vocals) | AI separates vocal, sets vocal-vs-music loudness to genre target; skipped if balanced or no vocal | Sit vocals automatically |
| Dynamics Match | 0–100% (Impact global) | Scales per-band Impact amounts to match microdynamics target | Match punch/density |
| Width Match | 0–100% (Imager global) | Scales per-band Imager amounts to side target; may enable Recover Sides; won't widen narrow bass | Match stereo width |
| Clarity Amount | 0–100% | Drives Clarity processing; applies genre-appropriate Tilt | Add perceived clarity/loudness |
| Stabilizer Amount | 0–100% | Drives Stabilizer toward genre/"Assistant" target | Adaptive tonal balancing |

### Equalizer (analog-matched or digital linear-phase)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Global Filter Mode | Analog (min-phase IIR) / Digital (linear-phase FIR) | Analog = colored/cheaper CPU; Digital = phase-preserving, enables Phase + Surgical shapes | Tone vs transparency |
| Amount | 0–200% (def 100%) | Scales all band gains (won't exceed +15/−30 dB caps) | Globally tame/exaggerate the move |
| Filter Shape | Bell / Proportional-Q / Band Shelf; Shelf: Analog/Baxandall/Vintage(Pultec-style dip)/Resonant; Pass: Flat(Butterworth)/Resonant/Brickwall(elliptic); Surgical (digital only) | Per-node filter character | Pick corrective vs musical curve |
| Frequency | 20 Hz–20 kHz | Center/cutoff of band | Place the move |
| Gain | −30 to +15 dB | Boost/cut amount | Shape level |
| Q / Slope | cF (bandwidth) or dB/oct | Width of bell / slope of pass-shelf (Baxandall & Brickwall fixed) | Surgical vs broad |
| Phase | 0% (linear) – 100% (minimum) | Per-band phase, Digital mode only | Trade phase smear vs pre-ring |
| Extra Curves | Phase Resp / Phase Delay / Group Delay rulers | Visualize phase/delay behavior | Diagnose phase issues |

### Dynamic EQ
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Global Filter Mode | Analog / Digital | Min-phase IIR vs linear-phase FIR | Color vs phase-preserve |
| Filter Shape | Baxandall (Bass/Treble) / Band Shelf / Peak Bell / Proportional-Q | Per-band shape | Gentle vs surgical dynamic move |
| Freq / Gain / Q | 20 Hz–20 kHz / −30 to +15 dB / cF | Static band parameters | Set the resting filter |
| Threshold | dB | Level that triggers dynamic movement | Set onset of action |
| Dynamic Direction | Up / Down | Filter moves up or down past threshold (with +/− gain combos for boost/cut-on-trigger) | De-ess (Down/cut) or ducked-boost (Up) |
| Auto Scale | on/off | Auto-scales attack/release by band frequency | Hands-off timing |
| Attack / Release | ms | Reaction & recovery of the dynamic trigger | Fast for taming, slow for glue |
| Offset | dB | Static gain offset for the band | Bias the resting level |

### Dynamics (up to 4-band analog-modeled comp + limiter)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Crossover bands | up to 4 | Multiband split (Learn auto-places at spectral minima); not shared across modules | Frequency-specific dynamics |
| Level Detection Mode | Peak / Env / RMS (global) | How level is sensed (Env = artifact-free RMS-like) | Peaks vs average control |
| Threshold | Limiter (left) + Compressor (right) handles, dB | Two thresholds per band | Separate comp & limit stages |
| Compressor Ratio | (10):1 to 30:1, def 2:1 | Positive = downward comp; negative = **upward** comp (raises quiet) | Glue, or lift quiet passages |
| Limiter Ratio | (2.5):1 to 30:1, def 10:1 | Positive = limiting (not brickwall, overshoots at 30:1); negative = **upward expansion** (punch) | Peak control or add punch |
| Attack / Release | ms | Comp/limit reaction & recovery | Shape transients/pumping |
| Adaptive Release | on/off | Auto-shortens release on transients, lengthens on sustain | Reduce pumping/distortion |
| Knee | dB range | Soft (gradual) vs hard (aggressive) | Natural vs surgical |
| Parallel | wet/dry, per band | Parallel (NY) compression mix per band | Dynamics + retained transients |
| Auto Gain | on/off | RMS-based make-up per band | Level-match while comparing |
| Global / Band Gain | dB | Make-up gain output / per band | Compensate level |

### Maximizer (full-band IRC limiter — *not* multiband)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Mode | IRC LL / IRC 1 / IRC 2 / IRC 3 (+ styles: Clipping/Crisp/Balanced/Pumping) / IRC 4 (+ styles: Classic/Modern/Transient) | Intelligent Release Control limiter flavors; higher IRC = smarter/CPU-heavier; IRC4 = spectral, least pumping | Loudness vs transparency vs CPU |
| Gain | dB (push into 0 dBFS) | Drives signal into limiting (formerly "Threshold") | Set loudness |
| Output Level | dB | Output ceiling (formerly "Ceiling") | Set delivery ceiling |
| Gain/Output Link | on/off | Inverse-link Gain & Output for unbiased A/B | Hear limiting without louder-bias |
| True Peak | on/off | Limits inter-sample (analog) peaks | Hot mixes / D-A safety |
| Character | Clipping(0.0)–Very Slow(10.0) | Continuous attack/release morph within the Mode | Fine-tune limiter timing |
| Target LUFS + Learn Input Gain | LUFS; 5s learn | Auto-sets Gain to hit target loudness (not for compliance) | Quick loudness target |
| Upward Compress | dB | Transparent parallel upward comp before limiter; level-matched (peaks stay ~0 dBFS) | Density/detail without crushing peaks |
| Soft Clip | power + Amount + Light/Moderate/Heavy | 4× oversampled soft clip before limiter; Light/Mod/Heavy start at −3/−9/−30 dBFS; 100% = full clip at 0 | High-fidelity loudness boost |
| Transient Emphasis | power + Amount | Shapes transients before limiting | Preserve drums/attacks |
| Stereo Independence | Transient + Sustain sliders (0–100%, linkable) | Per-channel limiting independence (successor to Stereo Unlink) | Louder vs stereo-image width |

### Imager (multiband stereo width)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Crossover bands | up to 4 | Per-band width control | Frequency-dependent widening |
| Width | −100 to + (per band) | + widens (side gain), − narrows; −100 = mono band | Widen highs, mono the lows |
| Amount | 0–100% (def 100%) | Scales all band Width | Global width trim |
| Stereoize | power + Amount + Mode I/II | Adds width to mono/narrow material (needs Width increase); Mode I = Haas, Mode II = transient-preserving; mono-compatible | Widen narrow recordings |
| Recover Sides | power + Gain + Solo | Restores side content when narrowing (needs Width decrease) | Keep some side info while tightening |
| Vectorscope / Correlation / Stereo Balance | meters | Polar Sample/Level, Lissajous, correlation bar, balance bar | Monitor phase/mono-compat |

### Exciter (multiband saturation)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Crossover bands | up to 4 | Per-band harmonic excitation | Band-specific saturation |
| Mode | Analog / Retro / Tape / Tube / Warm / Triode / Dual Triode | Harmonic character (odd/even, grit/warmth) | Choose saturation flavor |
| Amount | per band | Harmonic excitation amount | Drive/warmth |
| Mix | wet/dry per band | Blend processed vs dry | Parallel saturation |
| Oversampling | on/off | Anti-alias (more CPU) | Clean high-freq saturation |
| Post Filter | high-shelf on wet | Tames high freq added by saturation | Remove harshness |

### Vintage Compressor (feedback comp w/ detection filter)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Mode | Sharp / Balanced / Smooth | Character (transient-forward → thick/full) | Punch vs glue |
| Threshold | dB | Onset (soft knee — mild comp below) | Set comp point |
| Ratio | higher = more comp | Compression amount | Intensity |
| Attack / Release | ms (release longer for sustained) | Reaction/recovery | Shape feel |
| Gain / Auto Gain | dB / on-off | Make-up; Auto = adaptive RMS make-up | Level match |
| Detection Filter | filter nodes + Solo | Filters the feedback detection signal (HPF/high-shelf to reduce pumping, or HF boost to drive comp) | Frequency-selective triggering |

### Vintage Limiter (Fairchild 670-style)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Mode | Analog / Tube / Modern | Analog = fast/thick bass; Tube = balanced smooth feedback; Modern = vintage + IRC | Character of limiting |
| Threshold | dB | Where limiting starts | Drive loudness |
| Ceiling | dB (−0.3 typical; −0.6/−0.8 for MP3/AAC) | Max output level | Set ceiling |
| Link | on/off | Link Threshold↔Ceiling (same amount) | Unbiased loudness A/B |
| True Peak | on/off | Inter-sample peak limiting | D-A safety |
| Character | Fast(0.0)–Slow(10.0) | Attack/release morph per Mode | Tune timing |

### Vintage EQ (Pultec EQP-1A + MEQ-5)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Low Boost/Cut | freq 20/30/45/60/100 Hz + boost dB + cut dB | EQP-1A low shelf; boost+cut together = boost then dip (musical) | Classic Pultec low-end trick |
| High Boost | freq 3–16 kHz (7 opts) + amount + Q | EQP-1A HF peak (Q interacts w/ boost) | Air/presence |
| High Cut | freq 5/10/20 kHz + cut dB | EQP-1A high shelf cut | Tame top |
| Low-Mid Boost (MEQ-5) | freq 200 Hz–1 kHz (5) + boost | MEQ-5 LM peak | Body |
| Mid Cut (MEQ-5) | freq 200 Hz–7 kHz (11) + cut | MEQ-5 mid dip | Scoop mud/honk |
| High-Mid Boost (MEQ-5) | freq 1.5–5 kHz (5) + boost | MEQ-5 HM peak | Presence/edge |

### Vintage Tape (Studer A810)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Speed | 7.5 / 15 / 30 IPS | Tape speed; faster = better HF/cleaner, slower = warmer/more noise-shift | Vibe vs fidelity |
| Input Drive | dB (gain-compensated) | Drive into tape emulation | Saturation amount |
| Bias | −/+ | Distortion curve shape; − = more HF distortion, + = limits dynamics/different sat | Tone of saturation |
| Harmonics | amount | Adds even-order harmonic distortion | Analog warmth/character |
| Low Emphasis | low / high | Tape "head bump" — low removes peak (flat low), high boosts up to +10 dB | Low-end punch |
| High Emphasis | def 4.0 (flat) | HF compensation; lower = roll-off, higher = shimmer | Air control |

### Adaptive / AI tone & dynamics modules
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Clarity** Amount | 0–100 (max ±6 dB) | Scales spectral contouring toward flat noise (hundreds of bands); tames resonance, unmasks, "pulls blanket off" dull mixes, can raise perceived loudness at same LUFS | Add clarity/loudness transparently |
| Clarity Tilt | dB/oct (def 0 = pink) | Target noise tilt: + brighter (+3 = white), − darker (−3 = brown) | Aim tonal target |
| Clarity Attack / Release | ms | Reaction / return to no-gain; action region 300 Hz–20 kHz | Speed of adaptation |
| **Stabilizer** Target | All-purpose / genre / Assistant | Adaptive-EQ tonal-balance target (All-purpose = "Bass Heavy" TBC curve) | Choose balance target |
| Stabilizer Mode | Shape / Cut | Shape = loudness-neutral boost+cut to target; Cut = only tames resonances above target | Balance vs de-resonate |
| Stabilizer Amount | 0–100 (max +9 dB) | Scales adaptive corrections | Strength |
| Stabilizer Speed / Smoothing / Sensitivity | 0–100 each | Speed = reaction (faster→artifacts); Smoothing = 3–4 vs many filters; Sensitivity = how often resonances are caught | Precision vs artifact trade |
| Stabilizer Tame Transients | on/off | Instant tonal correction of transients | Harsh transients |
| Stabilizer Low/Mid/High | scale per band | Low <100 Hz, Mid 100 Hz–5.6 kHz, High >5.6 kHz | Limit correction by range |
| **Spectral Shaper** Mode | Low / Medium / High | Intensity of high-resolution spectral attenuation | Severity of taming |
| Spectral Shaper Amount | gain reduction in action region | How much to attenuate | Tame harshness/resonance |
| Spectral Shaper Tone | −/+ tilt | Darker (−) / brighter (+) overall character | Color the reduction |
| Spectral Shaper Attack / Release | ms | Onset/release of reduction; full-spectrum action region (Learn auto-sets cutoffs) | Speed of dynamic EQ-like taming |
| **Impact** | −/+ per band (up to 4) | Microdynamics: + expands (open/punchy), − compresses (dense/glued) | Punch or glue per band |
| Impact Envelope | ms or beat divisions (Sync) | Return-to-baseline time after a microdynamic event | Feel/groove |
| Impact Amount / Auto-gain / Stereo Link / Link Bands | 0–100% / on-off | Global scale; RMS make-up; mid-driven L/R link; link bands | Width-aware microdynamics |
| **Master Rebalance** Focus | Vocals / Bass / Drums (one at a time) | ML-detected stem on a finished stereo mix | Fix balance post-mix |
| Master Rebalance Gain | dB | Raises/lowers detected element in real time | Rebalance without stems |
| **Match EQ** Capture (Reference + Apply To) | snapshot capture/stop/clear | 8000+ band linear-phase match; capture ref + your track | Match tone to a reference |
| Match EQ Smoothing / Amount | 0–100% each | Smoothing = precision (lower=more); Amount = intensity (work <50%, smooth out narrow peaks) | Natural overall-shape match |
| Match EQ Cutoff handles | low/high freq | Restrict matched curve to a frequency range | Match only lows/highs |
| **Low End Focus** Modes | Punchy / Smooth | Fast (transient) vs slow (sustain) response | Punch vs body in lows |
| Low End Focus Contrast | −/+ | + = more transient/punch (attenuate out-of-focus); − = blur/saturate-like smear | Tighten or glue lows |
| Low End Focus Gain | dB | Make-up in action region (20–300 Hz) | Level the low band |

### Codec Preview & Dither (mothership; Dither also in Maximizer component)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Codec Format | AAC (Fraunhofer; Rosetta-only on AS) / MP3 (LAME) | Lossy format to audition | Match delivery codec |
| Codec Bit Rate | 96–320 kbps (256 max for mono) | CBR preview rate | Match target bitrate |
| Codec Solo Artifacts | on/off | Isolate the difference (what the codec removes) | Hear codec damage |
| Dither Bit Depth | 24 / 20 / 16 / 12 / 8 | Target export bit depth (MBIT+ algorithm) | Final bit reduction |
| Dither Amount | Off / Low / Medium(rec) / Strong | Dither level; Strong kills distortion at slight noise-floor cost | Quantization-distortion control |
| Dither Noise Shaping | Off → Max (~14 dB suppression) | Pushes dither noise to less audible bands | More dither, less perceived noise |
| Dither Harmonic Suppression | on/off (Amount=Off only) | Moves truncation distortion off audible overtones, no added noise | Dither-free distortion control |
| Auto-Blanking / Limit Peaks / DC Offset Filter | on/off / on/off / HPF 1 Hz | Mute on silence; suppress dither peaks; remove DC before limiter (needs Maximizer/Vintage Limiter in chain) | Clean-up at export |

## Use by lens
- **Producer (create):** Use **Master Assistant** as a one-click "make it sound finished" on a bounce, then push **Clarity** and **Impact** for energy/punch, **Imager** for width, and **Exciter**/**Vintage Tape** for color. Great for sketching a competitive loudness/tone before a mix is truly done; **Master Rebalance** can nudge a vocal or kick up on a flat bounce.
- **Mixing (balance):** Reach for the surgical tools — **Equalizer** (Digital/Surgical for clean cuts), **Dynamic EQ** for resonances/de-essing, **Spectral Shaper**/**Stabilizer** for harshness and adaptive tonal balance, **Dynamics** multiband for frequency-specific control, **Match EQ** to match a reference tone. **Stem Focus** lets you target vocals/bass/drums inside a stereo context.
- **Mastering (finalize):** Build the chain: corrective EQ → dynamics/Stabilizer → Vintage color (EQ/Comp/Tape) → Imager → **Maximizer** (IRC + Upward Compress + Soft Clip + True Peak) for loudness. Set Output Level to delivery ceiling (−1 dB streaming, −0.1 full-scale), verify with **Referencing** and **Codec Preview**, and finish with **Dither** to target bit depth as the last step.

## Notes / gotchas
- **Mothership vs component:** Master Assistant, Stem Focus, Signal Chain, Referencing, Codec Preview are mothership-only. Dither = mothership + Maximizer component. Sum-to-Mono/Swap = mothership + Imager component. Each module is also its own plug-in to save CPU.
- **Channel modes incl. Transient/Sustain:** Most modules support extra channel modes; T/S (Clarity, Dyn EQ, EQ, Imager, Low End Focus, Spectral Shaper, Stabilizer, Match EQ, Vintage EQ) splits attack vs body for independent processing — distinctive feature.
- **Latency/CPU:** Digital (linear-phase) EQ/Dyn-EQ, IRC 3/4, True Peak, Exciter Oversampling, and Codec Preview at >48 kHz all raise CPU/latency. IRC 3/4 high-latency (may be unusable in real-time >48 kHz). Tune EQ buffer size / crossover buffer size in Options. Stereo channel mode is cheapest.
- **Maximizer renames:** "Threshold"→**Gain** (turn up instead of down), "Ceiling"→**Output Level**. Limiter Ratio in Dynamics is not brickwall (overshoots at 30:1) — Maximizer/Vintage Limiter are the true loudness limiters.
- **AI behavior:** Master Assistant analyzes the loudest 8s (loop short selections); custom targets won't create vocal-balance (no Master Rebalance added); returning to Module View then picking a new Target overwrites manual edits. **Learn Input Gain / Learn Input** are not for loudness compliance.
- **AAC Codec Preview** is Rosetta-only on Apple Silicon; AAC/MP3 don't support >48 kHz (real-time resample applied). Leave −1 to −1.5 dB headroom for lossy export.
- **Dither last:** apply after all processing, post-fader, and disable DAW dither to avoid double-dithering. **DC Offset filter** only available with Maximizer or Vintage Limiter in the chain.
- **Delta buttons** on every module monitor exactly what that module changed (Vintage Tape Delta includes phase shift — sounds like more change than it is).

## Deep spec (Programmer only)
not reverse-engineered — capability only.
