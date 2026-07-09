---
name: easby-decomp
description: Reverse-engineering / decompile PROCESS for audio plugins (VST3/AU/AAX). Black-box system-ID + static disasm + direct-FFI harnessing to recover DSP algorithms, with a strict clean-room provenance firewall. Emits distilled specs into easby-programming. Trigger when reverse-engineering, decompiling, system-ID'ing, or measuring any plugin binary.
triggers:
  - "decomp"
  - "decompile"
  - "reverse engineer"
  - "reverse-engineer"
  - "RE this plugin"
  - "system id"
  - "system-id"
  - "black-box"
  - "measure this plugin"
  - "ghidra"
  - "radare2"
  - "ffi harness"
  - "decode the algorithm"
  - "how does this plugin work"
  - "easby decomp"
---

# easby-decomp — plugin reverse-engineering process

Sibling of [easby-programming](../easby-programming/SKILL.md) (the data store this feeds).
Owns: **how** to take any plugin binary apart and recover its DSP. Refuses: shipping anything
disasm-derived into product code (see firewall). Emits: a distilled per-plugin spec → easby-programming.

**Superset — you know both.** The Programmer side is the ONLY easby agent that knows **code/DSP *and* the full
music KB**. Load the music knowledge like any other agent: `~/.claude/skills/easby/shared/INDEX.md` (all angles).
Use it to interpret what a plugin does *musically* (why this curve, what a producer/mixer/master wants) — then
recover + clone the DSP. Music KB is CLEAN; your REF stays quarantined here, never crossing into product.

## Goal / target
Per plugin: recover its DSP **behavior** as a **CLEAN, clone-ready spec** — gain law, curves, times, params
with real units, signal chain — enough that ES-L can be rebuilt from CLEAN measurement + public literature.
Capture REF (exact code) maximally for *understanding*; the product firewall is absolute (REF never ships).
**"Done" = the spec lets you clone the behavior and every shippable fact is CLEAN.** A documented hard wall
(e.g. PACE-encrypted code) is an acceptable terminal state for the REF side — the CLEAN behavioral spec, not
the source, is the real deliverable. Decode order, cheapest-first: triage → black-box (CLEAN) → static (REF).
Solution ladder when the easy host fails: pedalboard (fast, main-bus) → **REAPER ReaScript** (DRM, sidechain,
exact PDC, param sweeps) → static disasm (navigation/REF only).

## ⛔ Clean-room firewall (READ FIRST — non-negotiable)
Per `private-research/_quarantine_disasm/NOTICE.md`, two provenance classes — never mix:

| Class | Source | Use |
|---|---|---|
| **CLEAN** | black-box MEASUREMENT (signals in → measure out), public DSP literature (AES/textbooks), own voicing | **may** feed shippable product (e.g. ES-L) |
| **TAINTED** | static disassembly / decompilation (r2, Ghidra, asm, RTTI, kernel addresses) | reference / education ONLY. **NEVER** cite from product source. Quarantine it. |

Rules:
- Disasm tells you *what to measure* and *why a curve looks odd* — then **confirm it black-box** and cite only the measurement.
- A formula recovered from Ghidra is TAINTED until independently reproduced by black-box measurement; once measured, cite the measurement.
- Keep tainted artifacts (`*.asm`, `decompiled.c`, `dsp.c`, RTTI dumps) under a `_quarantine_disasm/` or `decomp/` folder, tagged. Product code (e.g. `ES-L/Source`) must never reference them.
- When emitting to easby-programming, tag every fact `CLEAN` or `REF` (tainted/reference-only).

## Coverage policy — REF-maximal, CLEAN-gated
Recover as much exact code/DSP as the binary allows — full disasm/decompile of kernels, coefficient
tables, and class graphs — for **every** researched plugin, and store it all as **REF** under
`_quarantine_disasm/<NAME>/`. Exhaustive REF extraction widens *understanding*, never what may ship:
the firewall is unchanged — REF is reference/education only and **never** enters product (e.g. ES-L) or a
BuildSpec. Standard pass for stripped+RTTI FabFilter builds = RTTI class graph + Ghidra decompile-by-
address of the DSP kernels (see Pro-L2 — gain kernel ln→dB + atan styles fully recovered). PACE-iLok
stripped (MELD, ML4000/ML8000) = static wall → black-box only. Done so far (REF): AC-1, AS-1, AE-1×3,
FLVTTER (Ghidra/r2); **all 11 FabFilter** (Pro-L2/C3/DS/G/MB/Q4/R2/Saturn2/Timeless3/Twin3/Volcano3) = Ghidra REF complete.

**Cross-plugin finding (FabFilter):** one **shared DSP core library** is reused across the whole suite —
the same kernels appear byte-identical in multiple plugins. (1) **ln→dB / dB→lin + atan** transcendentals
(Cephes-class minimax: `1/√2`, `ln2` hi/lo, `20/ln10`, `2/π·atan(x·π/2)`) — identical in Pro-L2/C3/Saturn2/
Timeless3/Twin3. (2) **14-entry waveshaper `switch`** (+ `KNEEMIX`/`OUTGAIN` const tables) — byte-identical
Pro-G ↔ Saturn2. (3) **analog-prototype filter designer** (Butterworth/Cheby/elliptic → bilinear, magnitude-
matched Orfanidis-class) + shared prototype constants — Pro-Q4/Volcano3/Pro-DS/Pro-R2. (4) **TPT/ZDF SVF**
(Zavalishin) — Twin3/Volcano3/Timeless3. (5) shared **DynamicsEngine** RTTI graph — Pro-L2/C3/G/MB.
Recurring wall: realtime block kernels are schedule-dispatched (function-pointer graph) → not in `afl`,
found by NEON/scalar FP density; param→time (attack/release) maps live in prepare-time `Detector`/`Capacitor`
state, not the math kernels → those stay CLEAN-measurement. All REF, quarantined; re-derive black-box to ship.

