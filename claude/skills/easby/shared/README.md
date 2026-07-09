# easby/shared — the ONE music knowledge base (shared by ALL easby skills)

**→ Master entry: [INDEX.md](INDEX.md)** — the single music KB, all angles, that every agent loads.

**Architecture (2026-06-22):** there is **one shared music knowledge base, every angle**, and **all easby agents
share it in full** — Producer, Mixing, Mastering, and the Programmer side. The skills do **not** differ in *what
they know*; they differ only in **purpose / lens** (create / balance / finalize / engineer). Same knowledge,
tiny diff in purpose. **Only the Programmer side knows both music *and* code/DSP** — it's the superset.

The technique cores here (saturation, EQ/filtering, dynamics, troubleshooting) are the deduped "how it works";
deeper craft (theory, synthesis, drums, loudness, imaging…) is indexed from [INDEX.md](INDEX.md) wherever it
physically lives. A stage skill owns only the **decision** (when/how-much, in its purpose) — never a private
copy of the knowledge. The ONLY non-shared bit is each skill's **lens** file (`00-<stage>-mind`, `05-quick-decisions`).

## Provenance
All content here is **CLEAN** (public DSP literature + standard math + our own voicing). It is citable by
any easby skill, including for product (e.g. ES-L). It is **not** REF — disasm-derived facts stay quarantined in
`easby-programming` and never enter this layer.

## Topics (canonical technique cores)
| File | Covers | Stage application lives in |
|---|---|---|
| [saturation.md](saturation.md) | soft-clip / tanh / cubic / diode / tube, harmonic structure, OS/aliasing | Producer (timbre) · Mixing (track color) · Mastering (glue/loudness) |
| [eq-filtering.md](eq-filtering.md) | bell/shelf/HPF/LPF, Q, min- vs linear-phase, M/S | Producer (synth filter) · Mixing (surgical/tonal) · Mastering (broad/MS) |
| [dynamics.md](dynamics.md) | comp/limit/gate/expand: threshold/ratio/knee/attack/release, detectors, TP | Mixing (per-track/bus) · Mastering (glue/final limit) |
| [troubleshooting.md](troubleshooting.md) | symptom → cause → fix heuristics, routed to the owning stage | each stage diagnoses its own (router splits) |

## How stages use this
1. Stage skill reads the technique core here for the *how*.
2. Stage applies it with its **stage ranges + intent** (e.g. Mixing comp = per-track control; Mastering comp = ≤3 dB glue).
3. Verified runtime primitives (one-pole, RMS, biquad, true-peak, soft-clip) live in
   [`../easby-programming/building-blocks/`](../easby-programming/building-blocks/README.md) — shared/ is the
   *theory*, building-blocks/ is the *implementation*.

## Cross-family handoff (music ↔ easby-programming)
A music stage MAY cite a **researched plugin's CLEAN spec** as an emulation target (e.g. "glue like Pro-L2",
"comp like AC-1") — pull the CLEAN behavioural spec from `easby-programming/plugins/<NAME>.md`. Firewall holds:
only **CLEAN** rows cross; REF never enters a product BuildSpec. See INDEX "Cross-family handoff".
