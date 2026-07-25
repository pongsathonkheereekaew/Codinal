# 09 — Noise Reduction (Katz)

Tiered approach: always use the lightest effective tool.

## Tier 1 — Simple HP Filtering

- Cut below 20–40Hz: removes hum fundamental and subsonic rumble
- Artifacts: none if slope is gentle (6–12dB/oct)

## Tier 2 — Narrow-Band Expansion

- Upward expansion 1–4dB in 3–5kHz range; gate opens when music is loud (noise masked), partially closes in quiet passages
- Less destructive than broadband gating; risk = gurgling artifacts at poor threshold setting

## Tier 3 — Complex Filtering (statistical model)

- Capture noise profile from silence sample; subtract estimated noise across spectrum (Cedar, Sonic Solutions No-Noise, iZotope RX Spectral Denoise)
- Artifact: "underwater" sound if reduction set too deep
- Rule: use minimum effective amount — artifact is always worse than the original noise
- Always A/B bypass before committing

## Tier 4 — Specialized Repair

- Cedar Retouch / iZotope RX: impulse noise (clicks, pops, crackle) — single-event removal
- TC Backdrop: continuous noise (hiss, HVAC, tape hiss)
- iZotope RX Spectral Repair: spectral painting for complex localized noise

## Golden Rule

Never apply noise reduction to content that will be masked by music most of the time; treat only audible gaps (pauses, rests), not the full track.
