# Avid Pro Tools_Plugins — Avid (stock plugin bundle / catalog)

| | |
|---|---|
| Vendor / ver | Avid · Pro Tools Audio & MIDI Plugins Guide, REV A (2025) |
| Type | **Bundle** — the full Pro Tools / VENUE / Media Composer stock plugin set: EQ, dynamics, pitch/time, reverb, delay, modulation, harmonic/saturation, dither, sound-field, instruments, MIDI tools |
| Format | AAX Native + AAX DSP (Carbon/HDX) + AudioSuite (offline render). Not VST3/AU — AAX `.aaxplugin` |
| Source | manual: `Avid Pro Tools/Avid Pro Tools_Plugins.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
The complete first-party effects/instrument/MIDI suite shipped with (or sold alongside) Pro Tools. This is a **catalog card**, not a single plugin — its value is letting any easby agent pick the right Avid stock tool and set its key controls. Spans clean digital workhorses (EQ III, Dynamics III, Maxim, D-Verb, Reverb One, Mod Delay III), Euphonix-System-5-modelled "Pro" series (Channel Strip, Pro Compressor/Expander/Limiter/Multiband/Subharmonic) for mix/master, faithful hardware emulations (BF-2A=LA-2A, BF-3A=LA-3A, BF76=1176, Fairchild 660/670, Pultec EQP-1A/EQH-2/MEQ-5, SansAmp PSA-1, Purple MC77, Reel Tape, Moogerfooger, Eleven amp sims), and a set of MIDI generators (Note Stack, arpeggiators, chord/riff tools). All effects share common UX conventions (below) and support MIDI CC Learn.

## Global conventions (all Avid effects)
| behavior | detail |
|---|---|
| Formats per plugin | most are **mono / multi-mono / stereo**; "Pro" series + Channel Strip + Dynamics III go to **7.1** (>stereo needs PT Ultimate/Studio) |
| Sample rates | 44.1 / 48 / 88.2 / 96 / 176.4 / 192 kHz on virtually all |
| Fine adjust | hold **Cmd** (Mac) / Ctrl (Win) while dragging |
| Reset to default | **Option/Alt-click** a control or its text box |
| Bipolar sliders | center = 0; right = +, left = − |
| General I/O strip | many show **Line/Inst** (input level type), **Input** (−20…+12 dB), **Mix** (0=dry,100=wet), **Output** (−20…+12 dB) |
| "Stomp" plugins | Bypass toggle + Bypass LED (lit = active) |
| Sync | time-based FX (chorus/delay/flanger) have a **Sync** param locking to session tempo / rhythmic subdivisions |
| MIDI control | right-click any control → **Learn** (move a CC) or assign a CC #; **Forget** clears. Saved with session (use a template), NOT with presets. VENUE/Media Composer have no MIDI. |
| `k` shortcut | typing `k` after a number in a kHz field ×1000 |

---

## EQ Plugins

| plugin | controls | what / when |
|---|---|---|
| **EQ III** (1-Band) | INPUT gain, phase, **6 filter types** (High/Low Shelf, Peak, HPF, LPF, Notch), **FREQ**, **GAIN**, **Q**; frequency graph (drag points) | Clean surgical/musical single-band; shelf, bell, or 6/12/18/24 dB-oct pass filter. The everyday Pro Tools EQ. |
| **EQ III** (7-Band) | per band: enable, freq, gain, Q. **HP/Low-Notch** (20Hz–8k, slope 6/12/18/24), **LP/High-Notch** (120Hz–20k), **Low Shelf/Low Peak** (20–500Hz, ±12/±18dB), **Low-Mid Peak** (40Hz–1k), **Mid Peak** (125Hz–8k), **High-Mid Peak** (200Hz–18k), **High Shelf/High Peak** (1.8k–20k). Color-coded graph | Full-range mix EQ; switchable shelf↔peak and pass↔notch per band; ±18 dB on the peak bands. |
| **304E Equalizer** | **Bass** (±11), **Mid** + **Mid Freq** (500Hz–3.5k, ±11), **Treble** (±11), **Gain** (±11) | "Incredibly warm, musical" 4-knob broad-stroke tone shaping; vibe over precision. |
| **Eleven Effects Graphic EQ** | fixed-band graphic sliders | Quick guitar/bus tone shaping (Eleven Effects family). |
| **Focusrite D2** | parametric EQ + shelves/filters (multi-band, stereo-capable) | Classic Focusrite Red-series EQ voicing. |
| **Pultec EQP-1A** | low boost+atten (shelf), high boost (peak, selectable freq) + high atten | Legendary passive program EQ; the famous low boost+cut "trick" on bass/kick. |
| **Pultec EQH-2** | like EQP-1A + mid band | Pultec with extra midrange control. |
| **Pultec MEQ-5** | midrange boost/dip program EQ | Mid presence/de-mud on vocals & guitars. |
| **Channel Strip EQ section** | 4-band parametric (LF shelf/peak, LMF peak, HMF peak, HF shelf/peak) + **Filter 1 & 2** (HP/LP/BP/Notch, freq 20Hz–21k, slope 12/24 dB-oct or Q) | See Channel Strip below; the console-style mix EQ. |

## Dynamics Plugins

| plugin | model / job | key controls |
|---|---|---|
| **Dynamics III — Compressor/Limiter** | clean comp→limiter | THRESH (−60…0, def −24), RATIO **1:1→20:1, then LMTR (∞), then negative −20:1…0:1** (ducking), KNEE (hard↔soft), ATTACK, RELEASE, GAIN, DEPTH; gain-transfer graph; ext-key side-chain w/ HF+LF filters |
| **Dynamics III — Expander/Gate** | downward exp / gate | THRESH, RATIO **1:1→100:1 (=gate)**, ATTACK (10µs–300ms), HOLD (5ms–4s), RELEASE (5ms–4s), RANGE/Depth (−80…0dB), **Look Ahead** (2ms), KNEE, HYST; side-chain HF/LF filters |
| **Dynamics III — De-Esser** | sibilance | **FREQ** (500Hz–16k), **RANGE** (−40…0dB max reduction), **HF Only** (band vs broadband), **Listen** (solo sibilance); frequency graph. No threshold — tracks input. Insert AFTER comp/limiter. |
| **Channel Strip — Dynamics** | Euphonix System 5 comp+gate+SC all-in-one | Exp/Gate (Thresh, Attack, Ratio, Depth, Hold, Release, Knee, Hyst) + Comp/Limit (Ratio 1:1→20:1→LMTR→neg, Thresh, Attack 100µs, Knee, Release, Depth, Gain) + Side-Chain (Source Internal/Key/All-Linked, Peak/Avg, filter LP/HP/Notch/BP). FX-chain order EQ/FILT/DYN/VOL reorderable |
| **Maxim** | look-ahead peak limiter / maximizer (mastering) | **Threshold** slider (drag down to limit), **Ceiling** slider (output ceiling, ~−0.5dB), **Release**, **Mix** (dry/wet), **Link** (thresh↔ceiling), **Dither** + Noise Shaping + Bit Res (16/18/20). Histogram of peaks; Attenuation peak-hold meter. 1024-sample look-ahead → true zero-attack, transient-preserving. Adds latency (use Delay Comp/TimeAdjuster). |
| **BF-2A** | **LA-2A** opto leveling amp | **Peak Reduction** (drives side-chain/compression), **Gain** (tube makeup), **Comp/Lim** switch (~3:1 vs ~12:1), Meter (GR / Output 0VU=−18dBFS). Hidden side-chain HPF (250Hz, 0–100%) via automation. Smooth program leveling, vocals/bass; "Line Amp" trick (Peak Reduction off, use Gain for tube color). |
| **BF-3A** | **LA-3A** opto, solid-state | **Peak Reduction**, **Output Gain**, **Comp/Lim** (~3:1 vs ~15:1), Meter. More aggressive midrange than BF-2A; guitar/piano/vocals/drums. |
| **BF76** | **1176** FET | **Input** (=threshold+amount), **Output**, **Attack** (0.4–5.7ms, CCW=slow), **Release** (60–1100ms), **Ratio** push 4:1/8:1/12:1/20:1 (+ "all-buttons-in" via Shift-click), Meter GR/−18/−24/Off. Fast punchy FET color; drums, vocals, parallel. |
| **304C Compressor** | photo-optical FX compressor | Input Gain, **Compression** (feeds side-chain), Output Gain, **Slope** (=ratio, 1 gentle…5 severe pumping), Attack, Release. Non-logarithmic by design (psychoacoustic loudness, no "deadness"); brighten/tighten/clarify. |
| **Fairchild 660** | mono vari-mu tube limiter | Input Gain, Threshold, Time Constant (program-dependent A/R) | classic glue/limiting colour |
| **Fairchild 670** | stereo/dual vari-mu tube | as 660 ×2 + L/R or lat/vert (mid-side) modes | mastering/bus glue, the famous tube limiter |
| **Purple Audio MC77** | 1176-style FET (Purple voicing) | Input, Output, Attack, Release, ratio buttons | alternate 1176 flavour, aggressive |
| **Smack!** | modern FET-flavoured comp w/ modes | Input, Output, Attack, Release, Ratio, **mode** (Norm/Opto/Warm), Mix, side-chain | versatile colour compressor, parallel-capable |
| **Focusrite D3** | Red-series comp + limiter | comp (thresh, ratio, attack, release, gain) / limiter, side-chain | clean British comp/limiter |
| **Impact** | SSL-bus-style compressor | Threshold, Ratio, Attack, Release, Makeup | mix-bus glue ("instant radio") |
| **Eleven Effects Gray Compressor** | pedal-style comp | Sustain, Level | guitar/bus stompbox compression |

## "Pro" series (Euphonix System 5–based, mix/master)

| plugin | what | headline controls |
|---|---|---|
| **Pro Compressor** | flagship clean compressor, to 7.1 | Threshold, **Ratio** 1:1→20:1→LMTR→neg, Knee, Attack, Release, Depth, **Dry Mix** (parallel), Makeup; **Detection: Smart / RMS / Avg / Peak / Fast**; Attenuation Listen; side-chain (Source Int-StereoPairs/Ext-All(w-LFE)/Int-All(no-LFE)/Int-Front-Rear, filter LP/HP/Notch + Q, Listen); dynamics graph (drag Thresh/Ratio/Knee/Depth) |
| **Pro Expander** | flagship expander/gate, to 7.1 | Threshold, Ratio, Attack, Hold, Release, Range, Knee + detection modes + side-chain (mirrors Pro Compressor) |
| **Pro Limiter** | true-peak brickwall + loudness | Threshold/Ceiling, Release, attack modes; **loudness numeric (LUFS) + histogram + loudness meters**; AudioSuite Loudness Analyzer. Final-stage limiting + loudness compliance. |
| **Pro Multiband Dynamics** | multiband comp/exp/limit w/ FFT | FFT display, per-band thresh/ratio/attack/release/gain, In/Out gain, Source linking, side-chain; pairs with **Multiband Splitter** (route bands out) | mastering multiband control |
| **Pro Subharmonic** | synthesizes lows from source | **Subharmonic range** 120-180/80-120/60-90/40-60Hz, **Lower/Upper/Direct Gain** (±, solo each), **HP/LP filters** (freq 5–1000Hz + Q 0.10–5.00), **Drive** (soft-sat, 6 characters Clean I/II, Resonant I/II, Distort I/II), **Mix** (50%=both full), surround Front/Center/Surround/LFE sends, **MIDI-tunable** (notes 12–60, lower=note, upper=+5th) | bass reinforcement on kick/808/sub; club/cinema low end |

## Pitch & Time Shift

| plugin | job | key controls |
|---|---|---|
| **Pitch II** | real-time pitch shift + delay/feedback | Pitch (coarse/fine), Delay, Feedback, Mix, Crossfade |
| **Pitch Shift (Legacy)** | older pitch shifter | coarse/fine pitch, crossfade, level |
| **Time Shift** | AudioSuite TCE + pitch/formant | Speed/Pitch, **algorithm** (Monophonic/Polyphonic/Rhythmic/Varispeed), formant, transient/window | timestretch clips, post pull-up/down |
| **X-Form** | high-quality offline (Radius) TCE/pitch | time %, pitch, formant, quality; AudioSuite-only | best-quality stretch for critical material |
| **Vari-Fi** | varispeed-style spin-up/down | speed-up / slow-down direction | tape start/stop FX |

## Reverb Plugins

| plugin | job | key controls |
|---|---|---|
| **D-Verb** | studio digital reverb | Gain, **Algorithm: Hall / Church / Plate / Room 1 / Room 2 / Ambience / Nonlinear**, **Size** (Small/Med/Large), **Diffusion**, **Decay** (→∞), **Pre-Delay**, **Hi-Freq Cut**, **LP Filter**, Mix | go-to everyday reverb; Nonlinear = gated drum verb |
| **Reverb One** | world-class shaping reverb | Master Mix (Wet/Dry, **Stereo Width** 0=mono…100), Reverb (Level, **Time**, **Attack**, **Spread**, **Size** in m, **Diffusion**, **Pre-Delay**), **Decay Ratio/Threshold** (dynamic decay), **Chorus** (Depth/Rate), **Early Reflections** (ER preset Room/Club/Stage/Hall/Cathedral/Plate…, Level/Spread/Delay), editable **EQ + Color** graphs | detailed, natural halls/plates; vocal & orchestral verbs |
| **ReVibe II** | advanced room-modelling reverb | room types, decay EQ graph, decay color graph, contour, early/late balance, bipolar coloration sliders | film/post + music; surround-capable |
| **Space** | convolution (IR) reverb | IR browser/library (rooms/halls/plates/FX), decay, pre-delay, EQ, snapshots | true-space convolution, realistic ambiences |
| **Black Spring** (Eleven Effects) | spring reverb | On/Bypass, **Mix**, **Decay**, **Tone** (high-cut) | surfy/twangy guitar spring |
| **Studio Reverb** (Eleven Effects) | Reverb-One-derived digital verb | On, **Type**, **Decay** (0–10s), **Pre-Delay**, **Tone**, **Mix** | quick clean verb |

## Delay Plugins

| plugin | job | key controls |
|---|---|---|
| **Mod Delay III** | clean modulated delay | Gain, **Delay** (+ Sync to tempo), Depth, Rate, Feedback, LPF, Mix; comes in short/slap/medium/long/extra-long variants | bread-and-butter tempo-sync delay |
| **Moogerfooger Analog Delay** | BBD analog delay | Drive, Delay Time, Feedback (Short/Long), Mix, LFO Rate/Amount | warm analog/dub echoes |
| **Reel Tape Delay** | tape echo | tape-delay time (+ tempo sync), feedback, wow/flutter, Drive, Tape Machine, Mix | vintage tape slap/echo |
| **Tel-Ray Variable Delay** | oil-can delay emulation | delay/rate, sustain (feedback), mix | lo-fi warbly vintage echo |
| **TimeAdjuster** | sample-accurate delay/phase + gain | delay (samples), gain, phase invert | manual delay compensation (latency align) |

## Modulation Plugins

| plugin | job | key controls |
|---|---|---|
| **Sci-Fi** | analog-synth-style modulator | effect type (ring mod / resonator etc.), freq, depth, mod | sound-design/FX modulation |
| **Eleven Effects** (modulation set) | guitar pedals | **Black Shiny Wah**, **C1 Chorus/Vibrato**, **Flanger**, **Orange Phaser**, **Roto Speaker**, **Vibe Phaser** — each: rate/depth/mix + type toggles | classic guitar modulation |
| **Moogerfooger Lowpass Filter** | resonant LPF + envelope/LFO | Cutoff, Resonance, Envelope amount, LFO | filter sweeps, synth-bass |
| **Moogerfooger 12-Stage Phaser** | deep phaser | Rate, Amount, Resonance, LFO | lush phasing |
| **Moogerfooger Ring Modulator** | ring mod | carrier freq, LFO, mix | metallic/clangorous FX |
| **Reel Tape Flanger** | tape flanger | rate, depth, feedback, Drive, Tape Machine, Mix (+ tempo sync) | tape-style flange |
| **Voce Chorus/Vibrato** | Leslie-amp chorus/vibrato | Chorus/Vibrato C1-C3/V1-V3 settings | organ/Leslie modulation |
| **Voce Spin** | rotary speaker sim | rotor speed (slow/fast/brake), balance | Leslie rotary |

## Harmonic / Distortion / Saturation

| plugin | job | key controls |
|---|---|---|
| **Lo-Fi** | bit/sample-rate crusher | **Sample Rate** (down to ~700Hz, Off=bypass), **Sample Size** (24→2 bit), **Quantization** Linear/Adaptive, **Noise** (0–100%), **Distortion** (soft clip), **Saturation** (tube high-roll), **Anti-Alias** (0–100%) | retro/8-bit grunge, drums/synths |
| **Recti-Fi** | additive harmonics via rectification | **Pre-Filter** (43Hz–22k), **Type: Positive / Negative (=octave up) / Alternating / Alt-Max (=octave down/sub)**, **Gain**, **Post-Filter**, **Mix** | synthesize sub or super-harmonics; bass thickening |
| **Reel Tape Saturation** | analog-tape saturation | **Drive** (±12), **Output**, **Tape Machine** (US=3M M79 / Swiss=Studer A800 / Lo-Fi), **Tape Formula** (Classic=Ampex 456 / Hi Output=Quantegy GP9), **Speed** (7.5/15/30 ips), **Noise**, **Bias** (±6dB), **Cal Adjust** (+3/+6/+9dB) | warmth/glue, round transients; on tracks, bus, or mix |
| **SansAmp PSA-1** | tube amp / DI saturation | **Pre-Amp**, **Buzz** (low break-up), **Punch** (mid break-up), **Crunch** (upper harmonics/pick), **Drive** (power-amp dist), **Low** (±12), **High** (±12), **Level**. Arrows = unity. | guitar/bass amp tones + lo-fi textures on anything |
| **Recti-Fi / Pro Subharmonic** | (sub generation — see EQ/Pro & Recti-Fi rows) | | |
| **Eleven** / **Eleven MK II** | full guitar amp+cab modelling | amp model, gain/EQ/presence/master, cab + mic select, input calibration | the flagship Avid amp sim |
| **Eleven Lite** | reduced Eleven | core amp models + tone | bundled lite amp sim |
| **Eleven Effects Harmonic set** | drive/fuzz pedals | **Black Op Distortion**, **DC Distortion**, **Green JRC Overdrive**, **Tri-Knob Fuzz**, **White Boost** (Gain/Volume/Bass/Treble, +20dB clean boost) | guitar dirt pedals |
| **Aphex Aural Exciter Type III** | high-frequency exciter | rotary tune/mix controls + meters | air/presence/clarity enhancement |
| **Aphex Big Bottom Pro** | low-end enhancer | rotary drive/tune + switches + meters | fatten/extend low end |

## Dither

| plugin | job | controls |
|---|---|---|
| **Dither** | requantization noise at bit-reduction | **Bit Resolution** (16/18/20/24), **Noise Shaping** on/off | last insert on master when reducing bit depth |
| **POW-r Dither** | psychoacoustic dither | Bit Resolution, **Noise Shaping Type 1/2/3** | higher-quality mastering dither (type per material) |

## Sound Field

| plugin | job | controls |
|---|---|---|
| **AutoPan** | LFO auto-panner | Rate (+ tempo sync), Depth, waveform, stereo/surround pan path, phase | rhythmic panning, width FX |
| **Down Mixer** | multichannel → fewer channels | Source format, downmix coefficients/levels | fold surround to stereo/mono |

## Other / Utility

| plugin | job | controls |
|---|---|---|
| **InTune** | precision instrument tuner | pitch display, calibration (A-ref), note/cents readout | tuning reference |
| **MasterMeter** | oversampled true-peak / inter-sample meter | true-peak metering, over indicators | catch inter-sample overs at master |
| **Signal Generator** | test tone | frequency, level, waveform (sine/square/saw/triangle/noise) | calibration / test |
| **SoundReplacer** | drum/sample replacement | trigger threshold, 3 amplitude zones, target sample slots | replace/augment drum hits |
| **Time Compression/Expansion** (TCE) | AudioSuite stretch | ratio, source/destination length, crossfade | offline length change |
| **Trim** | gain trim | gain, phase | quick clip gain (AudioSuite) |
| **AudioSuite utilities** | offline file edits | DC Offset Removal, Duplicate, **Gain**, **Invert** (polarity), **Normalize**, **Reverse** | destructive file housekeeping |

## Instruments

| plugin | job | notes |
|---|---|---|
| **Click II** | metronome | sound select, accent/unaccent level, MIDI note/velocity |
| **Pro Tools \| GrooveCell** | drum/sample groove instrument | Pads / Sequencer / FX pages; import & drag-drop clips |
| **Pro Tools \| PlayCell** | phrase/loop player instrument | factory palette, global controls, macros |
| **Pro Tools \| SynthCell** | virtual synth | main + effects pages, global controls |
| **ReWire** | host other apps as instruments | requires ReWire-compatible app |

## MIDI Plugins (insert on MIDI/Instrument tracks)
- **Avid Note Stack** — stacks up to 9 transposed notes per input note (instant chords/octaves).
- **Avid Pitch Control** — transpose by Range + Control.
- **Avid Velocity Control** — scale/offset velocity by Range + Control.
- **Audiomodern Riffer 3**, **BLEASS Arpeggiator**, **K-Devices TATAT**, **Mixed in Key Human/Captain Chords Lite**, **Modalics EON-Arp**, **Nightfox Audio Rendition Lite**, **Pitch Innovations Groove Shaper Lite**, **SEQUND Lite Sequencer** — third-party generative/arp/chord/sequencer MIDI tools bundled with Pro Tools (piano-roll randomizers, arps, chord engines, step sequencers; most support MIDI Learn + presets).

## Use by lens
- **Producer (create):** Reach for the character boxes — **SansAmp PSA-1** / **Eleven** for guitar & DI grit, **Lo-Fi** for 8-bit crush, **Recti-Fi** for octave/sub synthesis, **Reel Tape Saturation** for warmth, **Sci-Fi** / **Moogerfooger** for sound design, **AutoPan** + **Mod Delay III** (tempo-synced) for movement, **GrooveCell/SynthCell** + the MIDI tools (**Note Stack**, arps, **Groove Shaper**) to generate parts. **304C** to make a track "jump."
- **Mixing (balance):** **EQ III** (7-band) or **Channel Strip** for tonal shaping; **Dynamics III** comp/gate/de-esser per track; pick the right vintage comp by job — **BF-2A** (smooth leveling/vocal/bass), **BF76** (punch/drums/parallel), **BF-3A** (guitar/piano), **Fairchild/MC77/Smack!/Impact** for colour & glue; **D-Verb**/**Reverb One**/**Space** for ambience, **Mod Delay III** for echoes; **Pro Subharmonic** for kick/808 weight; **Pro Compressor** (Smart detection + Dry Mix parallel) on busses.
- **Mastering (finalize):** **Pro Limiter** (true-peak + LUFS/loudness meters) or **Maxim** (transparent look-ahead limiting + dither) as the ceiling; **Pro Multiband Dynamics** for band control; **Pro Compressor** for gentle bus glue; **MasterMeter** to catch inter-sample overs; finish with **Dither** / **POW-r Dither** (16-bit + noise shaping) as the last insert.

## Notes / gotchas
- **AAX only** — these do NOT load in VST3/AU hosts; agents targeting non-PT DAWs can't use them directly.
- **Look-ahead latency:** Maxim adds 1024-sample (sample-rate-proportional) delay; Pro Limiter / Pro Multiband also add latency. If applied to only one of several parallel sources, align with **TimeAdjuster** or rely on Delay Compensation.
- **Dynamics III ratio is continuous past limiting into *negative* ratios** (ducking/"squash-and-soften") — same on Channel Strip & Pro Compressor.
- **De-Esser III has no threshold control** — it tracks the input; automate **Range** for loud/soft passages; always insert **after** comp/limiter.
- **BF-2A side-chain HPF** is hidden — only reachable via plugin automation / control surface (0–100% = filter <250 Hz out of the detector).
- **AudioSuite vintage comps (BF-2A/3A/76) default side-chain to "None"** — you must pick a key input or you'll hear no compression.
- **>stereo (surround) formats** for Channel Strip / Dynamics III / Pro series require **Pro Tools Ultimate or Studio**.
- **Pro Subharmonic is MIDI-tunable** (and can lock to a bass virtual instrument) — feed it a **monophonic** sequence only.
- **MIDI Learn assignments save with the session/template, not with plugin presets**; VENUE & Media Composer have no MIDI.
- **AAX DSP** variants (zero-latency, real-time) require **Pro Tools | Carbon or HDX**; everything also runs as **Native** + most as **AudioSuite** (offline render).
- Many plugins (304E, 304C, Aphex, BF-2A/3A/76, Eleven, Fairchild, Focusrite, Impact, Moogerfooger, Pro series, Purple MC77, Reel Tape, Reverb One, ReVibe II, Smack!, Space, Tel-Ray, Voce, X-Form) are **sold/rented separately** from the Marketplace — not all are in every Pro Tools tier.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
