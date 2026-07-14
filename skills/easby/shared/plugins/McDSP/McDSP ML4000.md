# McDSP ML4000 — McDSP (multi-band dynamics + mastering limiter)

| | |
|---|---|
| Vendor / ver | McDSP · v7.x (manual ©2022, v7.0+) |
| Type | Brickwall look-ahead mastering limiter (**ML1**) + 4-band Gate / Expander / Compressor feeding that limiter (**ML4**) |
| Format | AAX Native/DSP (HDX), AU, VST3 (VST2 dropped as of v7.0); mono + stereo. RTA only in AAX Native/AU/VST3. |
| Source | manual: `McDSP ML4000/McDSP ML4000.pdf` · deep spec: `easby-programming/plugins/ML4000_ML1.md` (limiter core) + `easby-programming/plugins/ML4000_ML4.md` (full 4-band) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
ML4000 is two plug-ins sharing one limiter engine. **ML1** is a flexible brickwall look-ahead mastering limiter with multi-stage peak detection; its standout controls are **Knee** (continuous hard→soft transition that trades loudness for transparency) and **Mode** (six "character" detection algorithms from Clean to Crush) — together the widest range of limiter "styles" McDSP has shipped, from a crushed drum buss to subtle vocal limiting. **ML4** puts a 4-band Gate + Expander (up or down) + Compressor in front of that same limiter, with steep 24 dB/oct crossovers, per-band output gain (a crude graphic-EQ when recombined), per-band solo/link, and simultaneous on-screen display of all three dynamics curves per band. Double-precision, ~1 ms look-ahead latency, supports up to 96 kHz with pull-up.

## Controls (every param → musical effect)

### ML1 limiter section (also the master section of ML4)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Ceiling | 0 to −36 dB | maximum output level — brickwall, output never exceeds it | set true-peak target (−0.3 to −1 dB typical); 0 dB = full scale |
| Threshold | 0 to −36 dB | level where limiting starts detecting peaks; **(Ceiling − Threshold) = max makeup gain** → lower Threshold = louder | push down to drive loudness into the ceiling |
| Knee | 0–100 (%) | limiting transition: 0 = hard/"limiting", 100 = soft. ~0%→0 dB, 25%→3 dB, 50%→6 dB, 75%→9 dB, 100%→12 dB knee | raise (>50%) for transparent vocal/program limiting; low (<10%) for loud drum busses |
| Release | 1 ms – 5 sec | recovery rate after peak reduction; faster = louder + more pumping/distortion | fast (<25 ms, even 1 ms) for max loudness; slow (>300 ms) to tame over-loud, gentler |
| Mode | Clean / Soft / Smart / Dynamic / Loud / Crush | secondary peak-detection character; most audible when Release < 200 ms (very audible < 20 ms) | pick the loudness-vs-distortion tradeoff (see Notes) |

### ML4 master / global
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Gate / Exp / Comp / Limiter enable | on/off (4 buttons) | bypass each dynamics stage + the limiter independently | A/B a stage; run bands as EQ-only with dynamics off |
| Main / X-Over tabs | display mode | Main = per-band sliders + GR curves + IO plots; X-Over = graphic crossover + dynamic IN/OUT/total plot | adjust band splits visually; verify spectral action |
| Display dynamic plot | IN / OUT / DYN | overlays input, output, or total Gate+Exp+Comp action on the spectrum | find which bands hold the signal (noise reduction, vocal work) |

