# DAWstream — LovestudyMix (audio-over-WebSocket streaming utility — not a DSP processor)

| | |
|---|---|
| Vendor / ver | LovestudyMix (`com.LovestudyMix.vst3.DAWstream`) · 1.0.0 |
| Type | **Network audio streamer**: captures the bus and ships it over a WebSocket (`/ws/stream`, `application/octet-stream`). Utility/transport, **no audio effect**. |
| Tech | **iPlug2** framework (built `/Users/tar/Desktop/iPlug2/…`) + **IXWebSocket** + Skia UI. NOT JUCE. 54.7k syms, NOT stripped, no PACE. **No audio frameworks linked** (Cocoa/Carbon only) — the giveaway it isn't a processor. |
| Binary | universal (x86_64+arm64) |
| Provenance | **CLEAN** (pedalboard + strings/Info.plist identity). No disasm. |
| Measured on | DAWstream 1.0.0 · 48 kHz · pedalboard 0.9.17 · 2026-06-26 |
| Source | `private-research/CleanMisc/Tools/cleanmisc_sysid.py` |

## Behavior
- **Audio = unity pass-through** (CLEAN): 1 kHz @ −13.5 dB in → out −13.5 dB, Δ 0.00 dB. Audio is monitored/forwarded, not processed.
- Sends the signal over a WebSocket to a remote endpoint (`/ws/stream`), likely a browser/web monitoring page (Skia-rendered UI). `FX 1..5 Depth` strings exist but are iPlug2 example boilerplate, not active DSP.
- `monitor_level` 0–100 % = local monitor gain only.

## Why / design rationale
- Streaming/collab utility: put it on the master, it broadcasts the DAW output to a web client (remote listening / review). The plugin slot is just a tap point; the value is the network transport, not any sound design.

## Parameters
| param | unit | range | notes |
|---|---|---|---|
| monitor_level | % | 0..100 | local monitor gain |
| bypass | bool | | |

## Open questions
- WebSocket endpoint/protocol is the actual product surface (out of audio-DSP scope). Nothing to clone for ES-L.

## To implement
N/A — utility, not a DSP target. Noted for catalog completeness. CLEAN.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing.
