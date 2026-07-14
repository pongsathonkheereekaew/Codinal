# Easby — Cross-Skill Router

Easby is five sibling skills over **one shared music knowledge base** ([shared/INDEX.md](shared/INDEX.md) —
all angles, loaded by **every** agent). They do NOT differ in *what they know*; they differ only by **purpose
lens** (create / balance / finalize / engineer). Same music knowledge, tiny diff in purpose.
**The Programmer side (`easby-decomp` + `easby-programming`) is the superset — it knows music *and* code/DSP**
(the only side with both). "Owns/Refuses" below = which **decision/output** each emits (its lens), NOT access to
knowledge — all five share the full music KB.

| Skill | Owns | Refuses | Path |
|---|---|---|---|
| **Producer** | sound-design, variation amt 1–5, music theory, melodic/harmonic/rhythmic development, synthesis recipes, arrangement principles | mix-bus / track-level mixing, LUFS / mastering, recording-session engineering | `~/.claude/skills/easby/easby-producer/SKILL.md` |
| **Mixing** | balance, EQ, panning, dimension (reverb/delay), dynamics, sidechain, automation, bus routing, genre-specific mix decisions | LUFS / streaming targets / final limiting, sound design from scratch, BPM/key detection | `~/.claude/skills/easby/easby-mixing/SKILL.md` |
| **Mastering** | LUFS targeting, broad tonal shaping, glue compression, limiting, true-peak compliance, dither, M/S, format prep (streaming/vinyl/Atmos/ADM) | individual track or bus processing, sound design, BPM/key detection | `~/.claude/skills/easby/easby-mastering/SKILL.md` |
| **Programmer** (`easby-decomp`) | RE/decompile plugin binaries: black-box system-ID, r2/Ghidra static, direct-FFI harness, REAPER host-route; clean-room firewall. **Also knows the full music KB** (superset) | shipping disasm-derived (REF) into product. (Knows music — but emits no music decision; defers to /produce·/mix·/master) | `~/.claude/skills/easby/easby-decomp/SKILL.md` |
| **Programming** (`easby-programming`) | knowledge base of researched plugin DSP — algorithms, formulas, params, signal chains, FFI contracts for implementation/cloning | handing TAINTED (disasm) facts to product code; doing the RE itself (→ Programmer) | `~/.claude/skills/easby/easby-programming/SKILL.md` |

## Routing by user request
Triggers are **stage-qualified**: the same DSP word (EQ, compression, limiter, M/S) means a different
operation per stage, so route by **stage**, not the bare word.

| Trigger / phrase | Route to |
|---|---|
| "vary this loop", "amt", "secondary dominant", "what waveform", "sound design", "synthesis recipe", "make it better not different", "3 Ps", "music troubleshooting" | **Producer** (easby-producer) |
| "mix", "balance", "panning", **"track/bus EQ"**, **"per-track / per-instrument compression"**, "sidechain", "vocal sitting", "stereo width / imaging", "reverb / delay send", "bus routing", "automation" | **Mixing** (easby-mixing) |
| "master", "LUFS / loudness target", **"true-peak / final limiter"**, **"stereo-bus glue"**, "dither", "K-system", **"M/S on the master"**, "format prep (streaming / vinyl / Atmos / ADM)", "stem master" | **Mastering** (easby-mastering) |
| "decomp", "decompile", "reverse engineer", "system-id", "black-box", "ghidra", "radare2", "ffi harness", "measure this plugin", "how does \<plugin\> work" | **Programmer** (easby-decomp) |
| "implement", "port the algorithm", "clone the behaviour", "gain computer", "\<plugin\> dsp/formula", "dsp reference", "exact / clean mode", "code under the hood" | **Programming** (easby-programming) |
| bare **"EQ this" / "compress this" / "limit this" / "M/S"** with no stage stated | **Disambiguate first** ↓ |

### Disambiguating a bare process word (EQ / compress / limit / M-S)
These live in BOTH Mixing and Mastering — split by **stage**:
- target is a **single track / instrument / bus** inside a multitrack session → **Mixing**
- target is the **finished stereo mix** for loudness/distribution → **Mastering**

If the request doesn't say which, **ask one question** — "per-track/bus (Mixing), or the stereo master (Mastering)?" — then route. Don't guess silently.

When in doubt (stage ladder):
- **sound's identity** (what is it / how to make / how to vary) → Producer
- **track relationships** (how these fit together) → Mixing
- **finished stereo file** for distribution → Mastering
- **a plugin binary** (how it works / measure / RE) → Programmer · **its recovered DSP** (implement/clone) → Programming

## Name map (dir ↔ skill ↔ command ↔ agent)
| Dir | Skill `name:` | Command | Agent |
|---|---|---|---|
| `easby-producer/` | `easby-producer` | `/produce` | — |
| `easby-mixing/` | `easby-mixing` | `/mix` | — |
| `easby-mastering/` | `easby-mastering` | `/master` | — |
| `easby-decomp/` | `easby-decomp` | `/decomp` | `easby-programmer` |
| `easby-programming/` | `easby-programming` | `/easby-programming` | — |

Bare **"easby"** (no stage/verb) → read THIS router, then route.

