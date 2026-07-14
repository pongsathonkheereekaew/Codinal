# McDSP CompressorBank — McDSP (compressor)

| | |
|---|---|
| Vendor / ver | McDSP · v7 (manual © 2022) |
| Type | Compressor / dynamics (with pre-filter + post-compression static/dynamic EQ) |
| Format | AAX Native + AAX DSP, AU, VST3 (Intel + Apple silicon); VENUE S6L (HD only). VST dropped as of v7. |
| Source | manual: `McDSP CompressorBank/McDSP CompressorBank.pdf` · deep spec: not RE'd |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
A high-end, model-flexible compressor that recreates the response of many classic and modern hardware units (UREI 1176 blackface, Teletronix LA2A, Neve 2254E/33609, dbx 165, Avalon AD2044, Empirical Labs Distressor, Altec 9473A) and goes beyond them. Beyond standard Threshold/Ratio/Attack/Release, the actual **shape** of the compression curve is sculpted by two unique controls: **Knee** (one continuous control morphs from a dbx-style "over easy" undershoot, through hard knee, to a Neve-style overshoot "tail") and **BITE** (Bi-directional Intelligent Transient Enhancement — lets fast transients pass while keeping overall compression amount the same). Ships as three interchangeable configurations: **CB101** (compressor + TC circuit only), **CB202** (adds side-chain/in-line pre-filter), **CB303** (adds post-compression static/dynamic parametric EQ). Built on the same filter/EQ tech as McDSP FilterBank. Double-precision, zero latency (AAX Native/AU/VST3; AAX DSP = 16-sample delay).

## Controls (every param → musical effect)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| **Output** (make-up) | 0 to +48 dB | Gain applied after the compressor algorithm. | Restore level lost to gain reduction; lifts low-level detail (room ambience). |
| **Key** (Ø / external) | Engaged / Disengaged | Selects side-chain (external key) vs internal key as the compression trigger. | Ducking (e.g. dialog ducks music/bg), keying off a separate source. |
| **Listen** | on/off button | Monitors the selected key input (no compression while held). In CB202/CB303 this is the **post-pre-filter** signal. | Hear/tune exactly what the detector is tracking. |
| **Ø (polarity)** | normal / invert | Output-stage phase/polarity flip. Independent per L/R channel (a v7 selling point). | Fix phase issues; the manual flags polarity as an output-stage feature. |
| **Threshold** | −48 to 0 dB | Level above which compression engages. Shown by the orange triangle on the output meter. | Set how much of the signal gets compressed. |
| **Compression (Ratio)** | 10:1 to 1:1 | Input-to-output ratio above threshold. | 2:1–4:1 gentle; 8:1+ strong/limiting. |
| **Knee** | −10.0 to +15.0 | Shapes the curve around threshold. **−10→0 = undershoot** ("over easy" dbx soft transition); **0 = hard knee**; **0→+10 = overshoot** (Neve 33609 pumping/breathe); **+10→+15 = overshoot "tail"** (LA2A-style — gain reduction *decreases* as signal drives hard). One continuous control changes compressor paradigm. | The plugin's signature move — dial vintage character or invent new curves; +10→+15 for opto "tail", −10→0 for smooth dbx feel. |
| **BITE** | 1.0 to 50.0 | Bi-directional Intelligent Transient Enhancement: lets fast transients (HF/percussive) pass less-compressed while overall compression amount stays the same. | Add snap/attack to over-compressed drums or vocals without backing off the ratio; emulate dbx attack behavior (set BITE 10–50 instead of touching Attack). |
| **Attack** | 0.25 to 25.0 ms | Rate the compressor responds as signal rises above threshold. (Fastest 0.03 ms / one-sample setting cited for brick-wall in the modeling text.) | Fast = catch transients/limiting; slow = let attacks through. Disabled in Auto. |
| **Release** | 25.0 to 2500.0 ms | Rate the compressor stops responding as signal falls below threshold. | Fast for pumping/density; slow for transparency. Too fast = "gain cogging." Disabled in Auto. |
| **TC Circuit Type** | Type-1 / Type-2 / Auto | Detection algorithm. **Type-1** = pure peak detection (release unaffected by sub-release-level signals). **Type-2** = adaptive release (release affected by any new signal). **Auto** = automatic attack+release (disables Attack/Release). | Type-1 for predictable/aggressive; Type-2 for natural program/vocal response; Auto for set-and-forget. |
| **IN** (per-band enable) | On/Off | Compressor enable/disable; red LED when enabled. | Bypass the dynamics stage for A/B. |
| **Pre-Filter In/Out** (CB202/303) | −60 to 0 dB | Engages/bypasses the pre-filter; also acts as its level. | Turn on side-chain filtering. |
| **Pre-Filter InLine** (CB202/303) | toggle | Places the *filtered* signal into the direct audio path (heard at output), not just the key. | Use the pre-filter as an actual EQ on the program, not just detector shaping. |
| **Filter Type** (CB202/303) | High / Low / Band pass / Parametric | Pre-filter shape feeding the detector (or in-line). | HP to stop bass over-triggering; LP to stop HF buzz tracking; Parametric for surgical key shaping. |
| **Pre-Filter Frequency** | 20 Hz – 20 kHz | Cutoff/center of the pre-filter. (−3 dB pt for HP/LP, 0 dB for BP.) | e.g. ~100 Hz HP for plosives; 200–800 Hz LP for bass buzz. |
| **Pre-Filter Q** | 0.1 to 5.0 | Bandwidth (parametric) or HP/LP shape. **Q=1.4 = critical** (no over/undershoot); 0.1–1.4 overshoot (resonant); 1.4–5.0 undershoot (damped). | Resonant Q for super-bass/emphasis; ~0.7 for smooth bass de-buzz. |
| **Pre-Filter Gain** | −12 to +12 dB | Boost/cut, parametric type only (range exceeds FilterBank). | Shape detector emphasis or in-line tone. |
| **EQ Mode** (CB303) | Off / Static / Dynamic | Post-compression parametric EQ. **Static** = fixed gain; **Dynamic** = gain tracks the compressor's gain-reduction amount (uses the same Attack/Release as the comp). | De-essing, signal enhancement, harmonic distortion, dynamic tone that moves with the comp. |
| **EQ Gain** (CB303) | −12 to +12 dB | Boost/cut of the post-comp band. | Tone-shape after compression. |
| **EQ Freq** (CB303) | 20 Hz – 20 kHz | Center frequency of the post-comp band. | Target the band to enhance/duck. |
| **EQ Q** (CB303) | 0.1 to 5.0 | Bandwidth, constant-Q (Q=1 ≈ one octave). At Q=0.1 (~10-oct) it approaches a smooth low/high *shelf*. | Wide=shelf-like tone; narrow=surgical (de-ess). |
| **Meters** | −60 to 0 dB | Input, Gain Reduction, Output meters with clip peak LEDs (click LED to clear). | Set threshold by watching GR; watch input/output clip LEDs. |

