# SoundToys PrimalTap — SoundToys (delay)

| | |
|---|---|
| Vendor / ver | SoundToys · v5 (manual "Version 5: For Mac and Windows", © 2015) |
| Type | Vintage digital delay (dual-tap lo-fi / pitch-warp / saturated feedback / Freeze) |
| Format | VST/VST3/AU/AAX (typical SoundToys; not explicit in manual). Mac & Windows. iLok authorized. |
| Source | manual: `SoundToys PrimalTap/SoundToys PrimalTap.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
The full ("deluxe") character delay modeled on the Lexicon Prime Time Model 93 (1978), of which **Little PrimalTap** is the one-knob-each subset. Where Little is a single delay line, PrimalTap gives you **two independent delay taps (A = red, B = yellow)** each settable in milliseconds *or* tempo-locked beats, plus an **LFO** (rate/depth/four shapes) for automated pitch/chorus/flange modulation, selectable **feedback algorithms** (Classic, Parallel, Series, Criss-Cross, Ping-Pong, Reverb), per-tap **depth & output pan with phase**, **Low/High-Cut filters** (globally or feedback-only via Rolloff), and the signature **Freeze** (Repeat Hold) for infinite digital tape loops. Its sonic DNA is the original's **Multiply** trick: to fake long delays on 1970s memory the unit halved its sample rate (and engaged steep anti-alias filters) each time the delay doubled — so fidelity collapses as delay grows (8X ≈ 1.5 kHz). Combined with the smooth sample-rate **Adjust** pitch-bend and a feedback path that can run away into saturated self-oscillation, it produces gritty echoes, octave/pitch jumps, chorus/flange smears, ping-pong rhythms, lush echo washes, runaway loops, and frozen sci-fi drones. A creative mangler, not a clean/transparent echo. Changing Time/Multiply/Delay-Select while audio plays glitches on purpose (period-correct artifact).

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Delay A** (red knob + LCD) | Time mode: ms (max 2500 ms via Delay Select; up to 2048 ms when Multiply 8X) · Beat mode: 0.00–4.00 beats | Sets base delay time of tap A. Click the switch under the red LCD to toggle **Time / Beats** for *this* tap only. Adjusting in real-time *introduces audible glitches* (period-correct, like the hardware). | Core echo/loop length of the first tap; raw-ms vintage feel or tempo-locked rhythm. |
| **Delay B** (yellow knob + LCD) | same as A (independent Time/Beat switch) | Sets base delay time of tap B, fully independent of A — e.g. A synced to beats while B is a fixed ms length. | Second voice for stereo/rhythmic interplay, dotted-vs-straight patterns, chorus stacking. |
| **Link** (button between A & B) | on/off (A is "alpha") | Ties both delay lines so adjusting one moves the other to match. A is the master; its setting is mirrored onto B. | Move both taps together; quick symmetric tweaks without touching each knob. |
| **Time/Beats switch** (under each LCD) | Time ↔ Beat (per tap) | Switches that tap between raw-millisecond display and tempo-relative beat spacing. | Lock one (or both) taps to host tempo, or run free-time. |
| **Adjust** | 1X → 0.5X (smooth, continuous) | Modulates the delay time of **both** A and B by changing sample rate — smoothly shortens delay by up to half, producing an audible **pitch bend / chorus / flange / dive** sweep as you turn it. Smooth (unlike Delay Select, which glitches). | Flange, phase, chorus, pitch dives, "wow"; performable/automatable pitch modulation on both taps at once. |
| **LFO Rate** | 0.1 Hz → 256 Hz | Speed of the LFO that auto-modulates the delay lines — slow sweeps up to full audio-rate FM for effects impossible on the original hardware. Smooth adjustment. | Auto-chorus/flange, vibrato, ring-mod-ish audio-rate textures, evolving sweeps. |
| **LFO Depth** | 0.0 → 1.0 | Amount of LFO modulation applied to the delay lines (varies delay time relative to Delay Select). 0 = no effect; 1.0 = maximum delay-mod limit. Smooth. | Dial intensity of the auto-modulation; subtle warble → seasick sweeps. |
| **LFO Shape** (Tweak menu) | Triangle · Sine · Square · Ramp | Selects LFO waveform. Triangle was the original hardware's only shape. | Triangle/Sine = smooth sweeps; Square = stepped/gated jumps; Ramp = sawtooth rises. |
| **Multiply** (large blue rotary) | stepped: 1X · 1.5 · 2X · 3 · 4X · 6 · 8X · 12 | Multiplies current delay time by the factor. Each step up **halves sample rate + steeper anti-alias filtering** → longer but more lo-fi: 1X≈12 kHz, 2X≈6 kHz, 4X≈3 kHz, 8X≈1.5 kHz (classic grimy PrimalTap tone). Also sets max Freeze loop length (8X → 2048 ms). Changing mid-audio glitches. | Lo-fi grit, extended delay/loop times, octave drops, the "fidelity down as delay up" character. |
| **Freeze** (button + red LED) | on/off (Repeat Hold) | Captures the audio currently in the buffer and loops it infinitely — a digital tape loop. Loop length = max delay set by Multiply (e.g. 2048 ms at 8X, repeating in 2048 ms increments). Toggle off to release. | Held drones, stutters, ambient washes, Eno/Lanois-style infinite loops; ride on/off at key moments. |
| **Feedback — IN** (green slider) | input drive | Drives PrimalTap's input stage; higher = saturation/overdrive with the lo-fi hardware character (separate from clean gain). | Add dirt/warmth; push echoes into distortion. |
| **Feedback — A** (red slider) | 0 → high (toward runaway) | Recirculation amount for tap A — repeats/regen. High adds sustain, saturation, resonance; can run away in Classic mode. | Dub repeats, sustained tails, building resonance on tap A. |
| **Feedback — B** (yellow slider) | 0 → high | Same as A, for tap B. | Independent regen on the second tap; cross-rhythmic build-ups. |
| **Low Cut** (knob, Feedback section) | 0.1 Hz → 1000 Hz (highpass) | Rolls off lows. Applies to whole output or feedback-only depending on **Rolloff**. | Clean mud out of repeats; keep low end tight under long/frozen delays. |
| **High Cut** (knob, Output section) | 15 kHz → 800 Hz (lowpass) | Rolls off highs — darkens the delay/tail. Routed by **Rolloff**. | Tame brightness; make echoes sit behind the source; tape-darken feedback. |
| **Rolloff** (Tweak menu) | Feedback · Output | Sets whether Low/High-Cut act on the **entire output** or **only the feedback path**. Feedback-only keeps each repeat darker/tamer while the first hit stays bright. | Stop long/frozen delays from overtaking the mix while keeping the dry/first tap full. |
| **Algorithm** (Tweak menu) | Classic · Parallel · Series · Criss-Cross · Ping-Pong · Reverb | How recirculated audio is routed — drastically changes Feedback response (see Notes). | Pick the feedback character: runaway (Classic), safe (Parallel), serial flange (Series), rhythmic (Criss-Cross/Ping-Pong), or lush wash (Reverb). |
| **Output — A** (red slider) | level | Output level of delay tap A. | Balance tap A in the wet signal. |
| **Output — B** (yellow slider) | level | Output level of delay tap B. | Balance tap B against A. |
| **Output — Mix** (green slider) | dry ↔ wet | Wet/dry blend. Up = 100% wet; down = dry only. | Blend echo into a track or go fully wet on an aux/return. |
| **Depth A / Depth B** (Tweak menu sliders, + phase invert each) | per-tap modulation depth + phase flip | Per-tap amount of LFO modulation (intensity), set independently for A and B; each has a phase-invert switch. | Modulate one tap more than the other; opposing-phase swirl for stereo movement. |
| **Output Pan A / B** (Tweak menu sliders, + phase each) | per-tap pan position + phase in/out | Pans each delay tap independently in the stereo field, each with its own phase switch. | Spread A/B left-right for width; ping-pong-style stereo placement. |
| **Preset bar** (top) | prev/next arrows, name field, save, A/B compare | Browse/save presets and A/B-compare settings (standard SoundToys header). | Recall starting points; compare two states. |
| **Tweak** (button) | show/hide Tweak menu | Slides out the advanced panel (Algorithm, Rolloff, LFO Shape, Depth, Output Pan). Turns blue when active. | Reveal the deep routing/modulation controls. |
| **Tempo Sync** (panel switch) | on/off (MIDI sync) | Switches both delay lines to MIDI/host-tempo sync; lets PrimalTap lock to project tempo or take tempo via MIDI. | Rhythmic, tempo-locked delays across both taps. |

## Use by lens
- **Producer (create):** The playground. Set A & B to contrasting times (or dotted vs straight in Beat mode), pick **Ping-Pong** or **Criss-Cross** for bouncing stereo rhythms, then crank **Feedback** and sweep **Adjust** / dial the **LFO** for octave jumps, chorus/flange and pitch dives. **Freeze** a phrase into an infinite drone or stutter; ride it on/off for transitions. Push **IN** for grit, step **Multiply** up for grimy lo-fi tails and octave drops. Automate Time/Multiply/Delay-Select for glitchy tape-stop effects.
- **Mixing (balance):** Use as a *character* delay on an aux/return (**Mix** high). Use **Parallel** algorithm for stable, predictable feedback; set **Rolloff = Feedback** with **High Cut** to darken successive repeats so echoes sit behind the dry source. Pan A/B for width on vocals/guitars/synths. Higher **Multiply** = darker/dirtier tail that won't mask. Not your clean tempo-synced workhorse — reach for it when you want vintage color and grit.
- **Mastering (finalize):** Not a mastering tool — unclean, glitch-prone, self-oscillation-capable creative effect. Avoid on the master bus except deliberate special-FX/transition moments.

## Notes / gotchas
- **Feedback algorithms (Tweak menu) define behavior:**
  - **Classic** (default) — A & B outputs mixed and fed back to both inputs; distorts/runs away easily at moderate-high feedback (models original Prime Time).
  - **Parallel** — A feeds back into A, B into B; independent and stable, the most "normal."
  - **Series** — A's output feeds B's input; A & B feedback paths independent → like two delays patched in series (flanged echo, special FX).
  - **Criss-Cross** — feedback paths crossed (A→B, B→A); rhythmic patterns when A/B differ.
  - **Ping-Pong** — crossed feedback but input feeds only A → audio bounces A→B→A…
  - **Reverb** — mixes A & B like Classic but prevents runaway; lush echo washes with long times + delay mod.
- **Glitches by design:** moving any **Delay Select** (Time/Beat knob) or **Multiply** during playback produces audible anomalies — intended period-correct behavior (changing delay forces a memory-location change). LFO/Adjust/Rate/Depth are the *smooth* modulators; use them for click-free movement.
- **Fidelity tied to delay length:** higher **Multiply** = lower bandwidth/more lo-fi (8X ≈ 1.5 kHz). The grime is the feature.
- **Adjust = sample-rate/pitch sweep on both taps:** shortens Time by up to half *and* shifts pitch continuously; expect chorus/flange/pitch artifacts whenever turned.
- **Freeze length = Multiply:** the frozen loop repeats in increments equal to the max delay set by Multiply (e.g. 2048 ms at 8X).
- **Feedback can self-oscillate → LOUDNESS WARNING:** high feedback (esp. Classic) plus **IN** drive can get very loud and saturated fast; SoundToys explicitly cautions at high volumes. Use **Parallel/Reverb** + **Rolloff=Feedback** to tame.
- **Max delay 2500 ms** via Delay Select; **two taps**, each independently Time- or Beat-synced.
- **Relationship to Little PrimalTap:** Little = single line, one knob per function, no taps/LFO/algorithms/Freeze. Reach for full **PrimalTap** when you need the second tap, LFO modulation, feedback routing modes, per-tap pan/depth, Rolloff, or Freeze.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
