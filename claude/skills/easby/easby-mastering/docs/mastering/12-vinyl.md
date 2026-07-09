# 12 — Vinyl Mastering

Vinyl is a physical-medium master — different rules from digital streaming.

## RIAA Pre-Emphasis Curve

- Cut: bass attenuated, highs boosted by lathe (prevents wide low-frequency groove modulation, lifts highs above surface noise)
- Playback: turntable preamp applies inverse curve → flat response
- Mastering implication: the cut process *exaggerates* anything that's already harsh in the highs or wide in the lows — sibilance and stereo bass become problems the moment the lathe touches lacquer

## Mandatory Cutting Constraints

| Constraint | Rule | Why |
|---|---|---|
| Mono below 150 Hz | Sum L+R to mono on everything < 150 Hz (≤ 100 Hz acceptable for classical) | Stereo bass = horizontal groove modulation; needle skips |
| De-essing 6–10 kHz | Stricter than digital; tame any sibilance hitting ~-6 dBFS in this band | Cutting stylus distorts on hot HF; vinyl playback amplifies it |
| HF limiting / LPF | Some cutting engineers LPF at 14–16 kHz or use acceleration limiting | Stylus heat / overshoot on very loud HF transients |
| Transient control | Avoid brick-wall square-wave masters | Lathe can't translate clipped transients into physical groove → flat, distorted cut |
| Loudness target | **-12 to -9 LUFS integrated** (≈ 4–6 LU quieter than streaming) | Hot cuts distort + reduce playing time |

## Side-Length vs Loudness Trade-Off (12-inch LP)

| Loudness | 33⅓ RPM max | 45 RPM max |
|---|---|---|
| Loud (~+4 to +6 dB) | 8–11 min | 6–8 min |
| Moderate (~0 dB) | 15 min | 11 min |
| Quiet (~-6 dB) | 22 min | 18 min |

Longer side = narrower grooves = lower cut level. Communicate side length to cutting engineer before mastering.

## Deliverable

24-bit / 48 or 96 kHz WAV, per side, **with 1 second of silence at start, 3 seconds at end**. No dither (cutter applies its own at lacquer cut). Optional separate side-A / side-B masters with different loudness if sides differ in length.
