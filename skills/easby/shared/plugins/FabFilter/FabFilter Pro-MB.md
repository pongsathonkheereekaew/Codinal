# FabFilter Pro-MB — FabFilter (multiband dynamics)

| | |
|---|---|
| Vendor / ver | FabFilter · Pro-MB |
| Type | Multiband dynamics — up to 6 freely-placed bands, each an independent up/down compressor + expander (dynamic, EQ-style) |
| Format | VST, VST3, CLAP, AU (macOS), AAX Native, AudioSuite (Pro Tools) |
| Source | manual: `FabFilter Pro-MB/FabFilter Pro-MB.pdf` · deep spec: `easby-programming/plugins/Pro-MB.md` (RE'd) |
| Provenance | **CLEAN** (vendor manual + usage) — no REF |

## What it does
Frequency-selective dynamics processor. Instead of carving the whole spectrum into fixed crossover bands, you place up to six bands only where you want them and leave the rest of the spectrum untouched — "think bands, not crossovers." Each band is a full dynamics engine: it can do downward/upward compression and downward/upward expansion (the four combinations come from pairing the Compress/Expand mode with a negative or positive Range), so one band can transparently tame a resonance, fatten a low end with upward compression, gate a hum, or pop a snare with upward expansion. Bands behave like dynamic EQ. The standout is the proprietary **Dynamic Phase** mode: zero latency, no pre-ringing, and phase is only altered when gain is actually changing — plus traditional **Linear Phase** and **Minimum Phase** options. Per-band side-chain (internal band/free-range or external), variable slopes (6–48 dB/oct), lookahead, and mid/side processing round it out.

## Controls (every param → musical effect)

### Per-band — basic controls (selected band[s], appear below the display)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Threshold | −90…0 dB | Level at which the band triggers; whether it acts above or below depends on Range sign + dynamics mode. Side-chain level meter rings the knob. | Set where dynamics kick in for that band |
| Range | −30…+30 dB | Max amount of gain change AND chooses direction: negative = downward, positive = upward (compression or expansion per mode). | Limit how much the band moves; flip up/down behavior |
| Dynamics Mode | Compress / Expand | Selects compression vs expansion. Combined with Range sign → 4 behaviors (see Notes). | Pick the dynamic action of the band |
| Attack | 0–100% | Speed gain change sets in (program- & frequency-dependent, shown as %). Fast = transient control / gating. | Fast for limiting/gating, slow to keep punch |
| Release | 0–100% | Speed of recovery from gain change (% , program-dependent). Higher = subtler leveling. | Longer for smooth leveling, shorter for pumping |
| Ratio | 1:1 … ∞:1 | Amount of compression/expansion applied, scaling the dynamic effect above/below threshold. | Gentle (low) to hard/gating (high) |
| Knee | Hard … Soft | How gradually the band reacts around threshold; soft smooths the effect. | Soft for transparency, hard for grab |
| Lookahead | 0–20 ms | Starts reacting up to 20 ms early to catch transients without ultra-fast attack. Global enable via bottom-bar Lookahead button. | Preserve transients; reduce distortion on fast settings |
| Output Level | gain (dB) | Final makeup level of the band (same value as the peak dot's gain in the display). | Compensate / boost the band's level |
| Output Pan | L↔R / Mid↔Side | Ring around Output Level: pans between mid & side levels (stereo width per band). Alt+drag Output Level adjusts pan too for proper makeup. | Widen highs, narrow lows, mid/side makeup |
| bypass (per band) | on/off | Bypasses selected band(s); band dims, button glows red. Hold = temporary. | A/B a single band |
| delete | — | Removes selected band(s) (Undo restores). | Clean up bands |
| band preset | menu | Save/load per-band settings; overwrite "Default" to change defaults for new bands. | Reuse band setups |
| Expert | on/off | Toggles the expert side-chain/stereo-link controls for all bands. | Reveal advanced triggering |

### Per-band — expert controls (Expert button on)
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Side Chain: Band / Free | toggle | Trigger source frequency range: the band's own input (Band, default) or a freely chosen range anywhere (Free) using intelligent adaptive filtering. | Trigger off a different frequency than you process |
| Side Chain: In / Ext | toggle | Internal signal vs external side-chain input. | De-ess/duck from an external source |
| Audition | on/off (hold = temp) | Monitors the filtered + stereo-linked trigger signal feeding detection. | Hear exactly what triggers the band |
| Stereo Link | 0–100% → Mid / Side | 0% = channels independent, 100% = identical gain both channels; dragging past 100% switches to Mid-only or Side-only processing (mode button toggles Mid/Side). Stereo version only. | Stabilize stereo; process only mid or only side |

### Per-band — display handles (on hover over a band)
| control | range / unit | what it does |
|---|---|---|
| Peak dot (gain/center) | drag V = gain, H = center freq | Moves the band; vertical = Output Level/gain, horizontal = center frequency (both crossovers in parallel). |
| Width | mouse-wheel / Ctrl(Cmd)+drag V | Sets band width (the two crossovers symmetrically). |
| Low / High crossover | drag each | Drag each crossover edge independently. |
| Low / High slope | 6–48 dB/oct each | Independent filter slope per crossover edge. |
| Range line | drag up/down | Adjusts the band's Range parameter directly. |
| Solo / Mute (S/M) | per band | Solo or mute the band (hold = temporary; Ctrl/Cmd-click = exclusive). |
| Split / Unsnap | buttons on snapped crossover | Split creates a new band between two snapped bands; Unsnap separates them. |

### Global / bottom bar & I/O
| control | range / unit | what it does | when to reach for it |
|---|---|---|---|
| Processing Mode | Linear / Dynamic / Minimum Phase | Algorithm for splitting/processing (see Notes). Dynamic Phase is default. | Linear=transparent master, Dynamic=zero-latency, Min=classic/CPU-light |
| Oversampling | Off / 2× / 4× | Internal upsampling to reduce aliasing on aggressive settings & improve HF response in Dynamic/Min Phase. Adds latency + CPU. | Aggressive comp/expand, low attack/high ratio |
| Lookahead (enable) | on/off | Globally enables/disables per-band lookahead. Off → zero latency in Dyn/Min Phase. | Turn off for zero-latency tracking |
| Analyzer (Pre/Post/SC) | on/off each | Real-time spectrum: pre-processing, post-processing, and side-chain overlays. | Visually judge effect & SC |
| Analyzer Resolution | Low/Med/High/Max (1024–8192 pt) | Spectrum FFT precision vs update speed. | More detail (slower) vs faster response |
| Analyzer Speed | Slow…Fast | Spectrum release/decay speed. | Catch fast events vs read steady spectrum |
| Analyzer Tilt | dB/octave (def 4.5) | Tilts displayed spectrum around 1 kHz for natural look. | Match perceived loudness curve |
| Analyzer Freeze | on/off | Holds the spectrum maximum over time. | Capture peaks |
| Input Level / Pan | gain + L/R | Pre-processing input trim & pan (alternative to moving all thresholds). | Drive into / out of thresholds |
| Output Level / Pan | gain + L/R | Final output trim & pan. | Match levels / compensate makeup |
| Global Bypass | on/off | Latency-compensated, click-free bypass of the whole plugin. | True A/B vs dry |
| Mix (dry/wet) | 0–200% | Blends dry & processed (scales all dynamic + static gain changes); >100% increases the processing instead of fading out. | Parallel multiband / push the effect |
| MIDI Learn | mode + menu | Map any MIDI controller to any parameter (Enable / Clear / Revert / Save). | Hardware control |
| Resize / Scaling | Medium/Large/XL · 100–300% | Interface size + DPI scaling (VST3 also free-drag resize). | Fit screen / precision |
| Full Screen | on/off | Fills the screen for precise editing (Esc to exit). | Surgical adjustments |
| A/B + Copy | states | Compare two full settings; Copy A→B. | Compare versions |
| Undo / Redo | history | Step through edits. | Recover work |

## Use by lens
- **Producer (create):** The creative side of multiband. Use **upward compression** (Compress mode + positive Range) to fatten a bass or add body without touching transients; extreme Range/Ratio/Release for **pumping** effects. Use **upward expansion** (Expand + positive Range) to pop a snare or enhance transients in a loop. Use **downward expansion/gating** (Expand + negative Range, high ratio) to tighten or gate a noisy band. Drag bands by ear; mute/solo to audition.
- **Mixing (balance):** Surgical, frequency-targeted dynamics — tame a boxy 300–500 Hz buildup, a harsh 2–5 kHz edge, or sibilance only when it spikes (dynamic-EQ behavior, transparent at rest). Use **Free** side-chain to trigger off a different frequency, **Ext** side-chain to duck a band from another source, and per-band **mid/side** to control width by frequency. Dynamic Phase keeps it zero-latency on tracks.
- **Mastering (finalize):** Choose **Linear Phase** for maximum transparency (accept latency/possible pre-ring) or **Minimum Phase** at 6 dB/oct (no static phase shift, CPU-light) for a classic master. Gentle low-ratio bands with wide soft knees for tonal balancing; **mid/side** processing to tighten the stereo low end or open up the sides; 2×/4× oversampling for cleanest results; Mix for parallel multiband.

## Notes / gotchas
- **Four dynamics behaviors** = mode × Range sign: Compress + negative Range = downward compression; Compress + positive Range = upward compression; Expand + negative Range = downward expansion (gating with high ratio/range); Expand + positive Range = upward expansion (transient enhancement).
- **Processing modes:** *Dynamic Phase* (default) — flat/linear phase when no gain applied, zero latency, no pre-ring, minor phase shift only when gain changes; closely approximates "normal" multiband but differs when muting all bands or placing bands adjacent. *Linear Phase* — flat phase, smooth crossover changes/no zipper, at cost of latency + possible pre-ringing. *Minimum Phase* — traditional filter split, no extra latency but static phase shift at crossovers (apparent on steep slopes); the 6 dB/oct case introduces no static phase shift, so it's very mastering-suitable.
- **Latency:** zero with Lookahead off + Dynamic/Minimum Phase (and no oversampling). Lookahead on = 20 ms; Linear Phase and oversampling add more.
- **Bands snap** to each other (share a crossover) and to display edges — snap all the way for a traditional full-spectrum split; Split/Unsnap buttons manage snapped pairs.
- **Stereo Link slider is stereo-only**; on the mono instance there's no link/MS control.
- **Up to 6 bands**, freely placed; 64-bit internal processing where needed; up to 4× oversampling.
- **MIDI routing differs by host** (Pro Tools MIDI track, Logic AU MIDI-controlled instrument, Live MIDI track, Cubase) — only the first plugin on a track usually receives MIDI.
- **External side-chain setup is host-specific** (manual covers Pro Tools, Studio One, Live, Logic, Cubase); requires Expert → Side Chain = Ext.
- Knob tricks: Ctrl/Cmd-click = reset; Shift+drag = fine-tune; double-click = type value (frequencies as "1k"/"A4"/"C#3+13", dB as "2x" for +6 dB, or percentages).

## Deep spec (Programmer only)
`easby-programming/plugins/Pro-MB.md` — measured/RE'd deep DSP spec (quarantined REF; never cited in CLEAN body or product).