## Triage first — pick the cheapest track that works
```
file <bin>; lipo -info; otool -L            # arch, frameworks (Accelerate/vDSP, WebKit UI…)
nm -U <thinned> | wc -l                      # 0-ish = stripped (black-box only); 1000s = symbols! 
nm <bin> | c++filt | grep -iE 'process|dynamics|_ffi|extern'   # C++/Rust? FFI boundary?
```
- **Stripped / DRM (PACE-iLok, e.g. MELD)** → black-box only. Static is a wall.
- **Not stripped + clean C FFI (e.g. AC-1 = JUCE→Rust)** → jackpot: black-box + direct-FFI + Ghidra all open.
- **AAX-only** → pedalboard/REAPER can't load AAX (Pro Tools only); get the **VST3/AU of the same product**.
  **PACE wrapping is often format-specific** — the AAX slice can be PACE-encrypted while the *VST3/AU is clean*
  (not stripped, no `__Pace_Eden.bundle`) → load that in pedalboard, no wall (Gaffel: AAX=PACE, VST3=clean,
  617 syms). Find installed formats: `pkgutil --pkgs | grep -i <vendor>` (lists `…pkg.<name>.{vst3,au,aax}`).
  Last resort: dlopen the binary directly.
- **Data-driven shell + runtime license (INVERSE-PACE, e.g. Waves WaveShell)** → one fat binary hosts a whole
  catalog; DRM is a **runtime license client** (`WCWLEClient`), **not** static encryption (no `LC_ENCRYPTION_INFO`).
  So it's the *opposite* of PACE: **static REF wide-open** (not stripped, full demangled C++), **black-box gated**
  (unlicensed host rejected ≈ PACE `exit 137`). Recover the catalog from data, not symbols: per-plugin
  `bundle/Contents/Resources/{AlgXML(FourCC),ProcessXML(<ProcessFunctionName>+States/Coefs),ParamXML,PageTable}`.
  **The realtime kernel ships per-plugin as a tiny unencrypted dylib** (`Contents/MacOS/Generic{MacArm,MacIntel}.dylib`)
  exporting the ProcessXML-named proc — decompile THAT (r2/Ghidra by-address), not the 40 MB shell. **License lives
  in the shell, not the kernel** → `ctypes.CDLL` the dylib + drive directly (no host/license) = numbers CLEAN-track,
  entry/ABI REF. Param surface (ParamXML/PageTable) + bundled PDF = CLEAN. Batch the whole catalog: see
  `private-research/WaveShell16/Tools/{decomp_all.sh,ghidra_all.sh}`.
- **Shell + path-indirected shared MONOLITH (iZotope Ozone 11 / RX archetype)** → each per-product `.vst3` is a
  thin `PluginHooks*` stub (~1 MB); `Contents/Resources/iZCore.path` names a **shared `iZ<Suite>Core.bundle`**
  (~100 MB, in `~/Library/Application Support/iZotope/<Module>/Cores/`) holding **every module's DSP in ONE
  binary** — RTTI: `DSP::Ozone<Module>` (Maximizer/DynEq/Exciter/VintageTape…) each a plug-in **`DSP::Element`**
  on `OzoneDSPSet`/`ElementHost` (command pattern). **No PACE, not stripped of text, RTTI intact** → load the
  product `.vst3` in pedalboard (CLEAN, full param surface) AND Ghidra the core by-address (REF); **decode-once
  covers the whole suite.** Unlike Waves (data-bundle + tiny per-plugin kernel dylib), iZotope = one fat
  monolith, all modules inside, **no license gate in the measured path**. Find cores:
  `find ~/Library/Application\ Support/iZotope -iname '*Core.bundle'`. (Worked: Ozone 11 Maximizer.)
- **STATIC-LINKED shared engine (Native Instruments "Effekt Rig" archetype)** → a product *family* (Bite/Dirt/
  Freak/Raum) where each `.vst3` is its **own full ~120 MB binary** but they are **byte-near-identical** — one
  engine `ni::effektrig::dsp` + statically-linked Qt, **compiled into each plugin** (not a separate shared bundle
  like iZotope, not a data shell like Waves). Detect: `nm` symbol counts are equal & huge (~144k) across the
  family; the **common-symbol intersection is ~99%** (`comm -12` two sorted `nm` dumps). Each plugin's unique
  ~1k syms = its QML `<Name>UI` + ONE DSP class `…dsp::<name>::<Name>` on `ModulatableDSPCore<NIn,NOut,NParams>`
  (the `<NIn>`=4 ⇒ sidechain). **No PACE, not stripped** → black-box each in pedalboard (CLEAN), pull the
  per-plugin DSP-class symbol roster as REF; decode-once on the shared engine covers the family. (Worked: NI
  Bite/Dirt/Freak/Raum, all v1.3.7, 135 431 common syms.)
