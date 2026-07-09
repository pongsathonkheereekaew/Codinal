# Crystallizer — Soundtoys 5.5 (granular pitch echo)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Granular pitch-echo / reverse delay (splice/grain delay + pitch-shifted feedback) |
| Tech | C++ VST3 over the shared **Soundtoys** framework (one statically-linked engine across the suite — co-loading two Soundtoys VST3s duplicates ObjC classes `SoundtoysCocoaView`/`AuxWindow` → load one-per-process). AAX slice = PACE; VST3 = clean, pedalboard-hostable. |
| Binary | Universal VST3, not stripped of the shared framework; AAX=PACE-wrapped (not used here). |
| Provenance | **CLEAN** — black-box pedalboard measurement of the licensed VST3 + public DSP literature + own description. No disassembly. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (harness `Tools/st_sysid.py`, `Tools/mod_probe.py`; data `out/Crystallizer_{params,null,probe,mod}.json`) |

## Signal chain
```
x → input gain → [Analog/Digital in-stage saturation] → HP (lowcut) / LP (highcut) on the recirculating path
  → splice/grain capture (note-division length) → delay line (note-division time)
  → pitch shifter (global pitch_cents) ──┐
  → feedback bus (regenerate) ───────────┤→ each regeneration: + pitchoffset_cents (cumulative pitch cascade)
        (fbmode: Mixed / Dual / PingPong; direction: forward / reverse-grain)
  → gate/duck (gateduck_db, duckmode = Output/Regen/Both)
  → dry/wet (mix) → output gain → y
```

## Per-stage formula (all CLEAN — black-box)
- **In-stage coloration (CLEAN):** at `mix=0` the output still nulls only **−18.1 dB** vs dry in the default **Analog** mode ⇒ the dry/input path is *always* colored (analog-style saturation), not a clean bypass. Digital mode removes it (see Tremolator/PanMan inoutmode: Analog ≈ even-harmonic saturation, Digital = 0 % THD). So `mix` is dry/wet of the *effect*, but the dry leg is still run through the colored input stage.
- **Splice / grain (CLEAN, tempo-locked):** `splicevalue` 0..6 selects a **note division** for the grain (splice) length; `spliceoffset` 0..100 % is a fine offset. In pedalboard (no host transport) the absolute grain floors to a short window (~1–6 ms measured; envelope ~18 ms at default) and does **not** respond to `tempo_bpm`. Absolute splice time = **tempo-sync: unmeasured (needs REAPER transport)**; only the relative note grid is visible.
- **Delay (CLEAN, tempo-locked):** `delayvalue` 0..7 = note division, `delayoffset` 0..100 % = fine. Measured first-echo times at default tempo: dv2=731 ms, dv3=481 ms, dv4=231 ms (≈250 ms note steps), dv≥5 clamps to 231 ms, dv0/1 = no echo (too short). **`tempo_bpm` does NOT move these in FreeRun** (60/120/240 BPM → identical 231 ms) and `delayoffset` had no effect at dv4 ⇒ the base delay is host-clock-driven. Absolute delay = **tempo-sync: unmeasured**; note-grid ratios visible (longer dv = shorter time, i.e. finer division).
- **Pitch — global (CLEAN):** `pitch_cents` ±3600 applies a static shift to the recirculating grains. Measured accurate: set −1200 → −1186 c, 0 → +1, +1200 → +1211 c on the echoes. Linear, ~1:1 cents.
- **Pitch — cascade (CLEAN, signature):** `pitchoffset_cents` 0..4800 adds its value to the pitch **each regeneration**, accumulating. Tone-burst echo FFT: offset=700 → successive echoes at −709, −1404 (−2×700), −2102 (−3×700) cents; offset=1200 → −1214, −2×1214 c (octave staircase). **This is the "infinite pitch cascade."** Both **up- and down-shifted grains appear simultaneously** (e.g. offset=700 produced taps at +700 c *and* −1400 c) — the Crystal pair (up + down) characteristic of the effect; `fbmode=Mixed` mixes both directions.
- **Feedback (CLEAN):** `regenerate` 0..1 = feedback amount. Tap count: 0.0→1 echo, 0.3→~10, 0.6→30+, sustained. Near max (0.9/0.99/1.0) the tail holds ~−30 dB at 2.5 s but does **not** run away/clip ⇒ feedback is internally bounded (no destructive self-oscillation).
- **Feedback routing (CLEAN):** `fbmode` **PingPong** bounces each repeat L↔R (measured hard-left then hard-right then left in successive 200 ms windows: L=−11.7/R=−127, then L=−99/R=−12.2, then L=−17.7/R=−96). **Mixed** = both pitch directions summed; **Dual** = independent L/R feedback paths.
- **Reverse (CLEAN, present):** `direction=reverse` reorders the grain (plays the captured splice backward). Confirmed active (reverse echo shows asymmetric zero-crossing-rate vs forward); exact intra-grain reversal qualitative (FreeRun grain timing makes a clean chirp-slope capture finicky).
- **Filters (CLEAN):** `lowcut_hz` 1–5000 (HP) and `highcut_hz` 500–20000 (LP) shape the feedback/echo path — band-limit the regenerating grains so the pitch cascade darkens/thins each pass (classic for taming runaway HF in pitched feedback).
- **Gate / duck (CLEAN):** `gateduck_db` ±60. Negative ducks the wet: −30 dB → tail dropped 30 dB (−27.6→−57.6 dB); 0/+30 → no duck. `duckmode` = Output / Regen / Both selects whether the duck hits the wet output, the feedback regen, or both (so the dry can push the echoes down, classic "duck-the-delay").

