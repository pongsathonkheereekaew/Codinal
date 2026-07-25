# saturation — shared public technique

CLEAN (public DSP). Stage decisions (when/how-much) live in Producer/Mixing/Mastering; this is the *how*.

## Shapers (memoryless)
- **tanh** `y=tanh(g·x)/g` — smooth, odd harmonics (H3,H5…), symmetric → no even. Drive = `g`.
- **cubic soft-clip** `y=x−x³/3` (clamp |x|≤1) — odd, gentle knee.
- **hard clip** `y=clamp(x,±c)` — odd, harsh (high odd harmonics + aliasing). FLVTTER-class.
- **arctan / sigmoid** — between tanh and hard; tunable knee.
- **asymmetric** (bias/offset, or different ±curves) → **even harmonics** (H2) = "tube/warm". Symmetric → odd only.

## Harmonic structure (the fingerprint)
- Symmetric ⇒ odd-only (H3,H5,H7). Asymmetric ⇒ adds even (H2,H4) — warmer, "fatter".
- H2 = octave (consonant, fattening). H3 = fifth-ish (edge/grit). Higher odd = harsh/fizz.
- THD rises with drive; the *ratio* of harmonics = the character.

## Stateful (circuit) vs memoryless
- A pure shaper is **frequency-independent** (THD same at 100 Hz and 5 kHz).
- A real analog circuit (diode/transistor + reactive parts) is **frequency-dependent** (THD varies with freq) and may add asymmetry under drive → it has *memory* (AS-1 = re-solved nodal circuit, not a tanh). Test: sweep THD vs **level AND frequency**.
- Diode law `i=Is·(e^(v/nVt)−1)`; transistor pair; tube = soft asymmetric.

## Aliasing / oversampling
- Any nonlinearity creates harmonics above Nyquist → fold back as inharmonic aliasing. **Oversample 2–8×** around the shaper (upsample → shape → downsample) to push images out, or accept the lo-fi character (FLVTTER does NOT OS).

## Implementation
Reuse `../easby-programming/building-blocks/` soft-clip primitive. Build CLEAN from these shapes + public lit (Zölzer DAFX — nonlinear processing; Pirkle). Match a target plugin's measured THD/harmonic table (handoff: `easby-programming/plugins/{AS-1,Saturn2,MELD}.md`).