- **Shared SOURCE toolkit, NOT a shared binary (Valhalla DSP archetype)** → a vendor reuses an in-house C++
  library across a product line, but **statically compiles it into each plugin with hidden visibility** → the
  `comm -12` exported-symbol intersection is **~0** (looks "not shared"), yet each plugin is built from the same
  primitives. **The tell is class-NAME recurrence, not symbol overlap:** dump each roster (`nm -U|c++filt`) and
  grep a vendor prefix — the same toolkit classes appear in every non-stripped sibling (Valhalla: `VMod_DelayLine`/
  `VMod_Biquad`/`VMod_TriOsc`/`VMod_Rotate`/`VMod_IIRPolyphase` + specialized `VMod_PitchShiftH949`/`VMod_DiffChorus`,
  each under a per-plugin `VPlug_<Name>` engine). **No decode-once shortcut** (no shared binary to decode), but
  identifying the toolkit tells you what primitive each plugin is built from → faster black-box hypotheses.
  Newer builds in the same line may be fully **stripped** (3 syms) → black-box only. (Worked: 9 Valhalla plugins.)

## Track 1 — Black-box system-ID (CLEAN, always do this)
Measure behaviour; never look at asm for these numbers.
- **Host route:** `pedalboard.load_plugin(<vst3/au>)`, render mono/stereo, probe. Template:
  `private-research/Pro-L2/Tools/prol2_sysid.py`, `AC-1/Tools/ac1_sysid.py`.
- **Direct-FFI route (if clean C ABI):** `ctypes.CDLL(<binary>)` and drive the DSP with NO host —
  faster, sample-exact, and getters expose internal state. Template: `assets/ffi_harness.py.tmpl`.
- Standard probes: static curve (threshold/ratio/knee), step (attack/lookahead/release),
  harmonics (per-mode distortion), impulse (OS FIR / latency), dual-burst (program-dependent release).

## Track 2 — Static (TAINTED / reference-only)
Use to *navigate* and *form hypotheses*, then confirm in Track 1.
- **r2:** `assets/extract.sh.tmpl` (thin arch, demangle → syms/ffi/types), `assets/cmds.r2.tmpl`
  (targeted disasm — `aa` then `af@sym; pdf@sym`; full `aaaa` too slow on 30 MB).
- **Ghidra (C-like pseudocode):** needs `JAVA_HOME=/opt/homebrew/opt/openjdk@21`.
  v12 dropped Jython → write the post-script in **Java**, target **by address** (name-matching pulls
  in bundled zlib/jpeg/HarfBuzz noise). Template: `assets/ghidra_decompile_by_addr.java.tmpl`.
  Keep the project (`-import` once, then `-process … -noanalysis` to re-run fast; never `-deleteProject`).
  **Ghidra-12 gotchas (hard-won, FabFilter suite):** (a) headless = `/opt/homebrew/Cellar/ghidra/<ver>/libexec/support/analyzeHeadless`;
  **v12 succeeds where r2's `pdg`/r2ghidra is ABI-incompatible** → use Ghidra for the C pseudocode. (b) **OSGi
  script-bundle resolver breaks when the project or `-scriptPath` live under `/tmp`** (the `/tmp`→`/private/tmp`
  symlink) **or contain a SPACE anywhere** (e.g. `…/Easby Plugins/…`) → keep the `.java` post-script in a
  space-free dir (`~/ghidra_scripts`), project under `~/`, and **run from a space-free cwd** (`cd ~`). The compiled
  bundle is cached by **class name**, so a failed first run *poisons* re-runs that reuse the same name → give the
  script a **fresh class name** (and clear `~/Library/ghidra/<ver>/osgi`) to recover. (`-import` may have spaces; only the script path/cwd matter.) (c) **addresses are per-slice** — an AAX-slice addr ≠ the
  VST3-slice addr (image rebased ~±0x8000) → **relocate the kernel by signature** (4-wide `.4s` Horner loop,
  `dup`-splatted consts, reciprocal prelude), not by a stale address. (d) realtime kernels are schedule-dispatched
  (absent from `afl`) → **locate by NEON/scalar FP-op density per page**, then decompile by address. (e) **exclude
  PNG/zlib gamma-LUT funcs** (gAMA/IDAT strings) — density-flagged but not audio.
- **Capture maximally — grab all the machine code you can (REF is cheap insurance).** When a binary is
  open (not a wall), dump *everything* under the hood and quarantine it: full FFI export list, `pdf` disasm
  of every DSP fn, Ghidra C pseudocode (by-address), `#[repr(C)]`/param **struct layouts**, vtables/RTTI,
  register-ABI notes, leaked crate/dev paths, even readable `Resources/` manifests. REF is reference-only,
  but it (a) tells you *what* to measure, (b) explains *why* a curve looks odd, (c) hugely cheapens the
  **next sibling** plugin — shared engines decode once (AC-1/AE/AS = one vendor Rust toolchain; AE-1a/b/p =
  one `tone` engine, 3 param subsets). More REF captured now = faster CLEAN later. Even at a stripped/DRM
  wall, still grab what's reachable: `strings`, `__TEXT` entry disasm, Info.plist, codesign/RTTI. Quarantine
  it all under `decomp/`; never let it cross into product.