## Why / design rationale (music ↔ code)
- **Grain (splice) + delay as separate note-divisions** → decouples *texture* (grain size = grainy/smeared vs clean) from *rhythm* (echo spacing). Short splice = shimmery granular cloud; long splice = clean pitched echo. Musical purpose: one box covers tape-echo, shimmer-verb, and granular FX.
- **`pitchoffset_cents` accumulating per regeneration** → the famous ascending/descending "shimmer" staircase: each repeat is a fixed interval higher/lower, so an octave-offset builds an octave-stacked cascade that climbs forever (bounded by the lowcut/highcut). Chosen over a single static shift because the *evolution* is the effect — it turns a delay into a generative pitched texture (the Eno/shimmer-verb trick, here exposed directly).
- **Simultaneous up+down grains (Crystal pair)** → instantly thick, chord-like shimmer from a mono source without an external harmonizer — the "crystallize" identity.
- **Band-limit on the feedback path (lowcut/highcut)** → pitched feedback accumulates HF (each up-shift pushes energy up); the LP keeps the cascade from turning into harsh fizz, the HP stops DC/rumble build-up — essential for a *stable, musical* infinite cascade.
- **Bounded regeneration (no runaway)** → lets the user sit at ~max feedback for an "infinite" wash that decays gracefully instead of clipping — safer creative tool.
- **Duck-the-delay (`gateduck`/`duckmode`)** → keeps the dense pitched echoes out of the way of the dry transient, so the effect supports rather than masks the source (a mix-glue move borrowed into a creative FX).
- **Analog in-stage** → the always-on input coloration glues the synthetic pitch-shifted grains with even-harmonic warmth so they sit like a real instrument, not a sterile DSP artifact.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| inputgain_db | dB | −24…+24 | input trim |
| outputgain_db | dB | −24…+24 | output trim |
| mix | % | 0…100 (def 50) | dry/wet of effect; dry leg still colored in Analog (mix=0 nulls only −18 dB) |
| inoutmode | enum | Digital / Analog (def Analog) | Analog = even-harmonic input saturation; Digital = clean |
| regenerate | 0–1 | 0…1 (def 0.21) | feedback amount; bounded (no runaway) |
| lowcut_hz | Hz | 1…5000 (def 10) | HP on echo/feedback path |
| highcut_hz | Hz | 500…20000 (def 10000) | LP on echo/feedback path |
| gateduck_db | dB | −60…+60 (def 0) | <0 ducks wet by that amount; ≥0 no duck |
| direction | enum | forward / reverse (def reverse) | reverse = grain played backward |
| syncmode | enum | FreeRun / MIDI (def MIDI) | use FreeRun for measurement; both still tempo-clock the splice/delay |
| fbmode | enum | Mixed / Dual / PingPong (def Mixed) | Mixed=up+down summed; Dual=indep L/R; PingPong=L↔R bounce |
| duckmode | enum | Output / Regen / Both (def Output) | where gateduck applies |
| smoothing_msec | ms | 20…2000 (def 20) | parameter/grain crossfade smoothing |
| pitch_cents | cents | −3600…+3600 (def 0) | static global pitch on grains (±3 oct) |
| pitchoffset_cents | cents | 0…4800 (def 13) | **per-regeneration** pitch increment (cascade); ±4 oct |
| splicevalue | note idx | 0…6 step 1 (def 3) | grain/splice length = note division (tempo-locked) |
| spliceoffset | % | 0…100 (def 6) | fine splice offset |
| delayvalue | note idx | 0…7 step 1 (def 3) | echo delay = note division (tempo-locked) |
| delayoffset | % | 0…100 (def 2) | fine delay offset |
| threshold_db | dB | −60…0 (def −40) | duck/gate sidechain threshold |
| attack_msec | ms | 0.1…5000 (def 100) | duck/gate attack |
| release_msec | ms | 0.1…5000 (def 500) | duck/gate release |
| tempo_bpm | BPM | 30…240 (def 120) | host tempo proxy; **does NOT drive delay/splice in pedalboard** (no transport) |

