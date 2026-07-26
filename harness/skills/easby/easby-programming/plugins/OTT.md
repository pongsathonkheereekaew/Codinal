# OTT — Xfer Records (3-band Upward + Downward Multiband Compressor)

| | |
|---|---|
| Vendor / ver | Xfer Records · OTT (free) · build Jan 2023 (universal x86_64+arm64) |
| Type | Multiband dynamics — 3-band **upward AND downward** compressor ("over-the-top" smasher) |
| Tech | C++ VST2-SDK `AudioEffectX` (`OTTProcessor`) wrapped as VST3 (`vst3wrap.def`); ChunkWare "SimpleSource" comp engine (extended w/ upward); LR4 crossovers; Accelerate-linked. No FFI, no UI script. |
| Binary | Mach-O universal bundle, **NOT stripped** (25908 syms / 13478 demangled exports), **no PACE / no LC_ENCRYPTION_INFO**. |
| Provenance | CLEAN = pedalboard black-box (all curves/times/crossovers). REF = static demangled symbols + setCoef disasm (topology hypotheses only, confirmed black-box). |
| Measured on | OTT (2023 build) · SR 48 kHz · pedalboard 0.9.17 · 2026-06-26 · `ott_sysid.py` |
| Source | `private-research/OTT_xfer/Tools/ott_sysid.py` · REF `private-research/_quarantine_disasm/OTT/` |

## Signal chain
```
x → in_gain → [ LR4 3-band split @ ~90 Hz, ~2.4 kHz ]
                 each band:  detector(env) → SimpleComp{ downward(thr,ratio) + upward(thr,ratio) } → band makeup
             → sum bands → out_gain → y
```
Per-band: ONE comp object does BOTH upward (lifts quiet) and downward (caps loud) toward a common band target level. No oversampling, no FIR — IIR, zero added latency.

## Per-stage formula (tag each CLEAN or REF)
- **Crossover** (CLEAN freq / REF topology): 3-band split. L|M ≈ **90 Hz**, M|H ≈ **2.4 kHz** (measured 90.5 / 2373 Hz). Slopes ≈ 24 dB/oct. REF: `FIL_Linkwitz_Riley4::SVFSet` + `TrapSVF` ⇒ **Linkwitz-Riley 4th-order** (TPT/ZDF SVF). `clean_xov` toggle barely alters response (IR support 0–61 vs 0–59 samp). **Latency = 0** (IIR, one-sided IR 0..241 samp).
- **Per-band dynamics — "smash to target"** (CLEAN): with depth=100, up=dn=100, each band collapses its output to a near-constant level regardless of input (∞:1 both ways):
  - **Upward** (out>in below knee): lifts low-level signal up to a plateau. Band M (1 kHz) upward plateau gain = **+9.1 dB**; the lift tapers to 0 as input approaches the threshold (knee ≈ −45 dBin at default). L plateau +12.3, H +13.4 dB (includes internal per-band makeup).
  - **Downward** (out<in above knee): caps high-level signal. Band M output pinned at ≈ −24.2 dBFS for all inputs above ≈ −33 dBin (∞:1). L pin ≈ −23.5, H ≈ −25.3 dBFS.
  - Net **both**: output sits in a narrow window (~3 dB) across a 70 dB input span — OTT's signature "everything at one loudness."
- **Depth law** (CLEAN): global 0..100 scales BOTH directions from none→full, ~linear in dB. Band M @ depth {0,10,25,50,75,100}: upward gain@−48 = {−0.2,+1.4,+3.7,+6.8,+9.2,+11.2} dB; downward GR@−3 = {−0.2,−1.7,−4.3,−9.3,−14.9,−21.2} dB. depth=0 ⇒ pass-through (split/sum only).
- **Strength** (CLEAN): `upwd_strgth`/`dnwd_strgth` 0..200 (100 default) scale each direction independently. **Downward saturates at strength ≥ 100** (GR −21.2 flat for 100/150/200) — 0→100 maps none→max. **Upward keeps climbing** past 100 (gain@−48 = +9.1/+10.2/+11.2/+12.3/+13.3 at strgth 0/50/100/150/200). strength=0 ⇒ that direction off (gain = makeup only).
- **Threshold** (CLEAN): per-band `thresh_l/m/h` 0..200 (100 default) slides the band target level. Higher thresh ⇒ MORE upward + LESS downward (raises the target); lower ⇒ less upward, more downward. Band M @ thresh {0,50,100,150,200}: up@−48 = {−0.4,+9.1,+11.2,+20.2,+29.2}, dn@−3 = {−30.8,−30.8,−21.2,−9.3,+2.6} dB.
- **Time (atk/rel)** (CLEAN): asymmetric. **Attack FIXED** ≈ 3 ms (63%) / 12 ms (90%) — independent of Time. **Time 0..1000 controls RELEASE**, ≈ **release_ms ≈ Time value** (Time 50→49 ms, 100→99 ms, 200→200 ms, 400→401 ms to 90% recovery). Release is non-exponential (fast initial drop + slow tail). REF: `chunkware_simple::AttRelEnvelope` (separate attack+release one-poles), `EnvelopeDetector::setCoef = exp(−1000/(ms·fs))`.
- **In/Out gain** (CLEAN): clean linear ±dB trims (−54..+19.1 dB), exact (Δ matches dB 1:1). **No output ceiling / brickwall** — full hot drive output not clamped.
- **Per-band makeup** `gain_l/m/h_db` (CLEAN): −54..+6 dB band trim (clamps at −54, label says −inf).