## Gotchas (hard-won — check these first)
- **Is it even a DSP processor? Null-test FIRST.** Some "plugins" are unity pass-through: a modulation-matrix
  host (MegaMod = 16 LFOs/macros, no audio path), a network utility (DAWstream = audio-over-WebSocket, iPlug2 not
  JUCE). Render in→out, check `max|out−in|` ≈ 0 dB before designing probes — saves a wasted full run. (Also: a
  plugin may expose **only `bypass`** to the host with all controls in a web UI — DM5MASTER; then black-box the
  default state, params are unreachable from pedalboard.)
- **Per-param null-test the tails — "reserved"/dead enum bands ship in the UI.** Beyond whole-plugin null, sweep
  each suspect param raw 0→1 vs the default and check `max|Δ|`: bit-exact 0 ⇒ INERT (modeled-but-disabled UI
  placeholder). Seen: Supermassive `reserved1-4`, FutureVerb `reserved1-8`, AOM bend/pivot, and **a live enum with
  dead bands** — UberMod `type` exposes 0-24 but only 0-9 are real DSP (10-24 = bit-exact dry). Don't document a
  param as functional until a null proves it.
- **Enum enumeration: a coarse taper UNDERCOUNTS.** Sweeping a mode/type param at ~11 points misses values
  (Valhalla: FutureVerb echomode read 6 → actually 12; reverbmode 4 → 8; Plate type 6 → 12; Room 10 → 12).
  Re-enumerate at high resolution (`--taper-n 96`) and dedupe `string_value` to get the true list + per-value raw band.
- **Cold-start NaN, sticky per-process (Hilbert/feedback DSP).** Some plugins intermittently emit NaN on the
  FIRST render after load (uninitialized analytic-signal / feedback state); worse, the corruption is **per-process
  sticky** — the **2nd render in the same process** poisons state, so a warmup double-render is the *bug*, not the
  fix, and in-process retry can't recover. Fix: render **exactly once per process**, check `np.isfinite`, and on
  failure **re-exec a fresh subprocess** (env-guarded retry). Dry path is usually clean — wet/feedback path NaNs.
  (Worked: ValhallaFreqEcho ~10% cold NaN; harness `valhalla_sysid.py` auto-reexecs.)
- **Name lies — confirm type by measurement.** "Tape Fiasco" is a buffer-glitch FX (stretch/stutter/varispeed),
  NOT a tape saturator. Triage the strings/params, then *measure* the class; don't trust the marketing name.
- **Shared-engine detection (generalize):** sort each binary's `nm -U` and `comm -12 a.syms b.syms | wc -l` →
  if the common set is ~99% of each, it's ONE engine across the family (decode-once). Equal + huge `nm` counts is
  the first tell. Covers the binary-sharing archetypes (FabFilter core / Waves shell / iZotope monolith / NI static-link).
  **Caveat — `comm -12` ≈ 0 is NOT proof of "independent":** a vendor can share a SOURCE toolkit compiled in with
  hidden visibility (0 *exported* overlap) — confirm by grepping a vendor class-prefix across `c++filt` rosters
  (recurring `VMod_*`/`VPlug_*`-style names ⇒ Valhalla "shared SOURCE toolkit" archetype, no decode-once but tells you the primitives).
- **Dynamic vs memoryless saturation tell:** a steady 1 kHz tone at MAX drive reading **≈0 % THD** ⇒ the saturator
  is **program-dependent / circuit-stateful** (McDSP Analog Channel), not a memoryless shaper — sweep THD vs level
  AND frequency to characterize (a memoryless shaper would distort the steady tone hard).
- **FFI shim → real impl:** `_x_set_ratio` just `bl`s `Crate::…::set_ratio::h…`. Follow the `bl` for math.
- **Register types (AArch64):** continuous params = **f64 in d0**; int/bool = **i32 in w1**; getters return d0/x0.
- **Units bite:** time params may be **seconds, not ms** — a clamp like `(t−0.0005)/0.0335` silently
  saturates if you pass ms → every setting looks identical. Decompile the setter to confirm the unit.
- **Init / un-mute:** Rust DSP often starts muted; must call a commit (`update_parameters`) after sets,
  and the **first block is warmup** (latency + priming) → discard it.
- **Process ABI:** confirm in-place vs **separate in/out** buffers, and f32 vs f64 — wrong guess segfaults
  (a length passed where a pointer is expected). Read the inner fn's memcpy to settle it.
