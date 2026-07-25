# Klevgrand Gaffel — Klevgrand (utility / band splitter)

| | |
|---|---|
| Vendor / ver | Klevgrand · © 2024 (Klevgränd Produkter AB) |
| Type | Utility — synced Linkwitz-Riley band splitter (frequency crossover) |
| Format | macOS: AU/VST/AAX (64-bit) · Windows: VST/AAX (64-bit) · iOS: AUv3/Standalone |
| Source | manual: `Klevgrand Gaffel/Klevgrand Gaffel.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Gaffel ("fork" in Swedish) splits an audio signal into up to four frequency bands using a classic **Linkwitz-Riley crossover**, so the sum of all bands has a flat amplitude response and a smooth, continuously-changing phase response. It is not itself an effect — its job is to let you turn *any* plugin into a multiband effect: duplicate a signal across up to four channels, put Gaffel on each, mute the bands you don't want on each channel, and insert your own effect on the surviving band. The standout feature is **global crossover sync**: instances tagged to the same group share their crossover frequencies, so dragging a thumb on one channel moves it on all the others — keeping the split coherent across the duplicated channels in any DAW.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **A · Crossover Frequency** (thumbs) | Hz/kHz — up to 3 draggable thumbs (4 bands) | Sets the split points between adjacent bands by dragging the thumbs along the spectrum. Linkwitz-Riley filters → flat summed magnitude, smooth phase. Hold **Alt/Option** while dragging for fine adjustment; **double-click** a thumb to reset to default. | Define where each band begins/ends — e.g. carve a "low / low-mid / high-mid / air" split to target an effect at just one region. |
| **B · Band On/Off** | per-band toggle (4 bands) | Click a band to mute/unmute it. Determines which part of the spectrum passes through *this* instance. | The core of the multiband trick: on each duplicated channel, leave on only the band you want that channel's effect to process. |
| **C · Tonality (Group)** | 1–8 (group selector) | Assigns this instance to one of 8 groups. Crossover frequencies sync **only** within the selected group. | Use one group per multiband chain so its channels stay locked together; use a *different* group for an unrelated split elsewhere in the session so the two don't fight over crossover positions. |
| **D · Zoom** | toggle | Toggles the zoom level of the frequency display area. | Zoom in for precise thumb placement; zoom out for the full-spectrum overview. |

**Special keys (global):** Hold **Alt/Option** to fine-tune any control · **double-click** any control to reset it to default.

## Use by lens
- **Producer (create):** The "any plugin → multiband" engine. Duplicate a track to up to 4 channels, drop Gaffel on each, solo a different band per channel, then chain creative processors per band — multiband distortion, band-specific delays/reverbs, parallel saturation on only the lows, a chorus on only the highs. Put all the channels in the same Tonality group so the crossovers move together as you taste-tune the split.
- **Mixing (balance):** Build surgical multiband chains your compressor/EQ doesn't natively offer — e.g. transient shaping on the mids only, de-essing via a high-band-only gate, or sidechain-ducking just the low band. Because Linkwitz-Riley keeps the bands summing flat, splitting and recombining is phase-coherent and won't tonally color the bus when bands are untouched.
- **Mastering (finalize):** Use sparingly. Viable for routing a master into bands to apply a different finalizer or stereo tool per band, but note it requires duplicating the signal across channels and re-summing — verify a true null when all bands are on/unprocessed before committing on a master.

## Notes / gotchas
- **Not an effect by itself** — it only splits. The processing comes from whatever plugin you insert on each band's channel; muted bands carry no signal.
- **Up to 4 bands / 3 crossover thumbs.** Fewer bands = mute the ones you don't need.
- **Global sync is per-group (8 groups).** Same group = shared crossovers; different group = independent. If splits in two separate chains keep moving each other, they're on the same group — change one.
- **Linkwitz-Riley topology:** flat summed amplitude, smooth phase response — bands recombine cleanly. (Note: LR crossovers introduce phase rotation, so a single band soloed isn't phase-flat against the dry signal, but the *sum* of all bands is amplitude-flat.)
- **Workflow is channel-duplication-based**, not a single multiband instance — set it up in the DAW by routing duplicated copies, one per band.
- **Demo limitation:** unlocked via the Demo label (bottom-left); until licensed it outputs ~1 second of silence intermittently. Licensing is desktop-only.
- No oversampling / latency / sidechain controls exposed; minimal CPU (it's just crossover filtering). Resizable window; macOS build requires OpenGL.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
