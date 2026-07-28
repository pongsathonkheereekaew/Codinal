# OSS Survey: AI Inline Completion & Inline Edit (Cmd-K)

Audience: Codinal (Tauri/Rust shell + CodeMirror 6 UI + Python runtime).
Scope: learn from primary sources how mature open-source projects implement
(1) inline ghost-text completion (Phase 51) and (2) inline edit / Cmd-K (Phase 52).

All claims below are verified against the actual source/docs of each project
(repo file paths, function names, constants). Where a project is closed-source
(Cursor), claims are reverse-engineered from their public engineering posts and
clearly marked as such.

Legend: `[P]` = primary source (code/docs we read directly); `[R]` = reverse-
engineered / secondary.

---

## TL;DR — what Codinal should steal from each

| Concern | Best reference to copy | Why |
|---|---|---|
| Debounce + supersede logic | Continue `AutocompleteDebouncer` | Request-ID supersede pattern, no timers leaked |
| Abort/cancel contract | Continue `completionProvider.ts` | `AbortController` driven by editor `CancellationToken` |
| Streaming + "show what we have at X ms" | Continue `DEFAULT_AUTOCOMPLETE_OPTS.showWhateverWeHaveAtXMs = 300` | First-token UX before full stream completes |
| Ghost-text rendering in CM6 | `saminzadeh/codemirror-extension-inline-suggestion` | Canonical `ViewPlugin + Decoration.widget + WidgetType` pattern |
| Inline edit diff format | Aider `SEARCH/REPLACE` blocks | Robust, well-documented, fuzzy fallback ladder |
| Fuzzy/whitespace-tolerant apply | Aider `replace_most_similar_chunk` + `RelativeIndenter` | Handles model indentation mistakes |
| Order-invariant multi-diff apply | Cline `replace_in_file` diff-apply | Handles out-of-order blocks + model-specific markers |
| Speculative decoding for fast apply | Cursor "Fast Apply" (fireworks blog) | ~1000 tok/s for rewrites |
| Per-cursor next-edit (NES) | Continue "next edit" + Cursor Tab | Jump-aware multi-cursor edits |

---

## 1. Continue (`continuedev/continue`) — [P]

Continue is the closest architectural analogue to Codinal's Phase 51: a
TypeScript core (`core/autocomplete/`) that is editor-agnostic, with thin
editor adapters (`extensions/vscode/src/autocomplete/`, `extensions/intellij/`).
For Codinal, the Rust shell + Python runtime map to the "core", and the CM6
adapter maps to the VS Code adapter.

### Repo layout (verified)
- `core/autocomplete/CompletionProvider.ts` — orchestrator
- `core/autocomplete/util/AutocompleteDebouncer.ts` — debounce/supersede
- `core/autocomplete/generation/CompletionStreamer.ts` — streaming to model
- `core/autocomplete/snippets/getAllSnippets.ts` — context window construction
- `core/autocomplete/templating/constructPrefixSuffix.ts` — FIM prefix/suffix
- `core/autocomplete/filtering/streamTransforms/` — line/char stream filters
- `core/autocomplete/postprocessing/index.ts` — cleanup
- `core/autocomplete/util/parameters.ts` — `DEFAULT_AUTOCOMPLETE_OPTS`
- `extensions/vscode/src/autocomplete/completionProvider.ts` — VS Code `InlineCompletionItemProvider` adapter
- `extensions/vscode/src/autocomplete/GhostTextAcceptanceTracker.ts` — accept/reject telemetry

### Default options (`core/util/parameters.ts`, verified)
```ts
export const DEFAULT_AUTOCOMPLETE_OPTS: TabAutocompleteOptions = {
  maxPromptTokens: 1024,
  prefixPercentage: 0.3,        // 30% of token budget to prefix
  maxSuffixPercentage: 0.2,
  debounceDelay: 350,           // ms — the headline number
  modelTimeout: 150,
  slidingWindowPrefixPercentage: 0.75,
  slidingWindowSize: 500,
  useCache: true,
  transform: true,
  showWhateverWeHaveAtXMs: 300, // stream partial result after 300ms
  experimental_includeRecentlyVisitedRanges: true,
  experimental_includeRecentlyEditedRanges: true,
  experimental_includeDiff: true,
  // ...
};
```

