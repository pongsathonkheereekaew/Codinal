# AL-1 (Alpha 12) — Brickwall Limiter  [reference target]

| | |
|---|---|
| Vendor / ver | research target "AL-1 Alpha 12" (VST3) |
| Type | Brickwall limiter — pure per-sample scalar gain `out[n]=in[n]·g[n]`, `0<g≤1` (strictly attenuating) |
| Provenance | **CLEAN** — 100% black-box system-ID (oracle reproduces to −326 dB ⇒ no hidden nonlinearity/sat/dither, deterministic) |
| Measured on | AL-1 Alpha 12 · Gen1 engine · os=0/tp=0 · probe scripts (sid*/probeOS/determ) |
| Source | `private-research/AL-1/` — `docs/al1-formula.md` (gain law), `adaptive-tc-design.md` |

## Gain law (CLEAN)
```
ceil   = 0.9886                                     # −0.10 dBFS sample-domain ceiling
req[n] = max(0, 20·log10(|x[n]| / ceil))            # required GR, dB ≥0  (HARD knee, ratio 1.000, exact log)
GRanticip[n] = MAX over k=0..La ( req[n+k] − phi[k] )   # PURE-MAX combine + attack penalty, lookahead La≈2–5
GR[n] = rising ? GRanticip[n]                        # attack: instant to anticipated max
        : held<HOLD ? GR[n-1]                        # hold ~1 sample at peak
                    : GR[n-1] − relRate              # release: linear-dB one-pole
g[n]  = 10^(−GR[n]/20)
```
Constants (measured): detector = instantaneous `|x|` sample-domain (no pre-filter/OS at os=0); **knee HARD**
(GR/over-dB = 1.000); combine = **PURE MAX** (isolated peaks → 0 excess, not additive); attack slew `phi`
≈ **2.18 dB/sample**, lookahead-capped ~4–5 samp (lead grows with depth: 0@2 dB, ~3@12 dB); release **LINEAR
0.272 dB/sample**, constant across depths; **no memory** beyond lookahead + release pole (`GR[n]=f(local window)`).

## Building blocks (→ building-blocks/)
Pure-scalar-gain limiter · exact-log hard knee at ceil 0.9886 · max-combine over lookahead with `phi` attack
slew · linear-dB release one-pole. All CLEAN — measurement-sourced, product-safe behavior_targets.

## Notes
Topology is the OPPOSITE of a symmetric-lookahead limiter (cf. Pro-L 2): asymmetric reshaper, per-sample.
Use `private-research/AL-1/` probe scripts to re-measure. Two combine voicings observed (pure-max for
isolated transients; a softer blend fits dense/tone clusters better on a peak-weighted null).