## CLEAN measurements
- **Pitch cascade (tone-burst echo FFT, regen=0.75):** pitchoffset=0 → echoes stay at ~1000 Hz (0 c); offset=700 → −709, −1404, −2102 c (steps of −700 per repeat) with simultaneous +700 c grain; offset=1200 → octave staircase.
- **Global pitch:** −1200→−1186 c, +1200→+1211 c (≈1:1).
- **Delay (default tempo):** dv2=731, dv3=481, dv4=231 ms; dv≥5 clamps 231 ms; invariant to tempo_bpm (tempo-locked).
- **Feedback taps:** regen 0.0/0.3/0.6 → 1 / ~10 / 30+ echoes; bounded near 1.0.
- **PingPong:** alternating L/R per repeat (≈110 dB L↔R separation per window).
- **Duck:** gateduck −30 dB → wet tail −57.6 dB (vs −27.6 at 0).
- **mix=0 null:** −18.1 dB (Analog input coloration always present).

## Tempo-sync deferrals
Splice (grain) length and delay time are **note-division params clocked by host tempo**; pedalboard exposes no transport so their **absolute times are unmeasured — needs REAPER transport**. Relative note-grid behavior (ordering, clamps) and *all* pitch/feedback/routing/duck behavior were measured CLEAN.

## To implement (CLEAN-only)
- Granular delay: capture a grain (note-division length, windowed splice) → pitch-shift (PSOLA/overlap-add or phase-vocoder) → write to a fractional delay line → feedback bus.
- **Pitch cascade:** on each feedback pass add `pitchoffset_cents` to the shift accumulator (so repeat *n* is shifted by `pitch_cents + n·pitchoffset_cents`); emit both +offset and −offset grains for the Crystal pair when `fbmode=Mixed`.
- Band-limit the feedback (HP `lowcut_hz`, LP `highcut_hz`) before re-injection to stabilize the cascade.
- Bound feedback gain (soft clip / ≤unity) to allow "infinite" wash without runaway.
- PingPong = swap L/R on the feedback path each pass; Dual = two independent feedback lines.
- Reverse = read the captured grain backward.
- Duck = sidechain (dry → detector, threshold/attack/release) gain-reduce the wet (`duckmode` routes to output / regen / both).
- Optional Analog stage = gentle even-harmonic input saturation for glue.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). No REF (no disassembly performed).