### Trigger logic / debounce (`AutocompleteDebouncer.delayAndShouldDebounce`)
- It does **not** track timestamps. It uses a **request-ID supersede pattern**:
  - each call generates a `uuid`, stores it in `currentRequestId`, clears any
    pending `setTimeout`, and sets a new one for `debounceDelay` ms.
  - when the timer fires, it compares the closure's `requestId` with
    `currentRequestId`. If they differ, a newer call superseded this one →
    resolves `true` ("should debounce / abort"). If equal → resolves `false`
    ("proceed").
- The provider calls `await this.debouncer.delayAndShouldDebounce(options.debounceDelay)`; if it returns `true`, the request is abandoned.
- Codinal note: this is cleaner than a classic trailing-edge debounce because it
  naturally handles the "user kept typing during the wait" race without manual
  `clearTimeout` plumbing.

### Abort / cancellation (`CompletionProvider.provideInlineCompletionItems`)
- If no `AbortSignal` is passed, one is created via
  `this.loggingService.createAbortController(input.completionId)`.
- The token is threaded into the streamer:
  `this.completionStreamer.streamCompletionWithFilters(..., signal, ...)`.
- After the `for await (const update of completionStream)` loop, it re-checks
  `if (token.aborted) return undefined;` before post-processing.
- The controller is removed in a `finally` block:
  `this.loggingService.deleteAbortController(input.completionId)`.

### VS Code adapter cancellation (`extensions/vscode/src/autocomplete/completionProvider.ts`)
- A dedicated `AbortController` is created per request.
- It is wired to VS Code's cancellation:
  `token.onCancellationRequested(() => abortController.abort())`.
- The abort signal is forwarded into the core provider.
- `willDisplay()` enforces `if (abortSignal.aborted) return false;` before
  rendering.

### Model call pattern
- LLM is fetched via `_prepareLlm()`; if `completionOptions.temperature` is
  undefined it is set to **0.01** (near-deterministic).
- Context: `getAllSnippetsWithoutRace(...)` gathers snippets, then
  `renderPromptWithTokenLimit(...)` produces the final `prompt`, `prefix`,
  `suffix` (FIM shape).
- Streaming: `CompletionStreamer.streamCompletionWithFilters(...)` returns an
  async iterator; the provider aggregates tokens and runs a stream-transform
  pipeline (`filtering/streamTransforms/`) live.
- `showWhateverWeHaveAtXMs = 300` lets the UI paint a partial ghost text after
  300 ms even if the stream is still open — important perceived-latency trick.
- Result is postprocessed (`postprocessCompletion`) and stored in an LRU cache
  (`AutocompleteLruCache`) keyed by prefix when `useCache` is on.

### Ghost text rendering (VS Code side)
- Returned as `[new vscode.InlineCompletionItem(completionText, range, command)]`.
- Range: for single-line completions, exact char start/end; for multi-line,
  range is "extended to the end of the line".
- The item carries a `command` argument `continue.logAutocompleteOutcome` so
  acceptance triggers telemetry via `GhostTextAcceptanceTracker`.
- Multi-line decision lives in `classification/shouldCompleteMultiline.ts`.

### "Next edit" / jump-aware completion
- `provideInlineCompletionItems` branches between standard autocomplete and a
  "next edit" path based on an active mode + jump state, and validates the
  prediction against any selected completion widget text via `willDisplay()`.
- `RecentlyVisitedRangesService.ts` and `recentlyEdited.ts` feed jump/edits
  context. This is the open-source analogue of Cursor's NES.

### Files worth studying
- `core/autocomplete/CompletionProvider.ts` (orchestration, temp 0.01)
- `core/autocomplete/util/AutocompleteDebouncer.ts` (supersede pattern)
- `core/util/parameters.ts` (`DEFAULT_AUTOCOMPLETE_OPTS`)
- `extensions/vscode/src/autocomplete/completionProvider.ts` (abort wiring)
- `core/autocomplete/templating/constructPrefixSuffix.ts` (FIM shaping)
- `core/autocomplete/generation/CompletionStreamer.ts` (streaming + filters)

---

## 2. Aider (`Aider-AI/aider`) — [P]

Aider is terminal-only (no ghost text), but its **edit-application** logic is
the gold standard for inline-edit (Phase 52). Codinal's Python runtime can
port this almost verbatim.

