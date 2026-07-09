# PSP VintageWarmer2 — PSP Audioware (saturation / compressor / limiter)

| | |
|---|---|
| Vendor / ver | PSP Audioware · v2.10.0 (manual © 2002–2022) |
| Type | Analog-style saturation + soft-knee compressor / brick-wall limiter (single- or multi-band), with tape-style overdrive and EQ |
| Format | VST3 / VST / AU / AAX (64-bit; up to 192 kHz); iLok License Manager (no dongle required) |
| Source | manual: `PSP VintageWarmer2/PSP VintageWarmer2.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A digital emulation of an analog-style compressor/limiter that adds tape-like saturation, density, and warmth. The same level-detection engine spans soft-knee compression all the way to brick-wall limiting, with an overload character modeled on analog tape recorders (musical distortion when driven hard). It runs in two modes: **Single Band** (full-range tape emulation with low/high shelving EQ — dense, characterful, slightly distorted) and **Multi Band** (3-band soft-knee limiter feeding a common 4th hard brick-wall limiter — transparent loudness/glue for mixes and masters). VintageWarmer2 adds **FAT** mode (proprietary Frequency Authentication Technique — double-sampled / FIR oversampled processing) for cleaner, more analog-like saturation with fewer aliasing artifacts when pushed, at the cost of ~15 ms latency and >2× CPU. The installer ships three variants sharing the same sound engine: **MicroWarmer** (single-band, lowest latency ~1.5 ms, for tracking/live), **VintageWarmer LE** (low latency ~3 ms, for mixing), and **VintageWarmer2** (FAT mode, for groups/bus/mastering).

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Drive** | −24…+24 dB (def 0) | Input level into the limiter — the main "how hard you hit it" knob; more drive = more compression + saturation. Active only when On switch is engaged. | Set the amount of density/loudness; the primary character driver. |
| **Knee** | 0…100 % (def 50) | Knee shape. 0 % = hard knee bent at 0 dB (limiting). Mid = analog tape-style behavior. 100 % = wide soft knee for deep, fast compression. | Low for limiting/brick-wall; mid for tape color; high for gentle dense compression. |
| **Speed** | 0…100 % (def 50) | Combined attack + release time, framed as "tape speed". 0 = slow tape = very fast (snappy) timing; 100 = fast tape = smooth, slow timing. | Fast (low) to grab transients/limit; slow (high) for glue and smoothness. |
| **Release (RelMul)** | multiplier ×¼…×2 std; def ×1 | Release multiplier relative to the Speed setting. Long button shifts the whole range 16× longer. | Fine-tune pumping/recovery without changing Speed. |
| **Ceiling** | dB (def 0 dB) | Max output level before the final brick-wall stage — keeps normalized signals from exceeding 0 dBFS even when set above it. Interacts with rear-panel Low/Mid/High Saturation in multi-band. | Set the true output ceiling; in MB it's the reference the band Saturation knobs work against. |
| **Mix** | 0…100 % (def 100) | Dry/wet (parallel) blend. 0 % = bypass (signal passes unaltered); 100 % = fully processed. | 30–60 % for parallel density/character while keeping transients alive. |
| **Output** | dB (def 0 dB) | Final makeup/output trim — last stage in the chain (after metering Post point). | Match levels / set final output after driving. |
| **High Freq** | def 4 kHz | Single Band: high-shelf EQ frequency. Multi Band: high-band crossover frequency. | Voice the top end (SB) or set where the high band splits (MB). |
| **High Adjust** | dB (def 0 dB) | Single Band: high-shelf gain. Multi Band: high-band pre-limiter gain (drives how hard the high band compresses). | Brighten/darken (SB) or push the high band harder (MB). |
| **Low Freq** | def 100 Hz | Single Band: low-shelf EQ frequency. Multi Band: low-band crossover frequency. | Voice the lows (SB) or set the low split point (MB). |
| **Low Adjust** | dB (def 0 dB) | Single Band: low-shelf gain. Multi Band: low-band pre-limiter gain. | Add/remove weight (SB) or drive the low band harder (MB). |
| **Auto** (button) | on/off | Auto-release — continuously readjusts release to follow program content for smoother sound and lower distortion (still scaled by Speed + Release). | Leave on for transparent, self-adapting release on complex material. |
| **Long** (button) | on/off | Extends Release Multiplier range — its scale begins where standard mode ends, giving up to 16× longer release. | Very slow, smooth recovery on bass-heavy or mastering material. |
| **Brick Wall** (button) | on/off | Engages true brick-wall clipping on the output limiter (SB) or the whole output limiter (MB). When on, absolutely no transients pass over 0 dBFS. | Final-stage safety / hard ceiling for mastering and broadcast. |
| **On / Off** (switch) | on/off | Master processing engage. When Off, everything is bypassed except VU metering. | A/B the processed vs. clean signal. |
| **Off / FAT** (switch) *(VW2 only)* | off/FAT | Engages double-sampled FAT (oversampled) processing — cleaner saturation, fewer aliasing artifacts when driven hard; also makes the shelving/crossover filters behave more "analog". Costs >2× CPU and large buffers (high latency). | Mastering, lead tracks, or any time you push it hard and want clean overdrive. |
| **Single / Multi** (switch) | SB / MB | Selects mode. Single Band = full-range tape emulation + shelving EQ (dense, characterful, distorted). Multi Band = 3-band soft-knee limiter + common hard brick-wall output limiter (smooth, transparent). | SB for tracks/tape color; MB for mixes/mastering glue and loudness. |
| **Mono / L / R / Stereo** (switch) | Mono / L / R / Stereo | Channel routing. Mono = process first channel, copy to both outs. L or R = process one channel only (for unlinked dual-instance use). Stereo = process both (more CPU; not for mono sources). *(Automation: split into MonoStereo + a new LR parameter.)* | Mono for mono sources; Stereo for stereo material. |
| **Link Off / Link On** (switch) | linked / unlinked | Links the two channels' level detectors. Link On = common detector → stable stereo image (preferred). Link Off = shared settings but separate detectors per channel (more CPU). | Link On for normal stereo; Link Off only when channels need independent correction. |

### Metering controls (front panel)
| control | options | what it does |
|---|---|---|
| **Pre / G.R. / Post** (switch) | Pre / G.R. / Post | Meter pickoff point. Pre = level after EQ (pre-processing). G.R. (default) = gain reduction. Post = level after all processing + Output knob. |
| **VU / PPM** (switch) | VU / PPM | Meter mode. VU = averaging analog ballistics (def 300 ms integration). PPM = pseudo-peak (def 10 ms attack / 2000 ms return; set attack 0 for true digital peak). |
| **Overload LEDs** | click to reset | Light when ≥ N samples hit ≥ 0 dBFS (N = rear-panel Overs counter, def 3). Stay dark-red after an over until clicked. |

### Rear panel (right-click bottom logo) — preferences + multi-band depth
| control | range / unit | what it does | scope |
|---|---|---|---|
| **Low / Mid / High Saturation** *(MB only)* | ±12 dB VW2 (±6 dB in VW1); def 0 | Per-band ceiling relative to front Ceiling. Negative = lower band ceiling → more band compression, less work for the output limiter; positive = less band processing, more to the output limiter. | Stored in preset/session |
| **Low / Mid / High Release** *(MB only)* | ×0.0625…×16 VW2 (×0.25…×4 in VW1); def ×1 | Per-band release multiplier (multiplied by front Release knob). Longer on lows = smooth/low-distortion bass; shorter on highs = faster top-end recovery. | Stored in preset/session |
| **Fine adjust** | def 100 % | Sets the operating range (multiplier) for Drive, Low Adjust, High Adjust, Ceiling, Output. (Ceiling/Output multipliers counted differently; displayed % ≠ their multiplier.) | Stored in preset/session |
| **VU Integration Time** | def 300 ms | VU needle ballistics. 400–600 ms = smoother reading. | Preference (global, not per-session) |
| **0VU Reference Level** | def −18 dBFS | Sine reference for 0 VU (−18 dBFS ↔ +4 dBu on a +22 dBu@0 converter). Set to −12/−10 dBFS for hot modern mixes. | Preference |
| **PPM integration / return time** | def 10 ms / 2000 ms | PPM attack and return ballistics (return recommended 1–2 s). | Preference |
| **Overs counter** | def 3 samples | How many ≥0 dBFS samples trip the overload LED. | Preference |
| **Knob Mode** *(VW2 only)* | linear / circular (def linear) | Knob drag behavior. | Preference |
| **VU / PPM / Overs Reset** (buttons) | double-click | Recall factory defaults for that meter group. | — |

## Use by lens
- **Producer (create):** Reach for **Single Band** on individual tracks to add tape-style warmth, grit, and density — drums, bass, gtr, vocals. Push **Drive** for color, set **Knee** mid for tape behavior, and use **Mix** at 30–60 % for parallel saturation that keeps transients punchy. Use the low/high shelves to voice the tone. For low-latency tracking/live use **MicroWarmer**.
- **Mixing (balance):** Use on the **mix bus** or groups for glue and "density". **Multi Band** keeps it transparent; the per-band **Saturation** and **Release** (rear panel) let you tame boomy lows (negative Sat / long release) and keep the top open (positive Sat / short release). Set the meter to **G.R.** and aim for a few dB of gentle reduction. Watch for the analog character — a little goes far. Use **LE** version for lowest latency in busy sessions.
- **Mastering (finalize):** This is **VW2 + FAT** territory. **Multi Band** for transparent loudness, or **Single Band** for vibe/cohesion. Set **Ceiling** for the target output max, engage **Brick Wall** for an absolute 0-dBFS-safe ceiling, and use **Auto** release for smoothness. Calibrate VU **0VU reference** to −14/−12 dBFS for modern loudness, and use **Post** metering + overload LEDs to confirm no overs. PSP explicitly recommends VW2 (FAT) for masters, groups, and master busses.

## Notes / gotchas
- **Two distinct modes, opposite jobs:** Single Band = colorful tape saturation + shelving EQ (dense, distorted on purpose); Multi Band = clean 3-band limiter + hard output limiter (transparent glue/loudness). The same knobs change meaning between modes (High/Low Freq = shelf freq in SB, crossover in MB; High/Low Adjust = shelf gain in SB, band drive in MB).
- **FAT = latency + CPU.** FAT (VW2 only) uses FIR double-sampling → ~15 ms latency and >2× CPU; PSP recommends LE/MicroWarmer for multitrack work unless FAT's clean overdrive is specifically needed. Latency is reported (samples + ms) at the bottom of the editor and is delay-compensated by modern DAWs. Approx latencies: MicroWarmer ~1.5 ms, VW/LE ~3 ms, VW2 (FAT) ~15 ms — all sample-rate dependent.
- **Ceiling vs. brick wall:** Ceiling sets a working max but can momentarily overshoot in multi-band (it doesn't govern every stage); engage **Brick Wall** to guarantee nothing exceeds 0 dBFS.
- **Rear panel split:** Multi-band **Saturation/Release** and **Fine adjust** are saved with the preset/session; all **meter/LED/Knob-Mode** settings are *preferences* — global, loaded on insertion, saved from the last closed instance (remove the plugin to persist a preference change).
- **VU calibration matters.** Default 0 VU = −18 dBFS (+4 dBu / +22 dBu@0). Modern hot mixes read better with reference set to −12 or −10 dBFS.
- **CPU savers:** Stereo mode and Link-Off both consume extra CPU; use Mono/Link-On where appropriate. Stereo mode is not recommended on mono sources.
- **Presets:** Factory presets are built-in and not editable (Application tab), categorized (Mix Bus, Multiband comp & lim, Guitar, Bass, Drums, Vocals, Tape, etc.). Save your own under the **My presets** tab → `~/Documents/PSPaudioware.com/User Presets/PSP VintageWarmer2`. Plus Copy/Paste between instances, A/B + A→B, Undo/Redo, scroll-to-resize GUI (double-click = 100 %), and a CONFIG (≡) menu for manual/version/hints.
- **MicroWarmer differences:** single-band only (no Multi/FAT/Brick Wall/Ceiling/Mix/Auto/Long), no per-band rear controls — just Drive, Speed, Knee, Low/High Freq+Adjust, Output, Mono/Stereo, Link. Same sound engine, lowest latency, best for tracking/live.

## Deep spec (Programmer only)
Not reverse-engineered — capability only.
