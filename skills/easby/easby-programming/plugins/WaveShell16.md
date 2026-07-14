# WaveShell 16.8 — Waves Audio (plugin SHELL / shared DSP engine, 215-plugin catalog)

| | |
|---|---|
| Vendor / ver | Waves Audio · WaveShell1-VST3-ARA **16.8.136** (`com.WavesAudio.WaveShell1-VST3.16.8.136`) |
| Type | **Shell host** (one binary hosts the whole Waves V16 catalog) over a **data-driven shared DSP engine** — not a single effect |
| Tech | C++ (`wvWavesV16_8_136::` namespace). 3 layers: shell adapter + `WavesLib` engine + 215 data-only `.bundle`s. WebKit/Metal GUI, Accelerate/vDSP. No FFI to product. |
| Binary | Shell: fat (x86_64+arm64) Mach-O bundle, 40 MB, **NOT stripped** (94.6k syms). Engine `WavesLib1_16.8.136.framework`: **NOT stripped** (39.6k syms). **No PACE / no `LC_ENCRYPTION_INFO`** — DRM = Waves License Engine *runtime* client (`WCWLEClient`). |
| Provenance | **CLEAN** = param surface (ParamXML/PageTable) + bundled PDF manuals + public DSP lit (Mitra/Orfanidis/Zölzer). **REF** = shell/WavesLib symbol dumps + AlgType→engine dispatch (static, quarantined). **No measured DSP yet** (license-gated). |
| Measured on | Static triage only · 2026-06-23 · no black-box (needs Waves license) |
| Source | `private-research/WaveShell16/Tools/` · REF `_quarantine_disasm/WaveShell16/` |

## Architecture (3 layers — data-driven)
```
VST3/ARA host
   └─ WaveShell1-VST3-ARA   (40MB) host adapter + WCWLEClient license + GUI + registry + cloud(WS/Redis)
        └─ WavesLib1_16.8.136.framework   shared DSP ENGINE (named biquad-designer kernels)
             ↑ dispatched by AlgType FourCC
        └─ Plug-Ins V16/<plugin>.bundle × 215   data + REALTIME KERNEL dylib
              MacOS/Generic{MacArm,MacIntel}.dylib  = ~32KB unencrypted kernel, exports the proc by name (math inlined)
              Resources/{ProcessXML(proc name+States/Coefs), ParamXML, PageTable, Presets, GUIXML, PDF}
```
A "plugin" = **AlgType FourCC** + param/graph data + a **per-plugin realtime kernel dylib**. 215 bundles → **303
distinct AlgTypes**. **Correction to first triage:** bundles are *not* data-only — each ships its realtime DSP as
`MacOS/Generic{MacArm,MacIntel}.dylib` (+ `Linux64/XLMC`): tiny, **unencrypted**, exports the ProcessXML-named proc
(DeEsser → `_DSSproc`/`_DSprocMono`), math fully inlined (imports only `dyld_stub_binder`). WavesLib supplies
**prepare-time** coef designers; the realtime loop is standalone. → **per-plugin decompile target = that 32KB dylib**, not the 40MB shell.

## Provenance route — INVERSE of PACE (key finding)
- **Static REF wide open** — ~134k demangled syms (shell+WavesLib), no decryption; **and** each plugin's realtime
  kernel is a ~32KB **unencrypted dylib exporting its proc by name** → r2/Ghidra by-address, trivial. r2:
  `r2 -A Generic*.dylib; s sym._<Proc>; pdf`. Per-plugin recipe: ProcessXML `<ProcessFunctionName>` → that symbol in
  `MacOS/Generic{MacArm,MacIntel}.dylib` → decompile by address; `States`/`Coefs` give the state/coef struct sizes.
- **Direct-FFI opening (license is in the SHELL, not the kernel):** the kernel dylib has no license check — `ctypes.CDLL`
  it and call `<Proc>(state*, coefs*, params*, in*, out*, n)` with **no host, no license** (AC-1 pattern). Makes the
  *numbers* black-box/CLEAN-track; only entry+ABI is REF. ABI from ProcessXML counts + entry disasm.
- **Black-box CLEAN (in-host) is license-gated** — `WCWLEClient` gates the *shell's* processing; unlicensed headless
  host rejected (≈ PACE `exit 137`). Run via **REAPER + a Waves license** (ReaScript Apply-FX/Freeze, as ML/MELD) —
  or skip the shell entirely via the FFI route above. Opposite of FabFilter/PACE (static-walled, black-box-open).
- **Param surface = CLEAN** (same standing as Weiss Pagetables): names/ranges/enums from `ParamXML`/`PageTable`;
  each bundle also ships a **public PDF manual** (CLEAN literature).