### The `SEARCH/REPLACE` block format (`aider/coders/editblock_prompts.py`)
Exact markers (regex-verified in `editblock_coder.py`):
```regex
HEAD    = r"^<{5,9} SEARCH>?\s*$"      # <<<<<<< SEARCH
DIVIDER = "======="
UPDATED = r"^>{5,9} REPLACE\s*$"       # >>>>>>> REPLACE
```
A block looks like (from the system prompt example):
```
mathweb/flask/app.py
```python
<<<<<<< SEARCH
from flask import Flask
=======
import math
from flask import Flask
>>>>>>> REPLACE
```
- Filename precedes a fenced code block; the block contains one or more
  SEARCH/REPLACE sections.
- The system prompt enforces: *"ONLY EVER RETURN CODE IN a SEARCH/REPLACE
  BLOCK"* and on failure asks the model to retry.

### Apply ladder (`editblock_coder.py`, verified symbols)
`do_replace(fname, content, before_text, after_text)` calls
`replace_most_similar_chunk(whole, part, replace)`, which tries in order:
1. `perfect_or_whitespace` → `perfect_replace` (exact tuple-of-lines match).
2. `replace_part_with_missing_leading_whitespace` (tolerant of indent drift).
3. Drop a spurious leading blank line (`part_lines[1:]`) and retry.
4. `try_dotdotdots` — supports elision with `...` placeholders; raises
   `ValueError("Unpaired ... in SEARCH/REPLACE block")` / "Unmatched ..." on
   misuse.
5. `replace_closest_edit_distance` — fuzzy fallback (currently dead-codded
   behind an early `return`, but present for reference).
6. `find_similar_lines(search_lines, content_lines, threshold=0.6)` — closest
   match reporting.

### Newer relative-indentation engine (`aider/coders/search_replace.py`)
Aider added a `RelativeIndenter` that rewrites both the file and the SEARCH
block to **relative indentation** (removes shared leading whitespace between
adjacent lines; uses a unicode `←` marker for outdents) before matching. This
makes pairs that "differ significantly in overall indentation" align — directly
addressing the #1 cause of failed applies (model returns code at wrong base
indent). Marker is chosen to be a codepoint not present in either text.

### Failure feedback loop
When a block fails, Aider writes a structured error back into the conversation:
```
SearchReplaceNoExactMatch: This SEARCH block failed to exactly match lines in {path}
<<<<<<< SEARCH
{original}=======
{updated}>>>>>>> REPLACE
```
plus diagnostics like *"The REPLACE lines are already in {path}"* or *"The
SEARCH section must exactly match ... including all white space"*. This
self-correcting loop is a key reason Aider's apply success is high.

### Multi-file edits
No special bulk syntax. The model emits filename + fenced block repeatedly,
once per file. `find_original_update_blocks(content, fence, valid_fnames)` is
a generator that yields `(filename, edit_text)` pairs (and `(None, shell_cmd)`
for shell blocks). Filenames are resolved against `valid_fnames` (files in the
chat) to be robust to model path mistakes.

### Variant coders (worth knowing)
- `editblock_fenced_coder` — fenced variant.
- `editblock_func_coder` — tool/function-call variant.
- `udiff_coder` / `udiff_simple` — unified-diff format (less reliable; benchmarked worse than SEARCH/REPLACE).
- `wholefile_coder` — returns entire file (fallback for weak models).
- `architect_coder` — one model proposes edits, another (editor) applies them.

### Files worth studying
- `aider/coders/editblock_coder.py` (`do_replace`, `replace_most_similar_chunk`, `try_dotdotdots`, regex markers)
- `aider/coders/search_replace.py` (`RelativeIndenter`)
- `aider/coders/editblock_prompts.py` (system prompt + examples)
- `tests/basic/test_editblock.py` (edge cases to copy as tests)

---

## 3. OpenHands (`All-Hands-AI/OpenHands`) — [P]

OpenHands is an **agent runtime**, not an inline-completion engine. It has no
ghost-text completion. Its relevance to Codinal is the **edit tool** design
(Phase 52 backend) and the editor protocol.

### Editor integration
- Connects to editors via the **Agent Client Protocol (ACP)**; for VS Code you
  install the community "VSCode ACP" extension. The agent drives the editor
  through ACP, not through inline-completion APIs.
- No `InlineCompletionItemProvider`-style ghost text. Completion-as-you-type is
  out of scope; the value is agent-driven file edits.

### File editing: `str_replace_editor` tool
A tool exposed to the agent with commands:
- `view` — read a file or directory tree (range-aware).
- `create` — write a new file (fails if it exists, to prevent clobbering).
- `str_replace` — exact string replacement (must be unique; the agent must
  include enough context lines to disambiguate).
- `insert` — insert text at a line number (with a target `insert_line`).

Key design choices Codinal can borrow:
- `str_replace` requires the `old_str` to appear **exactly once**; if not
  unique the tool errors and asks for more context — a stricter contract than
  Aider's fuzzy ladder, good for deterministic agent loops.
- `create` refusing to overwrite prevents accidental data loss.
- The tool returns a snippet of the changed region (not the whole file) to keep
  the agent's context window small.

This is essentially a hardened, agent-facing subset of Aider's apply logic
without the fuzzy fallbacks.

---

## 4. Cursor Tab — [R] (reverse-engineered from public engineering posts)

Cursor is closed-source; the following is synthesized from their blog and
partner posts (Fireworks AI). Treat numbers as approximate.

### Architecture
- **Custom sparse (MoE) model** purpose-built for completion: very long prompt
  (prefix + suffix + cross-file context, reported up to ~13k tokens), very
  small output. MoE suits "huge context, small output" because only a few
  experts activate per token.
- **Speculative decoding, modified for code ("Fast Apply")**: instead of a
  small draft model proposing tokens, *the file you are editing is the draft*.
  The original source is fed as speculated output chunks; the model only
  computes new tokens where a change is predicted, then verifies the rest in a
  single forward pass. With Fireworks' inference stack this reaches
  **~1000 tokens/sec** for rewrites.

### Latency budget
- Target end-to-end round trip (editor → server → model → editor) of
  **~300 ms**.
- A backend change reportedly cut server latency from **475 ms → 260 ms**.

### Prompt construction
- **FIM shape** (prefix before cursor, suffix after). Exact token boundaries
  not published, but the pattern matches Continue's `prefixPercentage`/`suffixPercentage` approach.
- Prompt assembly uses an internal templating system ("Priompt") that treats
  context like prioritized JSX: when the token budget overflows, a binary
  search drops the lowest-priority context first.
- **Codebase indexing via tree-sitter**: code is chunked at function/class
  boundaries so retrieval returns semantically coherent units.
- Context includes recent edits, recently visited/jump locations, and other
  open files (the "Tab is aware of all files and recent changes" UX).

### Next Edit Suggestion (NES) / multi-cursor
- Cursor predicts edits that are not at the cursor — e.g., after renaming a
  symbol on line 12, it suggests corresponding edits on lines 18/24/31. This
  is "jump-aware" completion: the model is told where the user just jumped and
  predicts the next likely edit location. Continue's "next edit" branch is the
  open-source analogue.

### What Codinal can take
- The **speculative-decoding-as-draft-is-your-file** idea is not directly
  portable without a custom model, but the *UX* (show partial fast, verify
  later) is approximated by Continue's `showWhateverWeHaveAtXMs`.
- Priompt-style **priority-ranked context dropping** is a good design for
  Codinal's Python context-builder.
- Tree-sitter chunking at function/class boundaries for retrieval.
- NES/jump-awareness: track last edit location and cursor jumps as context.

### Sources
- "How Cursor Actually Works" — The AI Engineer (Substack)
- "How Cursor built Fast Apply using Speculative Decoding" — Fireworks AI blog
- Cursor Forum: "Exploring the Implementation Principles of Cursor Tab"
- ZenML LLMOps Database: real-time inference case study

---

## 5. CodeMirror 6 completion / ghost text — [P]

Codinal's UI is CM6, so this is the most directly actionable section.

### Built-in `@codemirror/autocomplete`
- Provides `autocompletion({ activateOnTyping, explicitTrigger, override })`
  and a `CompletionSource` function `(context: CompletionContext) => CompletionResult | null`.
- Returns a **popup** of options (`from`, `to`, `options[]`), each with
  `label`, `type`, `apply`, `detail`. This is a **dropdown**, not ghost text.
- Also supports `contextListener` and `aboveCursor` rendering, and the legacy
  `languageDataAt("autocomplete")` hook for language-specific sources.
- Verdict: `@codemirror/autocomplete` is the right primitive for **word/symbol**
  completion dropdowns but **does not** ship a Copilot-style inline ghost text.
  Ghost text must be built with the `view` package.

### Ghost text pattern (canonical) — `saminzadeh/codemirror-extension-inline-suggestion`
This is the reference implementation Continue/others effectively re-implement.
Architecture (three layers):

1. **Fetch plugin** (`ViewPlugin`):
   - `update(u: ViewUpdate)` checks `u.docChanged`; if true, kicks off an async
     `getSuggestion(pos, doc)` call.
   - On resolve, dispatches an `InlineSuggestionEffect({ text, doc })` —
     carrying a **snapshot of the doc** at request time — into the editor state.

2. **State field** (`StateField<{ text, doc } | null>`):
   - Scans transactions for `InlineSuggestionEffect`.
   - **Stale-guard**: only stores the suggestion if
     `tr.state.doc == inlineSuggestion.value.doc`. If the doc changed since the
     fetch started, it resets to `null`. This is the CM6 equivalent of Continue's
     abort-on-supersede.

3. **Render plugin** (`ViewPlugin` producing `DecorationSet`):
   - Decorates at `view.state.selection.main.head` with
     `Decoration.widget(head, widget, { side: 1 })` (side:1 pushes it after the
     cursor).
   - `WidgetType.toDOM(view)` returns a `<span class="cm-inline-suggestion">`
     with `style.opacity = '0.4'` and the suggestion text.
   - `get lineBreaks()` returns the number of `\n` in the suggestion so CM6
     computes multi-line geometry correctly.

4. **Accept keymap** (high-precedence):
   - On `Tab`, if state has a suggestion, dispatch a transaction replacing at
     the cursor (`insertCompletionText`); else return `false` to fall through
     to default Tab.

### Related extension
- `rizerphe/codemirror-companion-extension` — same pattern, plus the ability to
  **display text different from what gets accepted** (useful when you want to
  show a summary ghost text but insert the full edit).

### Codinal implications
- The fetch/state/render split maps cleanly onto Tauri: fetch plugin invokes a
  Tauri command (Rust → Python runtime) returning the suggestion; the
  stale-guard is the natural place to drop superseded results without a JS
  `AbortController`.
- For Phase 52 inline edit, replace the simple `WidgetType` with a richer
  decoration set (diff highlights via `Decoration.mark`) and an accept/reject
  gutter/popup.

---

## 6. Cline / Roo Code / Serena — [P]

### Cline (`cline/cline`) — `replace_in_file` / diff-apply
Cline started by rewriting whole files (issue #583) and moved to a
search-and-replace diff tool, `replace_in_file`, displayed through a
`DiffViewProvider` (side-by-side in VS Code).

Diff format (search-and-replace, but with **model-specific markers**):
- Anthropic models: `- --/+++`-style markers.
- Gemini / xAI models: `>>>/<<<` blocks.
- Default/fallback: SEARCH/REPLACE-style blocks similar to Aider.

Apply algorithm (from the "Improving Diff Edits by 10%" post):
- **Order-invariant multi-diff apply**: applies blocks regardless of the order
  the model emitted them — a common LLM failure mode.
- Evaluated against an open-source harness of real user scenarios; the
  `diffEditSuccess` rate rose >10% on average, ~25% for Claude 3.5 Sonnet.

Accept/reject UX:
- Edits render in a VS Code diff view (`DiffViewProvider`); user accepts or
  rejects per change. Issue #11934 documents a regression where the inline diff
  broke, confirming the inline/side-by-side rendering path.
- Matching is **exact character-by-character** (issue #2909: "Diff Edit
  Mismatch" when whitespace differs), which is why the apply algorithm needs
  the fuzzy/order-invariant layer on top.

Files/concepts worth studying:
- `replace_in_file` tool definition and prompt (search the repo).
- `DiffViewProvider` for accept/reject UI patterns.
- The eval harness concept (parse / apply / prompt tested separately).

### Roo Code (fork of Cline)
Roo Code is a Cline fork; its diff-edit machinery is the same `replace_in_file`
+ diff view, with additional modes (Architect/Code/Ask). For Phase 52, treat
Roo Code as Cline+ and reuse the same findings.

### Serena (`oraios/serena`) — symbol-level editing via MCP/LSP
Different paradigm: Serena is an **MCP toolkit** that gives the agent
IDE-grade tools via a Language Server Protocol backend.

- Edits happen at the **symbol level** (functions, classes, methods), not via
  text/regex matching — the LSP resolves the symbol's precise range, so the
  edit is applied at the correct location regardless of how the model phrased
  the surrounding text.
- Tools include find-references, go-to-definition, safe rename, and inline
  symbol replacement — all exposed over MCP so any agent can call them.
- Cross-language: works with any language that has an LSP server.

Codinal implications:
- For Phase 52, an LSP-backed "replace symbol" tool dramatically reduces
  failed applies versus pure text SEARCH/REPLACE, because the LSP owns the
  authoritative range. This pairs naturally with Aider's fuzzy ladder as a
  fallback when no LSP/symbol is available.
- Serena validates the "agent calls a structured edit tool" pattern (same shape
  as OpenHands `str_replace_editor`).

---

## Cross-cutting patterns Codinal should adopt

### Completion trigger (Phase 51)
1. Debounce **350 ms** (Continue default), using a request-ID supersede rather
   than trailing-edge debounce.
2. Abort in-flight requests on (a) new keystroke, (b) cursor move, (c) editor
   blur — wire the editor's cancellation token to an `AbortController`-equivalent
   that reaches all the way into the Python model call.
3. Build the FIM prompt with a token budget (Continue: `maxPromptTokens=1024`,
   prefix 30% / suffix 20%), priority-ranked so low-priority context is dropped
   first (Cursor/Priompt).
4. Stream the response; **paint partial ghost text at ~300 ms**
   (`showWhateverWeHaveAtXMs`) for perceived latency.
5. Cache completions by prefix in an LRU (Continue `AutocompleteLruCache`).
6. Temperature ≈ 0.01 for deterministic completions.

### Ghost text rendering (Phase 51, CM6)
- Three-layer pattern: fetch `ViewPlugin` → `StateField` with doc-snapshot
  stale-guard → render `ViewPlugin` using `Decoration.widget({ side: 1 })` +
  custom `WidgetType` at `selection.main.head`.
- Multi-line aware `lineBreaks` getter.
- High-precedence Tab keymap to accept; fall through (`return false`) when no
  suggestion.

### Inline edit / Cmd-K (Phase 52)
1. Use Aider's **SEARCH/REPLACE** format as the baseline diff contract.
2. Implement the full apply ladder: exact → whitespace-tolerant → `...`
   elision → edit-distance fuzzy → relative-indent rewrite (`RelativeIndenter`).
3. Add Cline's **order-invariant multi-diff apply** and consider
   **model-specific markers** if Codinal supports multiple backends.
4. Feed structured failures back to the model (Aider's
   `SearchReplaceNoExactMatch` message) for a self-correcting loop.
5. Render accept/reject via a CM6 diff decoration (`Decoration.mark` for
  added/removed) — mirror Cline's `DiffViewProvider` inline.
6. Where an LSP is available, prefer **symbol-level replacement** (Serena) and
   fall back to text SEARCH/REPLACE only when no symbol resolves.
7. For large rewrites, consider a "fast apply" path: treat the existing file as
   the speculated draft and only regenerate changed regions (Cursor Fast Apply
   idea) — even without a custom model, a diff-then-patch workflow gives most
   of the benefit.

### Cancellation contract (both phases)
- Single `AbortSignal` threaded editor → Rust → Python. Python checks
  `signal.aborted` between streamed chunks and after the stream completes
  (Continue pattern) before committing any state.

---

## Source index (primary)

- Continue: `github.com/continuedev/continue`
  - `core/autocomplete/CompletionProvider.ts`
  - `core/autocomplete/util/AutocompleteDebouncer.ts`
  - `core/util/parameters.ts` (`DEFAULT_AUTOCOMPLETE_OPTS`)
  - `extensions/vscode/src/autocomplete/completionProvider.ts`
  - `extensions/vscode/src/autocomplete/GhostTextAcceptanceTracker.ts`
- Aider: `github.com/Aider-AI/aider`
  - `aider/coders/editblock_coder.py`
  - `aider/coders/editblock_prompts.py`
  - `aider/coders/search_replace.py`
  - `tests/basic/test_editblock.py`
- OpenHands: `github.com/All-Hands-AI/OpenHands` — `str_replace_editor` tool,
  ACP IDE integration (`docs.openhands.dev`)
- CodeMirror 6: `codemirror.net/docs/ref/#autocomplete`;
  `github.com/saminzadeh/codemirror-extension-inline-suggestion`;
  `github.com/rizerphe/codemirror-companion-extension`
- Cline: `github.com/cline/cline` (`replace_in_file`, `DiffViewProvider`);
  `cline.bot/blog/improving-diff-edits-by-10`
- Serena: `github.com/oraios/serena`; `oraios.github.io/serena`

## Source index (secondary / reverse-engineered)
- "How Cursor Actually Works" — theaiengineer.substack.com
- "How Cursor built Fast Apply using Speculative Decoding" — fireworks.ai/blog/cursor
- Cursor Forum: Exploring the Implementation Principles of Cursor Tab
- ZenML LLMOps Database: real-time inference case study
