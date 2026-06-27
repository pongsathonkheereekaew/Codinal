# Tremolator — Soundtoys 5.5 (tremolo / AM)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | Amplitude-modulation tremolo (rhythmic LFO gain, stereo phase offset, envelope/gate trigger) |
| Tech | C++ VST3 over the shared **Soundtoys** framework (statically-linked; co-loading two Soundtoys VST3s duplicates ObjC classes → load one-per-process). AAX=PACE; VST3=clean, pedalboard-hostable. |
| Binary | Universal VST3, not stripped of shared framework; AAX=PACE (not used). |
| Provenance | **CLEAN** — black-box pedalboard measurement of the licensed VST3 + public DSP literature + own description. No disassembly. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys` (`Tools/st_sysid.py`, `Tools/mod_probe.py`; `out/Tremolator_{params,null,probe,mod}.json`) |

## Signal chain
```
x → input gain → [Analog/Digital coloration] → VCA gain = 1 − depth·g(LFO_phase)
     LFO: rhythmic (tempo/rhythm-clocked) shape, swing (groove/feel), accent (accent_db)
     stereo: L/R LFO phase offset = width (0..180°)
     envmode: free-run LFO (Envelope) vs input-gated retrigger (Gate)
  → output gain → y
```
Tremolo = periodic gain (amplitude) modulation. Output spectrum of a carrier f0 = f0 ± rate sidebands.

## Per-stage formula (all CLEAN — black-box)
- **AM gain law / depth (CLEAN):** output = carrier × LFO with `depth` scaling the modulation. Carrier-envelope min/max vs depth (peak held at −9.4 dB = no makeup, modulation goes *downward* only): depth 0→AM 0.04 (residual), 0.25→0.18, 0.5→0.36, 0.75→0.62, **1.0→0.996** (envelope min reaches −62.6 dB = near-total cut). So gain ≈ `1 − depth·(½−½·LFO)` i.e. depth interpolates between unity and full-cut tremolo; max stays fixed (it attenuates from the top, doesn't boost).
- **LFO shape (CLEAN):** measured one envelope cycle at depth=1 (24-pt normalized): smooth rise 0.03→0.46→0.87, a soft plateau ~0.87–0.99, smooth fall to 0.03 — a **rounded near-sine with a slight flat-top** (no hard edges ⇒ not square; curved ⇒ not linear triangle). The default voicing is a smoothed sine/raised-cosine. (Soundtoys' editable rhythm grid can make squarer/spikier shapes; the measured default is the rounded sine.)
- **Rate (CLEAN, fixed at default in pedalboard):** the LFO ran at a **fixed 4.0 Hz** regardless of `tempo_bpm` (60/120/180 BPM → all 4.0 Hz). Tremolator's rate is **rhythm/tempo-clocked** with **no free-Hz param**; without a host transport pedalboard falls back to this internal default. **Rate is tempo-sync: unmeasured as a variable — needs REAPER transport.** Depth/shape/width were all measured at the fixed 4 Hz.
- **Stereo width (CLEAN):** `width` 0–100 % = **L/R LFO phase offset**, linear to 0–180°: width 0→0° (mono tremolo, L=R), 50→89°, 100→**180°** (anti-phase = hard ping-pong / auto-pan-like, one side dips while the other peaks). So width turns a mono tremolo into a stereo "harmonic/rotary" tremolo by phasing the two channels' LFOs apart.
- **Envelope vs Gate (CLEAN):** `envmode` Envelope vs Gate gave **identical** output on a sustained tone ⇒ it controls the **LFO trigger source** — free-running (Envelope) vs **retriggered/gated by the input transient** (Gate), which only differs on a signal *with* transients. On steady input, behaviorally the same.
- **Accent / groove / feel (CLEAN params, rhythm-domain):** `accent_db` ±20 = per-step level accent (emphasize certain beats); `groove` ±0.25 and `feel` ±0.5 = swing/timing offset of the rhythmic LFO. These shape the *rhythm grid* and need a transport to characterize fully.
- **`ratemod_oct` / `depthmod` (CLEAN params):** `ratemod_oct` ±6 = rate modulation in octaves (multiplier on the base rate, ±6 oct = ÷64…×64); `depthmod` ±100 = dynamic depth modulation. Both modulate the base LFO; rate scaling is tempo-relative (deferred).
- **In-stage coloration (CLEAN, important):** **Analog mode adds saturation even at depth=0** — measured 1.99 % THD with **H3 −34 dB dominant** (odd-harmonic) at zero modulation; Digital mode = 0 % THD (H3 −156 dB). So Analog = always-on analog-style coloration (matches the inoutmode gotcha across the suite). Note it when cloning: Analog is not transparent.

## Why / design rationale (music ↔ code)
- **Downward-only AM (attenuate from the top, no makeup)** → tremolo should *duck* the signal rhythmically without changing its loudest level — keeps the part sitting at the same peak in the mix, only adding rhythmic motion. A bipolar boost+cut would change perceived loudness on every cycle.
- **Rounded-sine default shape** → smooth, classic guitar-amp/Rhodes tremolo; no clicks. The editable rhythm grid (squarer/spikier) is for choppy "trance gate" effects — but the *default* is musical and gentle.
- **Width = L/R LFO phase offset** → at 100 % the two channels are anti-phase, giving a wide, rotating, "harmonic tremolo / stereo pan-trem" without an actual panner — motion + width from one LFO. Cheaper and more coherent than two independent LFOs.
- **Gate vs Envelope trigger** → Gate locks the tremolo phase to the performance (each note restarts the pattern → tight, rhythmic), Envelope free-runs (looser, drifts against the groove). Lets the same effect be "tight to the track" or "floating."
- **Accent / groove / feel** → turns a metronomic tremolo into a *grooving* one (swing, ghost-note accents) — the Soundtoys "rhythm engine" philosophy: modulation should feel played, not gridded.
- **Analog mode** → a real tremolo (tube/optical) colors the signal; the even/odd harmonic saturation glues the chopped signal and adds the vintage "throb" character a clean multiply lacks.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| inputgain_db | dB | −24…+24 | |
| outputgain_db | dB | −24…+24 | |
| inoutmode | enum | Digital / Analog (def Analog) | **Analog = always-on saturation (H3 −34 dB even at depth 0)**; Digital clean |
| depth | 0–1 | 0…1 (def 1.0) | AM depth; 1.0 = full cut (−62 dB min), attenuates from fixed top |
| groove | ±0.25 | −0.25…0.25 (def 0) | swing/timing of rhythm grid (tempo-domain) |
| accent_db | dB | −20…+20 (def 0) | per-step level accent |
| width | % | 0…100 (def 0) | L/R LFO phase offset, linear → 0–180° (100 = anti-phase) |
| ratemod_oct | oct | −6…+6 (def 0) | rate modulation (multiplier, tempo-relative) |
| depthmod | % | −100…+100 (def 0) | dynamic depth modulation |
| threshold_db | dB | −80…0 (def −40) | envelope/gate trigger threshold |
| attack_msec | ms | 0.1…5000 (def 500) | trigger/envelope attack |
| release_msec | ms | 0.1…5000 (def 500) | trigger/envelope release |
| envmode | enum | Envelope / Gate (def Envelope) | LFO trigger source (free-run vs input-retriggered) |
| feel | ±0.5 | −0.5…0.5 (def 0) | timing feel/swing (tempo-domain) |
| tempo_bpm | BPM | 30…240 (def 120) | host tempo proxy; **does not set rate in pedalboard** (fixed 4 Hz) |

## CLEAN measurements
- **Depth → AM:** 0→0.04, 0.25→0.18, 0.5→0.36, 0.75→0.62, 1.0→0.996 (min −62.6 dB); max fixed −9.4 dB.
- **Shape (depth=1, 4 Hz, 24-pt env, normalized):** 0.03, 0.03, 0.10, 0.25, 0.46, 0.69, 0.87, 0.87, 0.90, 0.99, 0.94, 0.92, 0.93, 0.87, 0.86, 0.77, 0.50, 0.27, 0.13, 0.04, 0.04, 0.03, 0.02, 0.03 → rounded sine, soft plateau.
- **Width → L/R env phase:** 0→0°, 50→89.3°, 100→180.0°.
- **inoutmode THD (depth 0):** Analog 1.99 % (H3 −34, H2 −68), Digital 0 %.
- **Rate:** fixed 4.0 Hz at all `tempo_bpm` (tempo-sync, no free-Hz param).

## Tempo-sync deferrals
Tremolator has **no free-Hz rate param** — the LFO is **rhythm/tempo-clocked**. In pedalboard (no transport) it free-ran at a fixed 4.0 Hz. **Rate, rhythm patterns, `groove`/`feel` swing, and `ratemod_oct` scaling are tempo-sync: unmeasured — needs REAPER transport.** Depth, shape, width, envmode, and Analog coloration measured CLEAN.

## To implement (CLEAN-only)
- LFO (rounded-sine default; allow editable shapes) → gain = `1 − depth·(0.5 − 0.5·LFO)` (downward AM, peak fixed).
- Stereo: run L/R LFOs with a phase offset = `width/100·180°`.
- `envmode=Gate` retriggers LFO phase on input transients (threshold/attack/release); `Envelope` free-runs.
- Rhythm engine: tempo-locked rate with note divisions + `groove`/`feel` swing + per-step `accent_db` (needs host clock).
- `ratemod_oct`/`depthmod` modulate base rate/depth.
- Optional Analog stage = odd-harmonic (H3-dominant) input saturation, always on in Analog mode.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). No REF (no disassembly performed).