- **create() args:** constructors often need sample_rate (feeds loudness/EBU) — passing none → `NoMem` panic.
- **dlopen a bundle:** `ctypes.CDLL` loads MH_BUNDLE fine; dlsym names drop the leading `_`.
- **pedalboard auto-compensates reported PDC** → an impulse reads **0 latency even with limiting hard-engaged**;
  the lookahead is real (prove it with a zero-overshoot attack step) but its sample count is **hidden** from the
  impulse. **Read it directly: `p.reported_latency_samples`** gives the exact PDC before auto-comp (Invisible
  Limiter IL=2496 / LL=336 @48k, matched the help-doc 52/7 ms) — no REAPER round-trip needed. (REAPER
  `TrackFX_GetNamedConfigParm(tr,fx,"pdc")` stays the fallback for PACE plugins pedalboard can't host.)
- **pedalboard `raw_value` is the VST3 NORMALIZED [0,1], not the real unit** (load-bearing — cost a full debug
  cycle on Invisible Limiter): writing a real dB/Hz into `raw_value` is **silently clamped/ignored** by the DSP,
  so every setting reads identical (a unit-bite sibling of the seconds-vs-ms trap). Convert yourself
  `raw=(real−lo)/(hi−lo)` over the param's `[min,max]`; sweep raw 0→1 logging `string_value` to recover the real
  norm→real taper (linear vs log/exp) and to enumerate enum bands. (`AudioProcessorParameter` exposes `[min,max]`
  but the DSP only consumes the normalized value.)
- **True-peak vs sample-peak, black-box:** clamp an **HF tone** to the ceiling, compare sample-peak vs
  **8×-oversampled** (zero-pad-FFT) true-peak — TP-limiter keeps true_peak≈ceiling; **sample-peak-only lets it
  overshoot +2…+3 dB**. **Use a tone OFF Fs/4** (7k/11k @ 48k) — a tone AT exactly Fs/4 makes zero-pad
  reconstruction ill-conditioned → a **false +2 dB artifact** that looks like TP failure but isn't.
- **Shared-monolith RTTI roster:** when one binary hosts many modules (iZotope), the per-module DSP class names
  hide in **mangled RTTI strings**, not the external symbol table — `strings <bin> | grep -oE 'N3DSP[0-9]+[A-Za-z]+E' | sed 's/^/_ZTS/' | c++filt`
  recovers the whole `DSP::*` Element roster (kernels themselves are local-stripped → Ghidra by-address/density).
- **REAPER measurement gotchas** (hard-won this round): (a) **`Range`/depth params often default to 0 = no
  effect** — a gate/expander reads as unity until you set Range (ML4 trap; cost me a whole run). (b) **`Solo`
  may be metering-only**, not audio-isolating — ML8000 band-solo returns full-range flat (no crossover slope
  that way); ML4 band-solo *does* isolate. Probe with an impulse before trusting solo. (c) **Apply-FX-as-take
  PDC-compensates** → impulse latency ≈ 0; read the `pdc` config-parm for real latency. (d) **Apply-FX ignores
  track receives** → sidechain MUST use Freeze. (e) **last staircase segment** can read silence (PDC trim
  shifts past EOF) → ignore the top segment. (f) auto-quit via `40004` prompts-to-save on a dirty project →
  `job.quit=false` + `killall REAPER`. (g) job-file name ≠ job-`tag` bites the run loop — key the wait on the
  manifest `tag`, not the filename. (h) **"demo-mute" false positive:** trailing post-PDC silence in an
  Apply-FX render reads like a periodic demo mute → don't judge iLok auth from the tail. Analyze ONLY the
  signal region (e.g. 0.2–11.5 s of a 12 s tone): clean passthrough + flat SNR there = **authorized**, not demo.

## Per-type playbook — reasoning + probes by DSP class
Pick by what the plugin *is*; the type dictates which CLEAN probes fully characterize it + which REF to pull.

- **Linear — EQ / filter** (AE-1a/b/p, Pro-Q4): linear system → **frequency response *is* the spec.**
  Per-band **magnitude+phase** via log-swept sine or impulse-FFT at several gain settings → center freq,
  Q/bandwidth, gain ladder, bell-vs-shelf, **min- vs linear-phase**, M/S-vs-L/R routing, latency (impulse).
  REF: filter topology (biquad / SVF / **WDF circuit**), band freq/Q tables, param struct. **Watch inert/NULL
  params** — modeled but disabled in the build (AE Drive/JFET/Makeup measured null); measure to prove what
  actually ships, don't trust the param list.
- **Linear — multiband splitter / crossover** (Gaffel): solo each band (mute others) + impulse-FFT →
  crossover Hz; **−6 dB crossing = Linkwitz-Riley** vs **−3 dB = Butterworth**; skirt slope → order
  (12 dB/oct=LR2, 24=LR4); **all-bands-active sum @ 0-dB ripple = phase-coherent** (LR sums flat/allpass);
  latency = IR-peak index (0 ⇒ IIR, not linear-phase FIR). Gotcha: ordered crossovers (f1<f2<f3) **clamp
  each other** when swept — shove neighbors to the rails to map one crossover's true range. Linear ⇒ one
  impulse fully specs it (mag+phase); no per-band gain ⇒ it's a router/splitter, not a multiband EQ.
- **Dynamics — comp / leveler** (AC-1, Pro-C3): time-varying gain → static + time + program response.
  Static curve (thr/ratio/knee per setting), step (attack/release), detector kind (peak vs **RMS boxcar
  window** — release floor often = window length, not the release param), dual-burst (program-dependent
  release), auto-gain. REF: detector fn + gain-computer fn (one computer may serve comp *and* limiter).
- **Dynamics — limiter / brickwall** (AL-1, Pro-L2, ML*, Ozone 11 Maximizer): per-sample gain law (static),
  attack **slew** (dB/sample), release (single + dual-burst), **lookahead/latency** (impulse), **true-peak**
  ceiling, OS. **TP test = HF tone clamped to ceiling, sample-peak vs 8×-oversampled true-peak (tone OFF Fs/4);
  divergence ⇒ sample-peak-only, not TP** (Ozone Maximizer's exposed params = sample-peak; TP overshoots +3 dB).
  **Release on a HELD carrier + transient burst** (not a dropping input — out/in ratio jumps the instant level
  falls, masking the release); a "Character/IRC" knob maps to an adaptive release ladder (Ozone: 0→~0 ms,
  10→~39 ms super-linear). REF: per-sample gain fn + combine mode (pure-max-lookahead etc.).
- **Nonlinear — saturation / clipper** (AS-1, Saturn2, FLVTTER-clip): nonlinear → transfer curve + spectrum.
  Static **transfer curve** (in→out DC/slow-ramp), **THD + per-harmonic** (H2/H3/H4…) vs drive, per-model
  fingerprint, **asymmetry** (even harmonics ⇒ asymmetric), OS/aliasing (HF tone → check images). Critical:
  **memoryless waveshaper vs stateful circuit solver** — sweep THD vs *level* AND *frequency*; freq-dependent
  ⇒ it has memory (AS-1 = re-solved nodal circuit, not a tanh). REF: shaping fn / circuit solver + per-model
  constants (diode Is/n/Vt, BJT pair).
- **Sidechain / aux-bus / spectral FX** (FLVTTER): **pedalboard feeds the MAIN bus only** (4-ch in →
  `does not support 4-channel`) → SC-dependent DSP (ducking, SC-tension, SC-keyed clip) is unreachable there.
  **SOLVED in REAPER via track-routing + Freeze** (see DRM entry below) — measured FLVTTER's SC ducking +
  tension-depth scaling CLEAN that way (REF→CLEAN). Main-path CLEAN regardless: `mode` values, clip
  curve/ceiling, FFT-mode latency (= `fft_size`).
- **Stripped / DRM — PACE-iLok** (MELD, ML4000/ML8000 = McDSP): static `__text` is **encrypted** → a wall
  (don't crack it; dumping decrypted code from memory = defeating anti-debug = circumvention, excluded).
  **First check sibling formats — PACE often wraps only the AAX slice; the same product's VST3/AU may be clean**
  (Gaffel: AAX=PACE, VST3=clean → straight into pedalboard, zero DRM dance). If *every* format is PACE:
  **`exit 137` SIGKILL in pedalboard ≠ unmeasurable** — PACE only rejects the *headless non-notarized*
  host. **Route black-box through a notarized DAW with the iLok authorized** — REAPER works great and is fully
  scriptable, no GUI clicking:
    1. ReaScript Lua: `TrackFX_AddByName(tr,"<Name> (Vendor)",false,1)` → loads (PACE happy).
    2. `TrackFX_GetNumParams`/`GetParamName`/`GetFormattedParamValue` → **dump the full param surface** (CLEAN —
       names/ranges/enums finally readable; e.g. recovered ML's 4 modes + 8-band crossovers this way).
    3. `TrackFX_SetParamNormalized(tr,fx,idx,v)` per probe; log `GetFormattedParamValue` → CLEAN norm→real map.
    4. **`Main_OnCommand(40209)` = Apply-track-FX-to-items-as-take** → bakes FX output to WAV *offline* (no
       render dialog). Read take source via `GetMediaItemTake_Source`→`GetMediaSourceFileName`. Analyze WAVs.
    5. **Param calibration:** sweep each key param norm 0→1, log `GetFormattedParamValue` → exact **norm→real
       map** (recovered ML Threshold/Ceiling −36…0 dB *log* taper, Release 1 ms–5 s *exp*, 6 modes
       Clean/Soft/Smart/Dynamic/Loud/Crush). No render — pure introspection, fast.
    6. **Exact latency:** `TrackFX_GetNamedConfigParm(tr,fx,"pdc")` → real lookahead in samples (ML = 51) —
       beats the PDC-compensated impulse.
    7. **Sidechain / aux bus** (Apply-FX **ignores receives** → must FREEZE): FX-track 4-ch +
       `CreateTrackSend(scTrk,fxTrk)` with `I_DSTCHAN=2` (ch 3/4); main item on FX-track, SC item on scTrk;
       select FX-track + `Main_OnCommand(41223)` (**Freeze to stereo**) renders FX *with the receive* → read the
       frozen take source; `41644` unfreezes for the next probe. Worked: `FLVTTER/Tools/flvtter_sc_probe.lua`.
    Unattended driver: drop a temp `~/Library/Application Support/REAPER/Scripts/__startup.lua` that `dofile`s
    the probe (reads a `/tmp/*_job.json`), `open -a REAPER` (Bash), poll for the output JSON, `killall REAPER`
    (set `job.quit=false` + force-kill — `Main_OnCommand(40004)` prompts to save → hangs). Remove the shim after.
    Caveat: Apply-FX **PDC-compensates latency** (baked WAV is shifted → impulse-latency reads ~0; get exact
    lookahead from the reported PDC instead). This is CLEAN (measuring a licensed plugin in a real host).
    **Worked example:** `private-research/ML4000/Tools/{ml_reaper_probe.lua,ml_sysid.py}` (param dump + gain
    curve + modes + TP for ML1/ML4/ML8000). Same trick drives a real aux **sidechain** (route a 2nd track) →
    unblocks FLVTTER-class SC DSP that pedalboard's main-bus-only path can't reach.

## Output contract → easby-programming
For each plugin produce a distilled spec (see easby-programming/plugins/_TEMPLATE.md):
identity, type, **measured_on** (plugin ver/SR/tool), signal chain, per-stage formula (tagged CLEAN/REF),
param table w/ units & ranges, FFI contract (if any), open questions. Drop a catalog row in
easby-programming/SKILL.md. Implementation craft + verified primitives live in easby-programming
(`implementation-doctrine.md`, `building-blocks/`).

## Enforce the firewall (CI / pre-commit)
The CLEAN/REF rule is only real if mechanical. In every product repo install the gate:
`assets/firewall_check.sh <product_src>` (fails on any REF/quarantine reference); hook template
`assets/pre-commit.hook.tmpl`. Tainted artifacts stay in `decomp/` or `_quarantine_disasm/`, never imported.

## Reference jobs (already done — study these)
- **AC-1** (full FFI+Ghidra decode, JUCE→Rust `dynamics`): [AC-1.md](../easby-programming/plugins/AC-1.md)
- **AE-1a/b/p** (EQ; one shared Rust `tone` engine → 3 param-subset variants; FFI struct + pedalboard):
  [AE-1a.md](../easby-programming/plugins/AE-1a.md)
- **AS-1** (saturation; Rust `harmonics` nodal-circuit clipper, struct-based FFI): [AS-1.md](../easby-programming/plugins/AS-1.md)
- **FLVTTER** (JUCE C++ sidechain ducker/clipper; main-path CLEAN, **SC ducking + tension-depth now CLEAN via
  REAPER Freeze**; exact AM/tension formula REF): [FLVTTER.md](../easby-programming/plugins/FLVTTER.md) · `FLVTTER/Tools/flvtter_sc_probe.lua`
- **ML4000_ML1/ML4, ML8000** (McDSP, PACE-iLok → **CLEAN via REAPER**, static walled): one shared brickwall
  core (6 modes, Threshold/Ceiling/Release/Knee norm→real maps, PDC 51); ML8000 8 per-band limiters; ML4 4
  per-band comps + gate(−60)/exp(−24), xover 100/1k/10k: [ML8000.md](../easby-programming/plugins/ML8000.md) · harness `private-research/ML4000/Tools/`
- **MELD** (Metric Halo channel strip, PACE — CLEAN via REAPER; 107-param dump, comp `MIO` ratio 2→1000:1 +
  EQ/MixHead/limiter/loudness): [MELD.md](../easby-programming/plugins/MELD.md)
- **Gaffel** (Klevgrand, JUCE): **AAX = PACE wall, but the same product's VST3 is clean** → black-boxed in
  pedalboard, no DRM route needed. LR4 4-band crossover splitter (−6 dB cross, 24 dB/oct, 0-ripple phase-
  coherent sum, zero latency, split 160/1k/5k): [Gaffel.md](../easby-programming/plugins/Gaffel.md).
  **Lesson: check sibling formats before trusting a PACE wall.**
- **FabFilter suite — all 11, Ghidra REF-complete** (Pro-L2/C3/DS/G/MB/Q4/R2/Saturn2/Timeless3/Twin3/Volcano3):
  black-box CLEAN spec + Ghidra exact-code REF each, quarantined under `_quarantine_disasm/<NAME>/decomp/ghidra/`
  (`<kernel>.c`, `coeff_table.md`, `architecture-findings.md`). Crown jewels: gain law `−(20/ln10)·ln|1−x|`
  (Pro-L2/C3, Cephes logf→dB), 14-waveshape `switch` + `KNEEMIX`/`OUTGAIN` tables (Pro-G/Saturn2), Orfanidis
  magnitude-matched biquad (Pro-Q4), analog-prototype IIR→bilinear (Pro-DS), FDN+**Hadamard** matrix + decay-EQ
  (Pro-R2), **TPT/ZDF SVF** (Twin3/Volcano3/Timeless3), band-limited **additive-wavetable** osc (Twin3),
  polyphase-FIR fractional delay (Timeless3). **Key finding: one shared FabFilter DSP core** reused suite-wide
  (kernels byte-identical across plugins — see Coverage policy) → decode once, reuse on siblings.
- **Waves WaveShell 16.8 — whole catalog decompiled (INVERSE-PACE archetype):** 215 plugins / **677 realtime
  kernels** fully recovered REF — r2 disasm (72 MB) **+ Ghidra C-decompile (29 MB), 677/677, 0 fails**. One fat
  shell (94.6k syms) + `WavesLib` engine (39.6k syms, Mitra/Butterworth biquad designers) + per-plugin **data**
  bundles whose realtime DSP is a tiny **unencrypted `Generic*.dylib`** (route: ProcessXML `<ProcessFunctionName>`
  → that exported symbol → decompile). No static encryption (license = runtime `WCWLEClient`); license is in the
  shell, not the kernel → FFI-drivable. Recovered e.g. CLA-76 (`1176`: format×ch dispatch → `ProcessType<float,2>`
  + modeled `HumGenerator`). Corpus `_quarantine_disasm/WaveShell16/decomp/` (index.csv + algorithm_index.csv);
  batch tooling `WaveShell16/Tools/{decomp_all.sh,ghidra_all.sh,wdecomp.java}`: [WaveShell16.md](../easby-programming/plugins/WaveShell16.md).
- **Ozone 11 Maximizer** (iZotope — **shell + shared-monolith archetype**): thin `PluginHooksVST3` → `iZCore.path`
  → **one `iZOzone11Core.bundle` (99.8M) shared across the whole Ozone 11 suite** (all module DSP as `DSP::Element`
  classes; no PACE, not stripped of text, RTTI intact → Ghidra-once = whole suite). CLEAN black-box (pedalboard):
  exact sample-peak brickwall, lookahead (0-overshoot), `Character` 0..10 = continuous-IRC release (0→~0 ms,
  10→~39 ms), **TP overshoots +3 dB ⇒ sample-peak only**, odd soft-clip L/M/H = drive +1.5/+3.7/+6 dB.
  Harness `Ozone11Max/Tools/ozmax_sysid.py`; REF roster `_quarantine_disasm/Ozone11Max/`:
  [Ozone11-Maximizer.md](../easby-programming/plugins/Ozone11-Maximizer.md).
- **AL-1**: clean-room limiter reference (CLEAN system-ID, no vendor binary). See easby-programming catalog.
- **Batch 2026-06 — 27 plugins, 4 parallel `easby-programmer` agents** (see memory `batch-decomp-2026-06`):
  • **NI Bite/Dirt/Freak/Raum** = the **static-linked shared-engine archetype** above ("Effekt Rig" + static Qt,
    135 431 common syms / 99.4%) — black-box CLEAN, per-plugin DSP-class roster REF.
  • **McDSP suite (PACE)** — CompressorBank/MC2000/FilterBank share ONE dynamics+filter core (byte-identical
    norm→real maps + shared filter ladder); all 15 PACE plugins iLok-authorized → CLEAN via REAPER, static walled.
    Analog Channel saturation is **dynamic** (0% steady-tone THD). Bus Processor 670 = Softube vari-mu; soothe3 =
    oeksound (param-surface only); MB MixHead/White Room = Metric Halo.
  • **On-target for ES-L/ES-X:** **TDR Limiter 6 GE** = genuine **true-peak** (Δ+0.04 dB) — the TP counter-example
    to Ozone Maximizer (sample-peak +3 dB); harness `TDR_Limiter6/Tools/tdr6_sysid.py`. **OTT** (Xfer) fully CLEAN
    (LR4 90 Hz/2.4 kHz, ∞:1 up+down, fixed ~3 ms atk, rel≈Time); `OTT_xfer/Tools/ott_sysid.py`.
  • Specs in easby-programming catalog; **MegaMod/DAWstream null-tested = no audio DSP** (utilities).
- **Batch 2026-06b — Soundtoys 5.5, all 23 plugins, 6 parallel `easby-programmer` agents** (see memory `soundtoys-re`):
  the **static-linked shared-engine archetype** again — every plugin statically links ONE "Soundtoys" framework (dup
  ObjC classes `SoundtoysCocoaView`/`AuxWindow`/`LEGACY_SYNC_*`) → load one-per-process. **Only AAX was installed
  (PACE-wrapped, Pro-Tools-only)** → re-installed VST3 from soundtoys.com; **VST3 is pedalboard-hostable (NO headless
  SIGKILL — unlike McDSP)** → fast black-box CLEAN for all 23. Types: Decapitator (5-model memoryless sat A/N odd·E/T/P
  even), Radiator/LittleRadiator (Altec tube), Devil-Loc(+Deluxe) (Level-Loc AGC+crush), SieQ (EQ), EchoBoy(+Jr)/
  PrimalTap(+Little)/Crystallizer (delay/granular), PhaseMistress/Tremolator/PanMan (mod), FilterFreak1/2 (SVF),
  MicroShift/LittleMicroShift/LittleAlterBoy (pitch), SuperPlate/LittlePlate/SpaceBlender (reverb), EffectRack (container,
  null passthrough). **Two harness gotchas (new):** (1) mode/style enums **latch one block late** → warmup-render
  (`render_settled`); (2) some *structural* params (EchoBoy `style`, PrimalTap `freeze`/`feedback`) + **all tempo-sync**
  need host suspend/transport pedalboard lacks → **deferred to REAPER**. Harness `private-research/Soundtoys/Tools/st_sysid.py`.
- **Batch 2026-06c — Valhalla DSP, 9 plugins, 2 sub-batches of parallel `easby-programmer` agents** (see memory `valhalla-re`):
  FreqEcho/SpaceModulator/Supermassive/VintageVerb + FutureVerb/Plate/Room/Shimmer/UberMod — reverb/delay/mod FX,
  off-axis from ES-L (KB coverage, like Diva). All JUCE VST3, universal, **no PACE/DRM** → straight pedalboard CLEAN.
  **New archetype: "shared SOURCE toolkit"** (`VMod_*` lib statically compiled into per-plugin `VPlug_<Name>` engines,
  hidden visibility → 0 exported overlap but class-name recurrence in rosters; see archetype list + detection caveat).
  Newer builds (Supermassive v5, FutureVerb) **stripped (3 syms) = black-box wall**; rest carry rosters (REF names only,
  no Ghidra — off-axis). **New gotchas captured above:** cold-start NaN sticky-per-process (FreqEcho → 1 render/process
  + subprocess re-exec), per-param null-test of `reserved`/dead-enum-band params (Supermassive/FutureVerb/UberMod
  `type` 0-9-live), coarse-taper enum undercount (re-enumerate `--taper-n 96`). DSP highlights: FreqEcho true Bode/Hilbert
  **SSB** vs SpaceMod/UberMod **Doppler-ramp barberpole** (Δf∝carrier); Shimmer **pitch-shift-in-feedback** (`VMod_PitchShiftH949`,
  f·2^k cascade); Room **3-band frequency-dependent RT60**. Harness `private-research/Valhalla/Tools/valhalla_sysid.py`.