## Shared music knowledge (full — every agent loads it)
**One music KB, all angles → [`shared/INDEX.md`](shared/INDEX.md).** Every easby agent (all 5) loads the *full*
KB — synthesis, theory, arrangement, EQ, dynamics, saturation, imaging, sidechain, loudness, recording,
troubleshooting. They do **not** know different things. A skill owns only the **decision** (its purpose lens);
the deduped technique cores live in `shared/*.md`, deeper craft is indexed from `shared/INDEX.md` wherever it
physically sits. The **only** per-skill content is the lens: `00-<stage>-mind.md` + `05-quick-decisions.md`
(how that purpose weighs the same knowledge). Runtime primitives → `easby-programming/building-blocks/`.

**Cross-family handoff (music ↔ programming):** a Mixing/Mastering decision MAY cite a researched plugin's
**CLEAN** spec from `easby-programming/plugins/<NAME>.md` as an emulation target ("glue like Pro-L2", "comp
like AC-1"). **Only CLEAN crosses; REF never enters a product BuildSpec** (firewall holds across families).

## Handoff Contracts (skill ↔ skill)

### Producer → Mixing

When Producer ships a `VariationDecision` / `SoundDesignTarget` / `ArrangementDecision`, the rendered audio is then a *mixable element*. Producer never specifies fader, pan, or reverb send — those are Mixing's domain.

- Producer emits per-element timbre target (e.g. "Rhodes patch with VCF half open").
- Mixing receives the rendered stems and decides `MixDecision` per element.
- **No fader_db, no pan, no reverb send from Producer.**

### Mixing → Mastering

Mixing's `MixBusDecision` defines the handoff state:

| Field | Target |
|---|---|
| `target_peak_lufs` | -18 to -16 LUFS integrated |
| `limiter_ceiling_dbfs` | mix-bus *safety* limiter only (≤ -3 dBFS) |
| `saturation` | usually false — saturation belongs to Mastering |
| `compression_gr_db` | ≤ 3 dB on the bus (final glue → Mastering) |

If a mix arrives outside this contract (e.g. peaking at -1 dBFS, integrated at -8 LUFS), Mastering refuses with `{"type":"Refusal","reason":"hypercompressed_mix","redirect":"Mixing"}`.

### Mastering → Distribution

Mastering's `MasterDecision` ships per-platform:

| Platform | LUFS | True Peak | Format |
|---|---|---|---|
| Spotify | -14 | -1.0 dBTP | 16/44.1 |
| Apple Music | -16 | -1.0 dBTP | 24/48 (ADM optional) |
| YouTube | -14 | -1.0 dBTP | 16/44.1 |
| Broadcast (EBU R128) | -23 | -1.0 dBTP | 24/48 |
| Vinyl | -12 to -9 | groove limit | lacquer cut spec |
| Club / DJ | -9 to -6 | -0.3 dBTP | 16/44.1 |

## Refusal redirect chain

Each skill's refusal redirects to the correct sibling, never a generic error. The redirect target is encoded in the JSON:

```json
{"type":"Refusal","reason":"<scope_label>","redirect":"<Producer|Mixing|Mastering>"}
```

Operator can re-issue the request against the named sibling.

## Shared infrastructure

| Resource | Used by | Path |
|---|---|---|
| Pro Tools DAW reference | All 3 | `Producer/docs/easby/09-pro-tools-daw-reference.md` (canonical) |
| Owsinski Producer's Handbook distill | Producer | `Producer/docs/easby/11-owsinski-producer-handbook.md` |
| Owsinski Mixing Handbook | Mixing | `Mixing/docs/mixing/*` |
| Katz + Owsinski Mastering | Mastering | `Mastering/docs/mastering/*` |
| Pitch / key / BPM detection | All 3 defer to our | `Source/Audio/SoundClassifier.h`, `Source/Audio/AnalysisCoordinator.h`, `Source/Audio/AubioUtils.h` |

## Per-skill INDEX.md

- Producer: `Producer/docs/easby/INDEX.md` (deepest — 6 routers + sub-files + 4 schemas)
- Mixing: `Mixing/docs/mixing/INDEX.md` (flat — 11 small files + 2 schemas)
- Mastering: `Mastering/docs/mastering/INDEX.md` (flat — 15 small files + 2 schemas)

## Schemas (cross-skill summary)

| Skill | Schemas |
|---|---|
| Producer | `VariationDecision`, `SoundDesignTarget`, `ArrangementDecision`, `TroubleshootDiagnostic` |
| Mixing | `MixDecision`, `MixBusDecision` |
| Mastering | `MasterDecision`, `StemMasterDecision` |
| Programmer | `PluginSpec` (RE output, CLEAN+REF tagged) |
| Programming | `PluginSpec` (internal, full), `BuildSpec` (product-facing, **CLEAN-only**), `Refusal` |

### Engineering firewall handoff (Programmer → Programming → Product)
- **Programmer** (`easby-decomp`) RE's a binary → emits `PluginSpec` (every fact tagged CLEAN or REF).
- **Programming** (`easby-programming`) is the **sole holder of REF** (source/disasm reference). For a product
  it emits a `BuildSpec` filtered to **CLEAN only** (black-box measurement + public DSP literature + own voicing).
- **Product** (ES-L DSP engine) consumes `BuildSpec` only; rejects any without `provenance_gate:"CLEAN_ONLY"`.
- REF crossing into a BuildSpec / product = firewall breach → `Refusal`.

Each in `<Skill>/schemas/*.schema.json` (Draft 2020-12).

## ADRs

- `Producer/docs/adr/0015-easby-producer-agent-contract.md`
- Mixing + Mastering ADRs: see respective `docs/adr/`
