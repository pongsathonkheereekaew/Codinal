# GodParticleBus — mix-bus chain system-ID (Null Challenge)

**Identity:** a god-particle-class mastering/mix-bus chain, recovered by black-box from a
Pro-Tools session render (dry "Mix pre mix bus" vs wet "REF from PT session").
**Type:** serial multi-FX bus chain. **Provenance:** CLEAN (audio-in→audio-out only; no binary).
**measured_on:** 44.1 kHz stereo WAV pair; pedalboard 0.9.17 + the licensed plugins; 2026-06.
Harness: `private-research/NullChallenge/` (`Tools/`, `god_bus.py`, `FINDINGS.md`).

## Signal chain (hint-confirmed; all components installed + individually REF'd)
`OTT → Saturn 2 → Pro-C 3 → MBMixHead → Pro-MB (3-band) → Pro-L 2`, net **polarity-inverted**.
Per-stage DSP: see [Saturn2.md], [Pro-C3.md], [Pro-MB.md], [Pro-L2.md]. OTT = 3-band up/down
multiband comp (fixed internal xovers, ~1 smp latency, **clean_xov** = cleaner IIR xover, no added latency).

## Measured net transfer (CLEAN)
- align: **REF leads dry by 2005 smp** (45.5 ms, GCC-PHAT, zero drift = PT PDC of chain latency); **polarity inverted**.
- loudness: +5.9 dB RMS, peak pinned 0.00 dBFS (brickwall at ceiling).
- dynamics: ≈1.6:1 upward leveling (−40 dB→Δ+13; −7 dB→Δ+3.5).
- tone: bright tilt +5 dB LF → +11.6 dB @8–16k.

## RESULT: nulled to −18.2 dB (cross-validated) from dry+wet only
`god_bus.py` = 6-plugin chain (tuned dynamics) + baked 2×2 MIMO EQ-match + polarity invert.

## Methodology lessons (reusable — CLEAN) — the winning recipe for nulling a master chain
1. **Align with GCC-PHAT**, not time-domain xcorr (PHAT whitening locks a single-sample offset
   where plain xcorr wandered ±400 smp). Then **LS-gain-match + test polarity** (neg LS gain = inverted).
2. **Run a coherence test first.** `coherence(dry,ref)` = 0.90 here ⇒ the master is ~**linear-time-
   varying**, NOT a nonlinear wall. A god-particle/OTT master = ~90 % static linear (EQ tilt + delay +
   stereo) + ~10 % fast (~20–50 ms) multiband dynamic gain + light sat + brickwall. (Saturation ≈ 0 %
   new-bin energy.) An LTV sweep gives the ceiling: static FIR −10.8 dB → per-frame −27 dB.
3. **Don't search plugin params on the raw null** — the linear tilt mismatch swamps the residual,
   killing the dynamics gradient (caps ~−0.5 dB; basin ~10⁻¹⁰ of a 20-D space). **Put a static Wiener
   EQ-correction in the loop** (`Sxy/Sxx`, fit-win ≠ eval-win so it's honest) and tune only DYNAMICS
   → −16.8 dB; bake a 2×2 MIMO EQ on top → −18.2 dB. STFT-magnitude fitting *worsens* the null (phase-blind).
4. **Reproducibility floor:** OTT self-nulls −58 dB (non-deterministic); any OTT chain floors ~−48 dB
   even same-host. −18 dB is strong for dry+wet; deeper needs the preset or intermediate stage renders.

## Open questions
- The 6-stage breakdown is hypothesis-fit (the FabFilters reproduce the *dynamics* to −17 dB; the
  exact stage params/order aren't uniquely identifiable). REF host/format (PT-AAX vs VST3) caps a deeper null.
