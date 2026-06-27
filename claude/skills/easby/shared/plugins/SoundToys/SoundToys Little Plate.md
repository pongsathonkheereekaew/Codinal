# SoundToys Little Plate — SoundToys (reverb)

| | |
|---|---|
| Vendor / ver | SoundToys · v5.2 |
| Type | Plate reverb (EMT 140 electromechanical-plate emulation) |
| Format | VST3 / AU / AAX (Mac & Windows) |
| Source | manual: `SoundToys Little Plate/SoundToys Little Plate.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Little Plate is a faithful emulation of the classic **EMT 140** plate reverb — the dense, smooth, warm-and-slightly-dark studio-classic sound used on countless records since 1957. Soundtoys studied five real EMT 140 units to capture the vibe, then extended it past hardware reality: decay goes all the way to **infinity** (tails that never fade) and a **Mod** switch adds subtle pitch movement the physical plate can't do. Deliberately simple — just four controls — it's built to be a fast, musical "send-it-to-the-plate" reverb. Distinct for: authentic dense/dark plate character, an infinite-sustain mode usable as a compositional/drone tool, and an aux-send-voiced Mix knob that behaves like riding a reverb return.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Decay** | 0.5 / 1 / 2 / 4 / 8 / 16 / 32 s … ∞ (RT60 @ 500 Hz) | The main control — sets reverb tail length (how long sound takes to fade after entering the plate). Markings are RT60 measurements at 500 Hz; **the maximum non-infinite setting is ~1 minute** (the "red" upper part of the range goes well past the printed 32). Decay is frequency-dependent: **highs always fade faster** than lows at every setting; lows vary a lot with decay (short = tight/controlled, 4–5 s = warm/boomy, tameable with Low Cut). Fully clockwise = **infinite** (see below). | Short for tight room-like ambience; medium for classic plate body on vocals/snare; long/red for huge cavernous spaces. |
| **(Infinite Decay)** | ∞ position of Decay knob (fully CW) | Special endpoint of Decay: the reverberating signal **never fades** — sound sustains indefinitely, continuing to darken/change over time, and new incoming audio keeps feeding/altering the wash. **CAUTION:** sustained loud input builds up energy inside the virtual plate — it can get very loud; watch levels. | Pads/drones, "hold" a chord or moment, live performance / sound-design tool. Automate Decay to ∞ and back to freeze specific passages. Pairs great with Mod. |
| **Low Cut** | 20 Hz – 20 kHz (high-pass) | High-pass filter applied to the signal **before it enters the reverb** — removes lows so the plate doesn't get muddy/boomy. **Affects only the reverb path, not the dry signal.** Because plate lows decay slowly, bass energy naturally builds in the tail; raise Low Cut to reduce low end fed to the plate. | Clean up boomy/muddy tails, keep reverb out of the way of bass/kick, tighten long-decay settings. |
| **Mod** | On / Off (toggle switch) | Introduces **slight modulation** (subtle pitch variation) into the reverb tail — thickens and smooths the sound, adding lush movement impossible on a real plate. Most audible on **pitched** sources (keys, guitar, voice); does little on percussive material (drums). | Add richness/lushness to sustained pitched material, especially at long or infinite decay times. |
| **Mix** | Dry ↔ Wet (0–100%) | Wet/dry blend. **Aux-send-voiced curve** (not a normal 50/50 mix): from 0% up to ~70% it mostly raises the *reverb* level while barely touching the dry (like bringing up a return); past ~70% the dry quickly drops, reaching fully wet (no dry) at 100%. **Dry** = no reverb in output; **Wet** = reverb only. | Set **100% Wet on an aux/send bus** (Soundtoys' recommended use — multiple sources share one plate). Lower values for insert-style blend on a single track. |

## Use by lens
- **Producer (create):** The infinite-decay mode is a creative instrument — freeze chords into evolving pads, play live into the plate as a compositional tool, or automate Decay→∞ to "hold" moments. Mod on long/infinite tails gives lush, slightly detuned washes on synths/keys/guitar/vocals. Great character reverb when you want vintage plate vibe without setup.
- **Mixing (balance):** The workhorse use — set it up as an **aux send at 100% Wet** and bus vocals, snare, keys etc. into one shared plate so everything sits in the same space. Classic plate decay (~1–2 s) on lead vocals and snare; use **Low Cut** to keep the tail from clouding the low mids and to stop bass buildup. As an insert, keep Mix below ~70% for parallel-style blend.
- **Mastering (finalize):** Rarely a master-bus tool (it's a character send reverb with no M/S, EQ, or sidechain). If used at all, keep Mix very low for a touch of cohesive plate "air"; more typically applied earlier in stem/bus reverb sends, not across the final 2-bus.

## Notes / gotchas
- **Decay markings are RT60 @ 500 Hz**; real readout extends past the printed numbers into a red zone up to ~1 minute before ∞. Highs always decay faster than lows.
- **Infinite decay can get LOUD** — sustained loud input accumulates energy in the virtual plate; ride levels / use a limiter downstream.
- **Low Cut is pre-reverb only** — it never touches the dry signal; it shapes what feeds the plate (use it to fight low-end buildup).
- **Mix is aux-voiced**, not linear: 0–70% mainly raises wet, dry collapses after ~70%. Most factory presets are ~100% Wet (designed for send use).
- **Parameter Lock** (Soundtoys-wide): hold **Ctrl+Option** (Mac) / **Ctrl+Alt** (Win) to lock a control (turns red) so it won't change when browsing presets — handy to lock Mix while auditioning presets.
- Mod has the most effect on pitched/sustained material; minimal on percussion.
- Part of the Soundtoys 5 bundle; runs inside the Effect Rack with other Soundtoys plug-ins. Light CPU; no oversampling/latency/sidechain controls exposed in the manual.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