### ML4 per band (×4)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| X1 / X2 / X3 (crossovers) | Hz, graphically draggable | 3 crossover points → 4 bands; steep 24 dB/oct to minimize band leakage | isolate kick/bass/vocal/air regions |
| Gain | dB (per band) | output level of that band before recombine | multi-band "EQ" tilt; rebalance after dynamics |
| Solo (S) / Link (L) / Master (M) | per band | S = audition band (multi-solo allowed); L = link to master band; M = set master band (one at a time) | edit one control across linked bands at once |
| **Gate** Threshold | 0 to −80 dB | level below which signal is attenuated | remove low-level noise/bleed per band |
| **Gate** Range | 0 to −80 dB | depth of gate attenuation (0 = full close) | partial gating vs hard close |
| **Gate** Hold | 2 ms – 2 sec | time gate stays open after dropping below threshold | stop chatter/buzz on sustained material |
| **Gate** Attack | 0.2–200 ms | speed gate opens once above threshold | fast for percussive transients |
| **Gate** Release | 20 ms – 2 sec | speed gate closes once below threshold | match decay tail |
| **Expander** Threshold | 0 to −80 dB | level below which expander acts | set onset for up/down expansion |
| **Expander** Ratio | 1:1 – 20:1 | slope of in→out below threshold (down) / increase (up) | high = fast change; low = gradual |
| **Expander** Range | −24 to +24 dB | max attenuation (−, downward) or boost (+, upward) | **+ values = upward expander** (loudness w/o limiting) |
| **Expander** Attack | 0.2–200 ms | speed gain returns to unity above threshold | transient handling |
| **Expander** Release | 20 ms – 2 sec | speed gain approaches Range below threshold | tail behavior |
| **Compressor** Threshold | 0 to −48 dB | level above which compression occurs | set per-band onset |
| **Compressor** Ratio | 1:1 – 20:1 | amount of gain reduction above threshold | 2:1–4:1 gentle; 8:1+ strong |
| **Compressor** Knee | 0–100 (0 hard, 100 soft) | hard→soft compression transition | soften strong ratios, make GR less apparent |
| **Compressor** Attack | 0.2–200 ms | speed GR engages above threshold | rough estimate: Attack ≈ 1.0 / upper-crossover-Hz |
| **Compressor** Release | 20 ms – 2 sec | speed GR returns to unity below threshold | keep slow in low bands to avoid distortion |
| Threshold Link | per band group | links Gate/Exp/Comp thresholds so moving one keeps relative offsets | hold a constant output level while adjusting one control |

## Use by lens
- **Producer (create):** ML4 is a creature designer — multi-band gate to de-bleed a drum kit (low band low-threshold for kick, others higher), upward expander (Range > 0, Ratio 1.5:1–2:1) for "OTT"-style excitement and loudness without limiting, dynamic-EQ moves (boost air on vocals, fatten low end) via band expander + gain. ML1 on a buss with Knee high as a transparent "ceiling cop."
- **Mixing (balance):** ML4 per-band compression to control a vocal whose tone shifts (plosives in low band, body in mids) without a single-band comp ducking everything; Threshold Link to ride a whole band group at once; band Gain as a recombine-safe graphic EQ that won't overshoot because the limiter caps output. ML1 for gentle buss limiting (Knee > 50%, moderate Release) and peak control.
- **Mastering (finalize):** ML1 is the purpose-built tool — set Ceiling (true-peak target), pull Threshold down for loudness, then sculpt subjective sound with Knee + Mode + Release. Use ML4 ahead of it to correct/augment program (tame a band, multi-band expand for loudness) so the limiter does less work. No internal dither — place a dithering plug-in after ML1.

## Notes / gotchas
- **Mode character ladder** (loudness ↑, distortion ↑): **Clean** = most transparent, least measurable distortion → **Soft** (slightly louder, still transparent) → **Smart** (intelligent, minimizes distortion while raising level) → **Dynamic** (louder than Smart, hint of pumping) → **Loud** (as loud as possible, minimal distortion) → **Crush** (louder than Loud, some distortion). Re-audition Knee whenever you change Mode.
- **Threshold is "drive," not a downward threshold** — loudness comes from lowering Threshold relative to Ceiling (verified in deep spec: norm 0.3 ≈ −16.4 dB).
- **Latency ≈ 1 ms** look-ahead (manual: ~68 samples @44.1k; deep-spec measured 51 samples @48k). Not zero-latency despite a marketing "Zero Latency"/"Low Latency" bullet — it uses a look-ahead delay line.
- **Crossover attack rule:** set band Attack no faster than ≈ 1.0 / (upper crossover Hz) — too-fast attack/release in low bands creates buzzing/distortion. Solo a band to hear its artifacts.
- **Multi-band linking:** one master band (M) at a time; linked (L) bands keep relative offsets and can still be nudged. When automating, automate the master band — automating linked bands too makes their data fight.
- **Preset compatibility:** ML1↔ML4 presets interchange (ML4-only multi-band controls ignored in ML1; ML1 preset disables ML4's Gate/Exp/Comp). LE versions force Mode = Clean and ignore the Mode control.
- **RTA / real-time analyzer** available only in AAX Native, AU, VST3 (not AAX DSP).
- **HDX instance counts @48k:** ML1 mono 8/DSP, stereo 7; ML4 mono 3/DSP, stereo 2.

## Deep spec (Programmer only)
- Limiter core (isolated, cleanest measurement): `easby-programming/plugins/ML4000_ML1.md` — MEASURED CLEAN via REAPER, 10-param dump, threshold-as-drive gain law, true-peak-clean ceiling.
- Full 4-band: `easby-programming/plugins/ML4000_ML4.md` — 118-param surface, per-band defaults, shared master-limiter core identical to ML1/ML8000. Related: `easby-programming/plugins/ML8000.md` (8-band sibling).
