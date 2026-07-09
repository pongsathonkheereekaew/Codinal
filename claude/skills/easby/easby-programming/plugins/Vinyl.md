# Vinyl — iZotope (Lo-fi / vinyl-record simulator)

| | |
|---|---|
| Vendor / ver | iZotope · 1.13.0.605 |
| Type | Lo-fi sim: mechanical/electrical noise, dust, scratch, warp (wow/flutter), wear EQ, year/RPM EQ |
| Tech | iZotope shell + LOCAL core: thin `PluginHooksVST3` → `Contents/Resources/iZVinyl.bundle` (62 MB, NOT shared, unlike Ozone monolith); no PACE, not encrypted |
| Binary | universal (x86_64+arm64); shell 3 syms (stub), core `iZVinyl` bundle holds DSP |
| Provenance | **CLEAN** (pedalboard measurement). No disasm done. |
| Measured on | Vinyl 1.13.0 · 48 kHz · pedalboard 0.9.17 · 2026-06-26 |
| Source | `private-research/CleanMisc/Tools/cleanmisc_sysid.py` |

## Signal chain
```
x → [year/RPM tonal EQ] → [warp = wow/flutter pitch-mod] → [wear HF rolloff]
  → +Σ artifact generators(mech, elec, dust, scratch) → in/out gain → (mono / lo_fi)
```

## Per-stage formula (CLEAN)
- **warp / wow-flutter** (CLEAN): periodic pitch modulation, **rate locked to platter revolution** — 0.50 Hz @ 33 rpm, 0.75 Hz @ 45 rpm (≈1 wobble per revolution, i.e. f≈rpm/60). Depth linear in `warp_depth`: ±1.30 % pitch dev @ 50, ±2.53 % @ 100 (sin model). → classic eccentric-spindle wow.
- **wear** (CLEAN): progressive HF shelf/rolloff (worn-groove dulling). Measured 1k/5k/10k/15k dB: wear0 = +0.2/+0.1/−1.5/−8.0; wear50 = −1.8/−5.8/−15.4/−29.5; wear100 = −3.0/−20/−40/−56.5.
- **year EQ** (CLEAN): era-tonal bandwidth shaping (older year ⇒ narrower band, rolled lows+highs). Distinct response per 1930/1970/2000.
- **lo_fi** (CLEAN): band-limit ~8–10 kHz brickwall-ish (1k −2.6 / 5k −5.2 / 8k −8.2 / 10k −8.6 dB).
- **noise/artifact generators** (CLEAN, additive): mech (centroid ~1.9 kHz, steady rumble/hum), elec (centroid ~1.6 kHz, steady), dust (centroid ~4.9 kHz, sparse bursts), scratch (transient cracks, loud — peak +13 dB @ gain 20). Each independent level (dB) + amount (%).

## Why / design rationale
- Wow rate = rev/60 → the wobble *sounds like a record* because the listener's ear locks pitch drift to platter speed; depth as a separate knob = exaggeration control.
- Wear as HF-only loss → emulates groove abrasion (treble dies first); year EQ → bandwidth of the era's cutting/playback chain. Together = age without touching the program's body.
- Separate, spectrally-distinct noise layers → user dials a specific decade's noise signature.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| input_gain_db / output_gain_db | dB | −30..+20 | |
| mech_noise_db / elec_noise_db | dB | −inf..+20 | steady noise beds |
| dust_gain_db / dust_amount | dB / % | −inf..+20 / 0..100 | sparse bursts |
| scratch_gain_db / scratch_amount | dB / % | −inf..+40 / 0..100 | loud transients |
| wear | % | 0..100 | HF rolloff depth |
| warp_depth | % | 0..100 | wow/flutter depth (±1.3%/50) |
| warp_model | enum | Sin/… | LFO shape |
| year | year | 1930..2000 | era tonal EQ |
| rpm | rpm | 33/45/78 | sets wow rate (rpm/60 Hz) |
| mono / lo_fi / spin_down | bool | | spin_down = tape-stop pitch glide |

## CLEAN measurements
Wow rate vs rpm: 33→0.50 Hz, 45→0.75 Hz. Warp depth: ±1.30%/50, ±2.53%/100.
Wear HF (see formula). Noise centroids: mech 1.9k, elec 1.6k, dust 4.9k, scratch 2.4k.

## To implement
Wow = single-LFO fractional-delay pitch-mod, rate = rpm/60, depth-scaled. Wear = 1-pole HF shelf, depth-mapped. Noise = filtered-noise beds + Poisson-triggered click/crackle bursts. All CLEAN-measured; reusable lo-fi block for ES-X-style character.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing.
