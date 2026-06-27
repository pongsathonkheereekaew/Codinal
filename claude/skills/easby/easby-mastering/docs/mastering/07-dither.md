# 07 — Dither (Katz)

Critical: apply whenever reducing wordlength. Omitting it introduces inharmonic truncation distortion — harsher and more audible than analog noise.

## Wordlength Math

- 16-bit = 96 dB dynamic range; 24-bit = 144 dB; 6 dB per bit
- Every DSP operation expands internal wordlength; DAWs must work at 48–64 bit float internally
- Truncation at 16-bit without dither → inharmonic aliasing correlated to signal → clearly audible in quiet passages

## Dither Types

| Type | Character | Best use |
|---|---|---|
| Flat TPDF | Triangular white noise; 1 LSB; neutral | General purpose; safest default |
| POW-R Type 1 | Noise shaped away from sensitive 3–5kHz | Pop, rock, electronic |
| POW-R Type 2 | Intermediate shaping between Types 1 and 3 | Less-critical material; transitional choice |
| POW-R Type 3 | Most aggressive shaping; ~19–20 bit performance on 16-bit | Classical, acoustic, high dynamic range |
| Auto-dither | DAW applies only when source > target wordlength | Default in most hosts |

## Practical Rules

1. Dither once, at the final step — never mid-chain
2. 24-bit → 16-bit (CD delivery): always dither
3. 24-bit streaming delivery: still apply dither if DAW processes at 32-bit float
4. Audition per genre: classical/acoustic → POW-R Type 3; pop/electronic → TPDF or Type 1
5. Auto-black between tracks: digital silence must be true zeros; enable auto-black if dithering across inter-song gaps (prevents noise burst between tracks)

## Anti-Patterns

- Double-dithering (degrades resolution)
- Forgetting dither on 16-bit CD master
- Applying dither before EQ/compression

**Pro Tools placement:** Master Fader insert slot, last item in the chain. Mirror this in `MasterDecision` — dither = terminal step, never anywhere else.

**References:** iZotope MBIT+, POW-R (bundled in most DAWs), Apogee UV22HR, Weiss Saracon