## WavesLib shared DSP engine (REF pointers → PUBLIC methods)
Plain-C `BIQUAD`-struct filter-designer library, reused suite-wide (decode-once-reuse):
- prototype/bilinear: `O2Butterworth`, `ButterworthOrd`, `Calc_Bandpass_ButterworthBiquads`, `BiquadBilinear`, `Ord3_CutFilter`
- shelf/bell/allpass: `Shelv`, `ShelvCf`, `ResShelv`, `SGBell`, `Ord1_AP`, `Ord2_AP`, `DoubleOrd1`
- Mitra family: `ComputeMitraBiquad`, `ComputeMitraBandPS`, `MitraBellWithRefSR`
- analysis/stability: `BiquadPhase`, `BiquadSqMag`, `FixBiquadStability`, `Normalise_EqSec`
→ These are **published** designs (Mitra *DSP*; Orfanidis *High-Order Digital Parametric EQ*, JAES). Cite the
textbook, not the symbol. REF only confirms *which* public method Waves picked.

## Why / design rationale (music ↔ code)
- **Single shell + data-driven engine** → 215 plugins ship/scan/license as one binary; the DSP core (EQ/dynamics
  primitives) is written once and parameterized per product. Explains Waves' house "family resemblance" (shared
  filter/EQ voicing across C4/Q10/Renaissance — same `ComputeMitraBiquad` designer underneath).
- **AlgType FourCC dispatch** → cheap product differentiation: a new plugin = new param/graph data + FourCC, no
  new DSP code. Mirrors FabFilter's shared-core finding, but Waves leaves the symbols named.
- **Runtime license (not static crypto)** → protects the IP without the perf/debug cost of PACE decryption;
  side effect for RE: code is fully legible, only *running* it is gated.

## Parameters
Per-plugin, in `<bundle>/Contents/Resources/ParamXML/1001.xml` + `PageTable/1001.xml` (CLEAN — surface only;
curves still TO MEASURE). Sample AlgType map:

| Plugin | AlgType | Plugin | AlgType | Plugin | AlgType |
|---|---|---|---|---|---|
| DeEsser | `DESR` | C4 | `RMBC` | CLA-76 | `1176` |
| C6 | `6MBC` | API-2500 | `APCO` | H-Comp | `HCMP` |
| MaxxVolume | `IVOL` | Q10 | `EQ10` | … | (303 total) |

## Decompile corpus (REF — quarantined, `_quarantine_disasm/WaveShell16/decomp/`)
**All 677 kernels disassembled** (r2 `aa; pdf`, `decomp_all.sh`) + **Ghidra C-decompile** of every fn
(`ghidra_all.sh`, marquee-first). Indexes: `index.csv` (677 kernels), `algorithm_index.csv` (380 algos +
States/Coefs). Recovered structure (REF) e.g. **CLA-76** (the 1176): `_CLA76Proc` dispatches by sample-format
(int16/float, `buf+0xc`) × channels to templated `ProcessType<float,2>::CLA76Process` (×4), plus a modeled
`HumGenerator` (analog mains hum). Effects tiny (DeEsser 32KB/2 procs); synths huge (Electric Grand 6909 procs).

## FFI contract (REF — recovered, for measurement only)
Per-plugin kernel dylib exports the proc by name; Ghidra-recovered ABI (DeEsser, AArch64):
`Proc(WavesSoundBuf* state, _, char* coefs, int n, int nCh, int* extReq, float* in, float* out, ExternStruct*, sNativeShellInfo*)`
(int16/float by `state+0xc`; `States`/`Coefs` counts in `algorithm_index.csv` size the state/coef blocks).
**License is in the SHELL, not the kernel** → `ctypes.CDLL` the dylib + drive directly (AC-1 pattern), no host/license.
This makes I/O **measurable = CLEAN-track**; the located entry/ABI is REF. No clean *product* FFI — measure, don't import.

## CLEAN measurements
**None yet.** Two routes: (a) FFI-drive the kernel dylib (above) — no license; (b) Waves license + REAPER
(`WaveShell16/Tools/README.md`). All disasm/C corpus is REF until reproduced black-box.

## To implement (ES-L / product, CLEAN-only)
The engine's value is its **public-literature filter designers** — reproduce directly, never from REF:
- **Mitra/Orfanidis magnitude-matched parametric EQ** (bell/shelf/allpass biquads) — see Orfanidis JAES;
  already in scope via Pro-Q4 REF→CLEAN. Shared with FabFilter's Orfanidis finding → one CLEAN building block.
- **Butterworth bilinear band/cut filters** — textbook; building-blocks/biquad.
- Per-plugin dynamics (e.g. CLA-76=`1176`, API-2500=`APCO`) need black-box once licensed; until then = param surface.

---
Provenance tags: **CLEAN** = black-box measurement / public DSP / own voicing (product-safe).
**REF** = disasm/decompile-derived (reference only — reproduce black-box before shipping).
