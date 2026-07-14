# <NAME> — <Vendor> (<Type>)

| | |
|---|---|
| Vendor / ver | |
| Type | Limiter / Compressor-Leveler / Multi-FX dynamics / Saturation / … |
| Tech | C++/JUCE? Rust? FFI boundary? UI? |
| Binary | arch, stripped?, DRM?, leaked build paths |
| Provenance | which facts are CLEAN (measured) vs REF (disasm) |
| Measured on | plugin vX.Y · SR · harness/tool · date (plugins change — pin it) |
| Source | `private-research/<NAME>/…` |

## Signal chain
```
x → stage1 → stage2 → …
```

## Per-stage formula  (tag each CLEAN or REF)
- **<stage>** (REF @0x… / CLEAN): formula, constants, units.

## Why / design rationale (music ↔ code — the deep layer's job)
For each notable DSP choice, capture **why**: the musical purpose it serves + why *this* method over alternatives.
This is what makes the Programmer the superset — not just *what* the code does, but *why* the designer did it.
- **<choice>** → musical effect → purpose. e.g. "RMS (not peak) detector → smooth, loudness-like gain → gentle
  'leveler' feel, not transient clamping" · "lookahead + true-peak ceiling → catch inter-sample peaks → safe for
  lossy codecs" · "asymmetric shaper → even harmonics → 'tube warmth'." Connect curve/constant → behavior → intent.

## Parameters
| param | unit | range | notes (normalized? seconds vs ms? dB?) |
|---|---|---|---|

## FFI contract (if clean C ABI)
- create / process / set / get signatures; register types; init/un-mute; latency.

## CLEAN measurements
curves / times / harmonics tables.

## To implement
building blocks to reuse; CLEAN-only path for product (e.g. ES-L).

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reference only — reproduce black-box before shipping).
