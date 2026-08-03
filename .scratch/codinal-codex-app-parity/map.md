## Destination

Ship Codinal with evidenced functional parity for the current public ChatGPT
desktop workspace and Codex developer workflows: every documented feature is
classified, every in-scope path has a pure-Rust implementation or explicit
adapter boundary, and the installed release passes security, accessibility,
performance, interaction, signing, and packaged end-to-end gates.

## Notes

- Primary sources: `https://learn.chatgpt.com/docs/app` and the current Codex
  manual fetched through the OpenAI docs workflow.
- “Parity” means equivalent user outcomes, not private OpenAI protocols,
  service identity, trademarks, or copied proprietary assets.
- Pure Rust remains non-negotiable: no Tauri, WebView, WebKit, Python,
  JavaScript, HTML, or CSS runtime.
- Preserve authenticated loopback boundaries, explicit approvals, redacted
  audit trails, atomic storage ownership, and recoverable release updates.
- This effort carries execution after the baseline is locked: resolve one
  ticket at a time, then create implementation tickets only when their scope
  and acceptance evidence are sharp.
- Existing cutover maps remain historical evidence; this map owns the broader
  product-parity destination.

## Decisions so far

## Not yet specified

- Individual implementation slices; these graduate only after the official
  baseline and current-product audit classify each capability.
- Which hosted or proprietary capabilities require provider-neutral adapters,
  local equivalents, optional connectors, or an explicit unsupported state.
- Cross-platform sequencing after the macOS release candidate.
- Quantitative performance and accessibility thresholds for artifact-heavy,
  browser, computer-use, and long-running workflows.

## Out of scope

- Impersonating ChatGPT/OpenAI services or reverse-engineering private APIs.
- Copying proprietary OpenAI visual assets, model entitlements, or account
  access behavior.
- Claiming parity for a feature without a reproducible acceptance test.
