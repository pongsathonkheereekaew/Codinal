# shared/plugins — plugin CAPABILITY layer (what each plugin does; shared by ALL agents)

Two layers of plugin knowledge, split by the firewall + by who needs what:

| Layer | Content | Who | Where |
|---|---|---|---|
| **Capability** (this dir) | what the plugin *does* + every control + how to *use* it musically (from the vendor manual) | **every easby agent** | `shared/plugins/<NAME>.md` — CLEAN |
| **Deep DSP** | gain law, formulas, FFI contract, signal-chain internals, REF/disasm | **Programmer only** | `easby-programming/plugins/<NAME>.md` |

So Producer/Mixing/Mastering all know *what a plugin can do* (pick the right tool, set the right control) — only
the Programmer side knows *how it works inside* (clone it). A capability card may link to the deep spec, but
holds **no REF** itself.

## How to store a plugin manual
1. Drop the raw manual (PDF/txt/html) into **`manuals/`** — gitignored (source material, like the source books;
   stays local, not bloating the repo).
2. Distill it into a **capability card** `shared/plugins/<NAME>.md` from `_TEMPLATE.md` (tracked, shared).
   The card = what every agent needs to *use* the plugin; the raw manual is just the source.
3. If the plugin is reverse-engineered, its deep DSP spec lives separately in `easby-programming/plugins/`
   (Programmer-only); cross-link from the card's "Deep spec" line.

To distill many manuals at once, an agent team can read `manuals/*` and emit one card each (see how the music KB
+ ML/AE/AS plugin specs were distilled).

## Provenance
Capability cards = **CLEAN** (vendor-public manual + your own usage notes) → any agent, product-safe. Raw manuals
are public vendor docs (not TAINTED) but kept out of git for size. **REF stays only in easby-programming.**