## Use by lens
- **Producer (create):** Reach for character. Knee +10→+15 = LA2A opto "tail" (glue, decreasing GR when pushed); Knee 0→+10 = Neve 33609 pump/breathe; Knee −10→0 = dbx "over easy" smoothness; Knee 0 + 0.03 ms attack = brick-wall limiter. BITE 3–6 to keep transients alive on a wild keyboard/piano take. CB303 Dynamic EQ for moving harmonic excitement that only appears when the compressor is working. Use presets named after the gear (`British Comp/Limiter`, `Old Smoothie` = dbx 165, `Class A Opto`, `LA too eh?`, `blackface` = 1176) as starting points.
- **Mixing (balance):** Vocals/dialog — ratio 2:1–3:1, Type-2, attack 2–4 ms, release 200–400 ms, Knee/BITE default, threshold for 6–9 dB GR in the orange meter zone. Plosives: CB202/303 pre-filter HP in-line ~100 Hz, default Q. Drums — 6:1–8:1, attack 0.2 ms, release 100 ms, Type-2, 15–18 dB GR for the smashed sound; raise BITE 4.0→8.0 for "thwack." Bass de-buzz — pre-filter LP, Q 0.7, 200–800 Hz so the detector stops tracking HF (kills digital fast-attack buzz). Keys/synths — gentle 2:1, attack 1–5 ms, release 200–500 ms, Knee −10 soft, only 3–6 dB GR at loudest parts.
- **Mastering (finalize):** Use the modeled curves for transparent bus glue — AD2044 (medium knee, moderate attack/release, low ratio) is the "nearly transparent" choice; LA2A "tail" for gentle program-dependent leveling. On a 2-buss, the LP pre-filter trick (Q 0.7, 2–8 kHz) smooths the whole compressor response. CB303 Static EQ for tonal finishing post-compression. Per-channel polarity available if needed. Mind sample-rate DSP cost on HDX (see gotchas).

## Notes / gotchas
- **Three configs, interchangeable presets:** CB101 (comp + TC), CB202 (+pre-filter), CB303 (+static/dynamic EQ). A preset made in a higher config loads in a lower one but the extra controls simply aren't present/active.
- **No control linking** (explicitly stated). All controls fully automatable. `<Option>` = defaults, `<Command>`+drag = fine, type into text box for exact values.
- **Auto TC** disables Attack and Release. **Type-1 vs Type-2** is the core "vintage feel" detector switch (peak vs adaptive release).
- **BITE replaces Attack tweaks** when emulating dbx-style behavior — set Attack 10–50 ms and shape transients with BITE instead.
- **Dynamic EQ (CB303)** reuses the compressor's own attack/release, so its movement is locked to the comp envelope.
- **Pre-filter "InLine" vs key-only:** by default the pre-filter shapes only the detector; InLine puts the filtered signal into the audible path.
- **Latency:** AAX Native / AU / VST3 = zero (double precision). AAX DSP (HDX) = 16-sample internal delay.
- **HDX DSP scaling:** counts per DSP at 48 kHz — CB101 mono 27 / stereo 23; CB202 23 / 20; CB303 21 / 15. DSP usage ×2 at 96 kHz, ×4 at 192 kHz (some larger configs unavailable at high rates).
- **Auth:** iLok (iLok2/iLok3 USB or iLok Cloud). v7 = two activations per license.

## Deep spec (Programmer only)
not reverse-engineered — capability only.
