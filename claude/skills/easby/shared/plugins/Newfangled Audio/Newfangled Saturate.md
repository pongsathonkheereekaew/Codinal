# Newfangled Saturate — Newfangled Audio (saturation / clipper)

| | |
|---|---|
| Vendor / ver | Newfangled Audio (distributed by Eventide) · v1.12.0 (manual Rev 5, 2018; covers 1.10 anti-aliasing/symmetry/ceiling additions) |
| Type | Saturation / soft-clipper / loudness ("Clip Without Clipping") |
| Format | VST, VST3, AU (Audio Units), AAX |
| Source | manual: `Newfangled Saturate/Newfangled Saturate.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Saturate is the standalone version of the final "Spectral Clipper" stage from Newfangled's Elevate. It overdrives a signal to add loudness, grit and harmonics — but its signature **Detail Preservation** algorithm treats the signal's sine components independently so that loud low frequencies don't swamp the quieter mid/high detail. The result: you can push up to 24 dB of drive without the "tubby", "woofy" or "muddy" smearing typical clippers produce, with the output tonal balance matching the input (only harmonics added). A single SHAPE control morphs from the mathematically smoothest curve to hard clipping, SYMMETRY adds even harmonics for warmth, and an efficient anti-aliasing mode removes aliasing more cleanly than brute-force oversampling. Equally at home gluing a full mix or driving a single track/drum bus.

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **DRIVE** | 0–24 dB (on/off enable dot) | Core control. Adds gain into the clipper for loudness + distortion. First 12 dB follows the SHAPE-determined gain curve; above 12 dB simply pushes the curve harder for more distortion. With output AUTO off, DRIVE adds gain; with AUTO on, it saturates without net gain by reducing headroom. | Main loudness/grit knob — push for density, presence, harmonic excitement. |
| **DETAIL PRESERVATION** | None → All (0–100%) (enable dot) | "The magic." Recovers the fine mid/high detail that ordinary clippers strip when peaks are flattened. 0% = behaves as a standard soft clipper; 100% = all detail preserved (open, tonally neutral saturation). | Turn up to keep a mix open and uncolored under heavy drive; turn down for a more conventional/aggressive clipped character. |
| **CLIPPER SHAPE** | Soft → Hard (0–100%) (enable dot) | Morphs the gain curve from the smoothest possible (0% = minimal harmonics, max boost) toward hard clipping (100% = more harmonics, but quieter sounds less affected). At 0 dB DRIVE, soft and hard shapes are identical. | Soft for transparent loudness/glue; hard for aggressive clipper tone and edge. |
| **SYMMETRY** | -100% → +100% (enable dot) | Makes one side of the clipper curve harder and the other softer, creating an asymmetrical saturator that generates **even harmonics** on top of the odd ones. | Dial in for a richer, warmer, "vintage gear" tone; leave at 0% for pure odd-harmonic symmetric clipping. |
| **CEILING** | -12 dB → 0 dB (enable dot) | Sets the maximum output level / clip threshold. With ANTI-ALIASING off, output never exceeds CEILING. With ANTI-ALIASING on, output may slightly exceed it (correct via lower CEILING or HARD LIMIT). | Set your output clip point; lower it (or use HARD LIMIT) to guarantee a true ceiling when anti-aliasing is on. |
| **MASTER INPUT LEVEL** | gain knob (above INPUT meter) | Trims level into the processor, just before the INPUT meter. | Set how hard the signal hits the clipper independent of DRIVE. |
| **MASTER OUTPUT LEVEL / AUTO** | AUTO button + manual knob (above OUTPUT meter) | AUTO auto-compensates for the gain change DRIVE introduces (constant perceived level for A/B). Click the down-arrow to instead set output manually. Sits just before the OUTPUT meter. | AUTO on for honest loudness-matched auditioning; manual for explicit makeup/trim. |
| **ANTI-ALIASING** | on/off | Engages oversampling + the aliasing-reduction engine; removes the inharmonic "cloudy/muddy" overtones from clipping/saturating sustained harmonic material. Not needed for transient material. Note: when on, output may slightly exceed CEILING. | On when saturating tonal/sustained content; off on pure transients (drums) to save CPU and keep a strict ceiling. |
| **HARD LIMIT** | on/off | Adds a secondary hard clipper after the anti-aliased clipper to guarantee output never exceeds CEILING even with ANTI-ALIASING on. Introduces a small amount of aliasing (less than no anti-aliasing at all). | Use when you need both anti-aliasing AND a true ceiling; leave off if you'd rather lower CEILING and avoid any aliasing. |
| **ACTIVE** | on/off (bypass) | Activates / bypasses all processing in the plug-in (top-left, near logo). | True bypass for in/out comparison. |
| **Δ (Delta Listen)** | on/off | Subtracts output from input so you hear only what the processor is changing/removing. | Audition exactly what the saturation is adding/removing — powerful for dialing detail preservation. |
| **METER TYPE** | radio: GAIN CURVE / WAVEFORM | Selects what the central display shows: the live gain/transfer curve (how signal hits the clip shape) or the waveform. | Gain Curve to read shape/drive interaction; Waveform to watch clipping on the signal. |
| **INPUT / OUTPUT meters** | Peak (ticks) + RMS (bar + numeric) + Peak Hold (numeric) | Mastering-grade in/out metering. Click the Peak Hold readout (or bypass) to clear held peaks. | Gain staging and loudness reference in and out. |
| **GAIN REDUCTION meter** | dB (with peak text readout) | Shows how much gain reduction the saturation algorithm is applying, plus peak GR as text. | Gauge how hard you're clipping/compressing the peaks. |

## Use by lens
- **Producer (create):** Aggressive sound design — high DRIVE + harder CLIPPER SHAPE + add SYMMETRY for thick even-harmonic grit on synths, bass, vocals, guitars. Use Delta + a hard shape to hear and sculpt the distortion. ANTI-ALIASING off on drums/transients for bite and lower CPU. Browse factory presets (Asymmetric Overdrive, Searing Hot, Hard Hitter) as starting points.
- **Mixing (balance):** Drive individual tracks or buses for density and forward presence without dulling them — keep DETAIL PRESERVATION high and SHAPE soft so the source stays open and tonally true. AUTO output on for level-matched A/B so you judge tone, not volume. A touch of SYMMETRY warms a thin source.
- **Mastering (finalize):** Transparent peak control + loudness on the full mix — soft SHAPE, high DETAIL PRESERVATION, modest DRIVE, ANTI-ALIASING on to avoid aliasing artifacts, CEILING set to target (engage HARD LIMIT or trim CEILING to guarantee it). Watch Peak/RMS and GR meters; use Delta to confirm you're only adding harmonics, not shifting tonal balance.

## Notes / gotchas
- **Only two "main" controls** (DRIVE + DETAIL PRESERVATION) by design; SHAPE, SYMMETRY, CEILING, anti-aliasing/hard-limit are the supporting set. Most controls have an enable dot to defeat them individually.
- **CEILING is not a hard guarantee when ANTI-ALIASING is on** — output can creep slightly above it. Either lower CEILING or engage HARD LIMIT (which costs a little aliasing) for a true ceiling.
- **ANTI-ALIASING vs oversampling:** uses an efficient aliasing-reduction method (PFFFT-based spectral processing) that beats high oversampling at a fraction of CPU. Off is fine/preferred for transient-only material.
- **AUTO output** changes the meaning of DRIVE: AUTO on = saturate-without-net-gain (eats headroom); AUTO off = DRIVE adds gain.
- Workflow: pairs naturally **after** a transient designer (e.g. Punctuate) to transparently tame transients you boosted.
- Control gestures: double-click a slider/knob to type a value, Option-click to reset to default, Cmd/Ctrl-click for vernier fine-tune. All controls have hover tooltips.
- Full preset librarian (banks/categories/tags/favorites), A/B compare, multi-level undo/redo, resizable UI, color schemes, OpenGL toggle. PACE/iLok licensing (2 activations).

## Deep spec (Programmer only)
not reverse-engineered — capability only.
