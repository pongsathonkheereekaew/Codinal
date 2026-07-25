> 📎 Technique core (shared/public): [../../../shared/dynamics.md](../../../shared/dynamics.md). This file = **mastering application only** — don't duplicate the technique here.

# 04 — Limiting in Mastering

**Limiter role:** brick-wall ceiling control. Ratio 10:1+. Sets the absolute peak ceiling (-0.1 to -1.0 dBFS). Raises average loudness without changing internal dynamics.

## Transparent Digital Limiting (Katz)

- Short-duration transients on unprocessed digital sources can be reduced 4–6 dB with minimal audible effect
- This does NOT apply to analog tape masters — tape has already lost short transients in recording; further limiting causes distortion
- Short peaks = inaudible by ear but waste headroom; safe to limit
- Long sustained peaks = audible; limiting causes distortion

## The Most Transparent Limiter Is No Limiter At All (Katz — PRIMARY TECHNIQUE)

**Manual limiting via DAW automation should be tried before any plugin limiter** when only a handful of peaks exceed the target ceiling. Place a short gain-drop (DAW clip-gain or volume automation) directly on the offending peak:

| Parameter | Value |
|---|---|
| Duration | < 3 ms (1–2 ms ideal) |
| Reduction | 1–3 dB |
| Curve shape | Quick taper in, quick taper out (no sharp edges) |

**Why this beats a plugin limiter:**
- Zero pumping (no envelope detector chasing the signal)
- Zero attack/release tradeoff (you place the drop exactly where needed)
- Zero inter-band crosstalk (vs. multiband limiter)
- Inaudible at < 3 ms duration even at 3 dB depth

**When to escalate to a plugin limiter:**
- More than ~15 peaks per song need taming → automation tedium > artifact cost
- Sustained loudness target requires consistent gain riding (LUFS streaming targets)
- Automation rendering not supported by the chain

⚡ **Rule:** for the last 1–2 dB before the ceiling, automation > plugin limiter. For the bulk loudness lift, plugin limiter (preceded by saturation if needed) is correct.

## Limiter Settings

- Ceiling: -0.3 to -1.0 dBFS (streaming standard -1.0; club/DJ masters -0.3)
- Release: 50–100ms typical; too fast → distortion; too slow → pumping
- Saturation pre-limiter (optional): adds harmonic warmth, softens transients before brick-wall; use on digital sources that sound harsh

**Hardware references:** Waves L1/L2, UA Precision Limiter, T-RackS Brickwall
