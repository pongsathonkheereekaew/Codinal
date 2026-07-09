# EQ / filtering — shared public technique

CLEAN (public DSP). Stage decisions live in Producer (synth filter/timbre), Mixing (surgical/tonal per-track),
Mastering (broad / M-S, gentle). This is the *how*.

## Band types
- **Bell / peak** — center `f`, gain `±dB`, `Q` (bandwidth). Q = f/Δf; high Q = narrow.
- **Shelf** (low/high) — boost/cut everything below/above a corner; `S`/Q shapes the knee.
- **HPF / LPF** — cut below/above corner; slope `dB/oct` (6/12/24/48 = order 1/2/4/8).
- **Notch** — deep narrow cut (hum/resonance removal).

## Implementation = biquad (RBJ cookbook)
Each band = a biquad (2-pole). `Q`, `f0`, `gain` → coefficients (Robert Bristow-Johnson cookbook). Cascade bands. SVF (state-variable) is an alternative with cleaner modulation. Reuse `../easby-programming/building-blocks/` biquad.

## Phase
- **Minimum-phase** (analog-style, default) — cheap, 0 latency, but phase shift near moves (can smear transients / cause comb when summing).
- **Linear-phase** (FFT or long FIR) — no phase shift, but **latency** + pre-ring. Mastering/M-S often wants linear; tracking wants min-phase.

## Q / gain interaction
- Boost: high Q = surgical/resonant; low Q = broad/musical. Cut: high Q = surgical removal.
- Constant-Q vs proportional-Q (Q widens as gain drops) — analog EQs are often proportional (AE-1 = ERB-proportional).

## M/S
Process Mid (L+R) and Side (L−R) separately: e.g. cut Side lows for mono-bass; boost Side highs for width. Mastering/imaging use.

## Stage application (don't duplicate here)
Producer = filter as part of the patch (VCF, brightness). Mixing = fix balance, carve masking, tonal shape per track (±15 dB, can be surgical). Mastering = broad ±6 dB, gentle Q, often M-S, min- or linear-phase. Target a researched EQ via handoff (`easby-programming/plugins/{AE-1a,Pro-Q4}.md`).
