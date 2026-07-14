# EffectRack — Soundtoys (Container · FX chainer / host)

| | |
|---|---|
| Vendor / ver | Soundtoys 5.5 |
| Type | **Container / host** — not a single DSP algorithm. A serial FX-rack that hosts up to 6 Soundtoys modules in a chain with a global feedback (recycle) path. |
| Tech | C++ VST3, shared "Soundtoys" framework. AAX = PACE; VST3 = pedalboard-hostable, no DRM wall. |
| Binary | universal2 (arm64+x86_64); VST3 not PACE-encrypted. |
| Provenance | **CLEAN** (null/passthrough test + param-surface enumeration of the licensed VST3). No disasm. |
| Measured on | VST3 Soundtoys 5.5 · pedalboard 0.9.17 · SR 48000 · 2026-06-26 |
| Source | `private-research/Soundtoys/` (harness `Tools/st_sysid.py`; data `out/EffectRack_*.json`) |

## What it is
EffectRack is the Soundtoys **multi-effect host**, not a processor. Its own audio path is **unity passthrough** until you insert modules into its slots — so there is no DSP algorithm to recover here. Documented honestly as a container.

## Signal chain
```
x → input gain → [slot1 → slot2 → … → slot6]  (each slot = an inserted Soundtoys effect; empty = unity)
                       ↑___________ recycle (global feedback) ___________|
  → output gain → mix(wet/dry) → out          (tempo_bpm feeds tempo-synced modules)
```
With **no modules loaded** the chain is a wire.

## Measured behavior (all CLEAN)
- **Passthrough confirmed**: a 1 kHz tone in → out nulls against dry at **−400 dB** (bit-exact) in the default empty state. Holds with **recycle = 0 / 35 / 70 %** (the feedback loop wraps the *inserted effects*; with empty slots it has nothing to feed back, so still −400 dB).
- **Zero latency**: impulse peak at the input sample index (0-sample shift) in the empty state.
- **No single DSP** to characterize — behavior is entirely defined by whichever modules the user inserts (each of which is its own plugin spec, e.g. SuperPlate / LittlePlate / SpaceBlender / EchoBoy / Decapitator …).

## Parameters (140 total = 12 named + 128 macro slots)
The large param count is the host's **automation surface**, not DSP knobs.
| param | unit | range | notes |
|---|---|---|---|
| bypass | bool | Off/On | |
| slot1_solo … slot6_solo | bool | Off/On | **6 rack slots**, each soloable → host chains up to 6 Soundtoys effects in series |
| inputgain_db | dB | −24…0 (def 0) | rack input trim |
| outputgain_db | dB | −24…0 (def 0) | rack output trim |
| recycle | % | 0–70 (def 0) | **global feedback** around the inserted chain (no effect when slots empty) |
| mix | % | 0–100 (def 100) | overall wet/dry of the rack |
| tempo_bpm | BPM | 30–240 (def 120) | tempo source for tempo-synced inserted modules |
| unassigned_001 … unassigned_128 | norm | −1…+1 (def 0) | **128 generic automation/macro-assignment slots** exposed to the host (map to inserted-module params); no audio effect on their own |

## Why / design rationale
- **Serial rack + recycle feedback** → Soundtoys' workflow is chaining their characterful effects (e.g. distortion → delay → reverb); wrapping the whole chain in a single global feedback path ("recycle") lets the rack self-oscillate / build evolving textures that no single module could — the headline creative feature of a chainer.
- **128 unassigned macro params** → because the inserted modules vary, the host pre-exposes a fixed bank of automatable slots that get *mapped* to whatever is loaded → stable host automation regardless of the chain contents.
- **6 soloable slots + global I/O + tempo** → a mini mixer/host: audition any one effect (solo), gain-stage the chain, and keep every tempo-synced module locked to one BPM.

## To implement
- **Not a DSP to clone.** If ES-L ever needs a rack/host wrapper, this is the reference architecture: N serial insert slots, a global feedback (recycle) tap around the chain, per-slot solo, rack I/O trim, master wet/dry, a shared tempo, and a fixed bank of host-facing macro params remapped onto the loaded modules. The processing itself lives in the inserted plugins, each specced separately.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe). **REF** = disasm-derived (none used here).
