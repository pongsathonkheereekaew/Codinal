# 06 — Sidechain Compression

Compressor reacts to a **trigger signal** (key input), not the audio passing through it. Audio ducks when trigger crosses threshold.

## Three Uses

1. **Ducking** — bass/pad/master ducked by kick so kick punches through (room-making)
2. **Pumping effect** — exaggerated ducking as aesthetic (EDM, house, future bass)
3. **Frequency-targeted dynamic control** — de-essing, ghost-kick triggering, dynamic EQ-style moves

## Mechanism

Sidechain input listens to a *different* track. When that source exceeds threshold, the compressor on the target track reduces gain. Target audio itself never affects detector.

## Typical Settings

| Use case | Ratio | Threshold | Attack | Release | GR |
|----------|-------|-----------|--------|---------|-----|
| Subtle kick→bass duck | 2:1 | just below bass avg (~-10dB) | 0–5ms | 20–75ms | 2–4dB |
| EDM kick→bass/synth pump | 4:1–6:1 | -10 to -15dB | 0ms | tempo-synced (1/8 or 1/16) | 6–10dB |
| Kick→full mix sidechain (pump) | 4:1–∞:1 | hot | 0ms | 80–150ms (matches kick spacing) | 3–6dB |
| De-ess via sidechain key filter | 2:1–4:1 | -15dB | <1ms | 50–100ms | 2–4dB |

## Key Filter on Sidechain Input

- Strips low-end from detector so kick doesn't false-trigger on bass rumble
- For de-essing: HPF detector at 4–6kHz + narrow boost at ~7kHz; compressor only fires on sibilance (4–10kHz range)
- For kick→bass: HPF detector ~50Hz to ignore sub-rumble

## Release Timing

- Subtle ducking: 20–75ms (recovers fast, ducking inaudible)
- EDM pump: release ends *just before* next kick (sync to 1/8 or 1/16)
- Too slow → never recovers → bass missing
- Too fast → audible "click" / no pump character

## Ghost-Kick Trigger

When bass needs to duck but kick isn't playing or isn't on a clean track — feed a muted/silent MIDI kick or click track into sidechain to drive ducking on the grid. Pump exists without the kick being audible.

## Intentional vs Accidental Pumping

- **Intentional:** EDM, house, trance — pump is the groove; mix bus often sidechained for "breathing" feel
- **Accidental:** bus compressor with slow release reacting to kick on full mix → unintended pumping on vocals/pads. Fix: HPF the sidechain detector ~120Hz so compressor ignores kick energy

## Rules

1. Always engage sidechain key filter on bus/master compressors to prevent low-end false-trigger
2. Fast attack (0ms) for clean ducking; slower attack lets kick transient through before ducking
3. Tempo-sync release on EDM pump; clock-based release on natural ducking
4. De-ess via SC compressor + key filter often sounds smoother than dedicated de-esser
