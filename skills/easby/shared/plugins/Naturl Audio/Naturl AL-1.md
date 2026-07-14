# Naturl AL-1 — Naturl Audio (limiter)

| | |
|---|---|
| Vendor / ver | Naturl Audio · v0.1.0-alpha.8 (Quick Guide, Nov 2025) |
| Type | Mastering-grade peak limiter / loudness maximizer (zero look-ahead, non-brickwall) |
| Format | not stated in manual (typical VST3/AU/AAX) |
| Source | manual: `Naturl Audio/Naturl AL-1.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
The AL-1 is a mastering-grade true-peak/loudness limiter built on an unconventional **zero look-ahead** design — it abandons the look-ahead delay used by most modern limiters in favor of an original gain-reduction circuit that stays "minimally invasive," giving extremely low latency plus more weight and articulation. It is also **non-brickwall**: it deliberately avoids the clipping / wave-shaping stage that conventional limiters use to force a hard ceiling, so it preserves dynamics, detail and dimension and sounds more natural and open. The threshold is **fixed at 0 dBFS** — you push the signal into limiting with the Input knob rather than dragging a threshold down. Distinctive features: three controller **Modes** (discrete / continuous / blend), two gain-reduction **Envelope** shapes, **program-dependent stepped Attack/Release**, a **Window** control that trades audibility-of-limiting vs. distortion, a continuously-adapting **correlation-driven stereo-linking** section, and a built-in **Maximizer** (Makeup + Lift). Designed as a final master-bus limiter but equally usable on the mix bus, sub-groups, and individual tracks (produce/track/mix through it).

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Input Gain** | ±24 dB | Applies gain to the input signal. Since the threshold is fixed at 0 dBFS, this is the **drive control** — more input = more limiting / gain reduction. | Primary loudness control. Push 1–3 dB of gain reduction first, then fine-tune by ear. |
| **Output Gain** | ±24 dB | Applies gain to the output signal (final ceiling / make-down). | Set your true output ceiling (e.g. −0.1 / −1.0 dB) after limiting. |
| **Unity** | on/off | Compensates the output for unity loudness when adjusting Input, so louder ≠ unfairly "better" in A/B. | Leave **on** while dialing Input to judge limiting honestly, not just level. |
| **Mode** | I / II / III | Selects the gain-reduction controller algorithm. **I** = discrete controller, gain reduction in controlled steps → tighter transient handling (best for transient-dense / already-dense material). **II** = continuous controller, seamless GR → natural dynamics (best for highly dynamic content). **III** = blend of discrete + continuous → balance of transient + controlled. | I for dense/transient material; II for very dynamic mixes; III for "best of both" (recommended default for mix bus). |
| **Envelope** | I / II | Selects the shape of the gain-reduction envelope. **I** = raised-cosine function → transparent transitions. **II** = smoothstep function → more defined motion / "movement." | I when you want it invisible; II when you want audible, defined limiter motion. |
| **Attack** (stepped) | 0.5–34 ms, stepped | Sets attack time; **program-dependent** — the chosen value is the *maximum* attack time within the program-dependent window. | Faster = tighter peak catch (more limiting character); slower = lets transients through (more punch/openness). |
| **Release** (stepped) | 0.5–843 ms, stepped | Sets release time; **program-dependent** — the chosen value is the *maximum* release time within the program-dependent window. | Fast for loudness/density; slow for transparency and to avoid pumping. |
| **Window** | % (e.g. ~30%) | Adjusts the window size used by the selected Mode's controller algorithm. Higher times → **more audible limiting but less distortion** on hard-to-limit sounds (e.g. piano); lower times → more open sound. | Raise on percussive/tonal hard-to-limit material (piano, plucks) to trade audibility for cleanliness; lower for openness. |
| **External Sidechain (Ext. SC)** | on/off | Enables/disables external sidechain detection (limiter reacts to an external key signal). | Duck/limit one source from another's level; standard sidechain routing. |
| **Oversampling** | factor (e.g. 4x, 8x) | Selects the oversampling factor for the limiter/maximizer. | Higher (4x–8x) for cleaner true-peak control on final masters; lower to save CPU while tracking/mixing. |
| **Linking Toggle** | on/off | Enables/disables stereo linking. When **disabled the AL-1 runs fully dual-mono** (L/R limited independently). | On for glued, mono-safe masters; off (dual-mono) for width or per-channel control. |
| **Link Threshold** | dB (correlation threshold) | Sets the correlation threshold above which stereo linking engages. | Set how correlated the signal must be before the linker adapts. |
| **Max** (link) | % | Maximum amount of stereo linking allowed when signal correlation exceeds the link threshold. | Cap how "mono-locked" the limiter gets on highly correlated (centered) material. |
| **Min** (link) | % | Minimum amount of stereo linking allowed when correlation exceeds the link threshold. | Floor for linking — keeps some glue even on less-correlated passages. |
| **Speed** (link) | % | Speed at which linking adapts continuously between Min and Max. | Faster = linker tracks correlation changes quickly; slower = smoother, more stable imaging. |
| **Maximizer Toggle** | on/off | Enables/disables the internal maximizing stage (Makeup + Lift). | Turn on to squeeze extra loudness; off for limiting only. |
| **Makeup** | dB | Maximum makeup gain allowed **during the release phase** of the limiter. | Adds loudness/density in the limiter's recovery; raise for competitive level. |
| **Lift Threshold** | dB | Sets the threshold below which Lift engages. | Define the average-level point where quiet passages get boosted. |
| **Lift** | dB | Maximum gain allowed when the signal's average level falls **below** the Lift threshold. | Brings up low-level/quiet sections for density without crushing peaks. |
| **A / B + Copy** | toggle / button | A/B compare two parameter states; Copy duplicates current state to the other slot. | Compare two limiter settings; Copy A→B then tweak. |
| **Bypass** | on/off | Bypasses processing. | Honest before/after (mind the loudness difference; use with Unity). |
| **Combo Output Meter Calibration** | dBFS (e.g. −6 … −18) | Sets the reference level for **0 VU** on the output meter. | Calibrate VU/Crest readout to your monitoring/standard. |

### Meters (read-only)
| meter | shows |
|---|---|
| **Loudness Meter** | Integrated / Short-Term / Momentary LUFS per EBU R128 / ITU-R BS.1770-4. |
| **Link Meter** | Stereo-linking activity. |
| **Combo Gain Meter** | Gain reduction + maximizer gain. |
| **Combo Output Meter** | Peak + VU of the final output. |
| **Crest Meter** | Crest factor (peak minus VU) — how much dynamic range remains. |

## Use by lens
- **Producer (create):** Track or produce *through* it as a tone/glue stage. Use Mode III + Envelope II for defined motion, a slow-ish Attack and moderate Release, and just 1–2 dB of gain reduction to add density and "finished" weight to stems while keeping transients. Low oversampling (saves CPU) is fine here. Use it creatively as a non-brickwall colour, not just protection.
- **Mixing (balance):** On the **mix bus**, follow the manual's recipe — Mode III, Envelope II, Attack ~21–34 ms, Release ~0.5–3 ms, Window ~30%, Linking on (defaults), Maximizer on (defaults), Oversampling 4x; drive Input for ~1–3 dB GR and adjust by ear. On sub-groups, use lighter GR and lean on the correlation linker (Min/Max/Speed) to keep the stereo image intact while controlling peaks. Keep **Unity** on so you balance by tone, not level.
- **Mastering (finalize):** Final limiter — set Output for your ceiling (e.g. −0.1 / −1.0 dB), drive Input to taste while watching the LUFS readouts (Integrated/Short-Term/Momentary). Prefer higher oversampling (4x–8x) for true-peak safety. Choose Mode I for dense masters, II for dynamic ones, III for balance. Use Window higher on hard-to-limit tonal material to reduce distortion, and Makeup/Lift to push competitive loudness without brickwall artifacts. Watch the **Crest** meter to confirm you're preserving dynamics.

## Notes / gotchas
- **Threshold is fixed at 0 dBFS** — you limit by raising **Input**, not by lowering a threshold. Use **Unity** + **Bypass** for fair A/B.
- **Zero look-ahead → very low latency** (a feature, not a limitation), but it means no pre-emptive transient handling like look-ahead limiters; Attack/Window do that job instead.
- **Non-brickwall**: there is no clipper/wave-shaper forcing an absolute ceiling, so set **Output** conservatively and use **oversampling** for genuine true-peak control on masters.
- **Attack/Release are stepped and program-dependent** — the dialed value is the *maximum* time within an adaptive window, not a fixed constant.
- **Window** is the key character control: higher = less distortion but more audible limiting; lower = more open.
- **Stereo linking is correlation-driven and continuous** (Threshold/Min/Max/Speed); turning the Link toggle **off makes it dual-mono**.
- **Maximizer** is a separate engageable stage: **Makeup** acts during the release phase, **Lift** boosts when average level drops below the Lift threshold.
- **Loudness metering** is EBU R128 / ITU-R BS.1770-4 compliant (Integrated/Short-Term/Momentary); output meter has selectable **0 VU calibration** for the VU/Crest displays.
- Manual is an early **alpha (v0.1.0-alpha.8)** Quick Guide — ranges/labels are "subject to change."

## Deep spec (Programmer only)
not reverse-engineered — capability only.