## Why / design rationale (music ↔ code)
- **Upward + downward per band** → squashes both loud peaks down and quiet detail up to a single target loudness → the aggressive, "in-your-face," ultra-dense sound OTT is famous for on drums/synths/master bus. Far more extreme than a normal multiband comp because it fills the bottom of the dynamic range, not just tames the top.
- **3 LR4 bands @ 90 Hz / 2.4 kHz** → phase-coherent split lets each band be smashed independently without comb filtering on recombine → tight low end, present mids, crisp highs without smearing.
- **Fixed fast attack + variable release** → snappy transient grab (the "pumping" character) with user-tunable recovery → Time becomes a groove/pump control, not an attack-shaping one.
- **Depth as global wet amount** → one knob from "off" to "destroyed" → producer-friendly single-control intensity; the classic move is to pull Depth back from 100 to taste.
- **Strength asymmetry (downward clamps at 100, upward keeps going)** → upward can over-lift the noise floor for extreme density while downward stays at a sane max → matches how people push the Upward knob hardest.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| in_gain_db / out_gain_db | dB | −54 … +19.1 | clean linear trim |
| depth | % | 0 … 100 (def 100) | global dynamics amount; 0 = bypass-ish (split/sum only) |
| time | % (≈ms) | 0 … 1000 (def 100) | **release** time; release_ms ≈ value; attack fixed ~3 ms |
| upwd_strgth | % | 0 … 200 (def 100) | upward amount; keeps boosting past 100 |
| dnwd_strgth | % | 0 … 200 (def 100) | downward amount; **saturates at ≥100** |
| thresh_l / m / h | % | 0 … 200 (def 100) | per-band target/knee position (↑ = more up / less down) |
| gain_l / m / h_db | dB | −54 … +6 | per-band makeup (clamps at −54) |
| byp_upwd_l/m/h | enum | '--' / 'BYPASS' | per-band **upward** bypass |
| byp_dnwd_l/m/h | enum | '--' only | **downward bypass LOCKED** (cannot disable) |
| program | int | 1 / 2 | preset voicing — **setter hard-blocks headless; do not set in harness** |
| clean_xov | bool | off/on | "clean crossover" mode (minimal measured effect) |

## CLEAN measurements (SR 48 kHz)
- Crossovers: 90.5 Hz (L/M), 2373 Hz (M/H). Latency 0 samp. IR one-sided (IIR).
- Static band M: upward plateau +9.1 dB (≤−45 in), downward pin −24.2 dBFS (≥−33 in), ∞:1 both.
- Depth/strength/threshold/time tables above. Attack ~3 ms fixed; release ≈ Time(ms).

## To implement (CLEAN-only path for ES-X GodBus)
- **LR4 3-band crossover** @ 90 Hz / 2.4 kHz (public Linkwitz-Riley, e.g. cascaded Butterworth or TPT SVF — building-blocks/biquad). Sum phase-coherent.
- **Per-band dual-sided gain computer**: downward comp (thr, high ratio) + upward comp (thr, high ratio) toward a band target; map Depth → overall amount, Strength(up/dn) → per-direction ratio/amount (dn clamps at 100), Threshold → target level.
- **Asymmetric envelope**: fixed fast attack (~3 ms), release = Time ms (one-pole + slow tail). Reproduce `release_ms ≈ Time` black-box; do NOT import the REF `exp(−1000/(ms·fs))` coef — re-derive from the measured release table.
- No oversampling / no output ceiling needed (zero latency). This is the explicit OTT reference for the GodBus bus.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reference only — reproduce black-box before shipping).
