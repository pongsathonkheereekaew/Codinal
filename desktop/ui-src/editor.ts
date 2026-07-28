// Codinal multi-file code editor — Phase 49.
//
// CodeMirror 6 with tab strip, syntax highlighting (8 languages), dirty-state
// tracking, and a save callback bridge. The editor is bundled by esbuild
// into dist/editor.js and loaded as window.CodinalEditor by the vanilla JS
// in startup.js — same bridge pattern as xterm.js.
//
// The vanilla JS side owns the DOM host elements (#editor-strip + #editor-pane)
// and calls: openTab, closeTab, setActive, getContent, onSave.

import { EditorState } from "@codemirror/state";
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { syntaxHighlighting, defaultHighlightStyle, bracketMatching, foldGutter, indentOnInput } from "@codemirror/language";
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { rust } from "@codemirror/lang-rust";
import { json } from "@codemirror/lang-json";
import { markdown } from "@codemirror/lang-markdown";
import { css } from "@codemirror/lang-css";
import { html } from "@codemirror/lang-html";
import { oneDark } from "@codemirror/theme-one-dark";
import { linter, lintGutter, Diagnostic } from "@codemirror/lint";
import { completionExtension, clearCompletion } from "./completion";
import { inlineEditExtension, applyReplacement, dismissEditBar, setEditHandler } from "./inline-edit";

// --- Types ---

interface OpenTab {
  path: string;
  view: EditorView;
  dirty: boolean;
  readOnly: boolean;
  /** LSP diagnostics for this file, keyed by a version counter to avoid
   * re-rendering identical diagnostics. */
  diagnostics: Diagnostic[];
  diagVersion: number;
}

type SaveHandler = (path: string, content: string) => Promise<void>;
type GotoDefHandler = (path: string, line: number, col: number) => void;
type EmptyHandler = () => void;

interface CodinalEditorAPI {
  hello(): string;
  mount(stripHost: HTMLElement, paneHost: HTMLElement): void;
  openTab(path: string, content: string, opts?: { readOnly?: boolean }): void;
  closeTab(path: string): void;
  setActive(path: string): void;
  getContent(path: string): string | null;
  hasTab(path: string): boolean;
  onSave(handler: SaveHandler): void;
  /** Fired when the last tab closes, so the host can hide the panel. */
  onEmpty(handler: EmptyHandler): void;
  setTheme(theme: "light" | "dark"): void;
  dispose(): void;
  /** Phase 50: push LSP diagnostics for a file (from lsp-notification events). */
  setDiagnostics(path: string, diagnostics: Diagnostic[]): void;
  /** Phase 50: register goto-definition handler (opens target file). */
  onGotoDef(handler: GotoDefHandler): void;
  /** Phase 50: trigger a hover request at the current cursor position.
   * Returns the LSP hover text, or null. */
  requestHover(path: string): Promise<string | null>;
  /** Phase 51: register the inline completion fetcher (ghost text). */
  onComplete(fetcher: (doc: string, pos: number) => Promise<string | null>): void;
  /** Phase 52: register the inline edit handler (Cmd-K on selection). */
  onInlineEdit(handler: (text: string, instruction: string, from: number, to: number) => Promise<string | null>): void;
  /** Phase 52: apply a replacement to the active tab. */
  applyEdit(path: string, from: number, to: number, replacement: string): void;
}

// --- State ---

let _stripHost: HTMLElement | null = null;
let _paneHost: HTMLElement | null = null;
let _tabs: Map<string, OpenTab> = new Map();
let _activePath: string | null = null;
let _saveHandler: SaveHandler | null = null;
let _emptyHandler: EmptyHandler | null = null;
let _gotoDefHandler: GotoDefHandler | null = null;
let _completionFetcher: ((doc: string, pos: number) => Promise<string | null>) | null = null;
let _theme: "light" | "dark" = "light";

const MAX_EDITABLE_BYTES = 2 * 1024 * 1024; // 2MB — larger opens read-only

// --- Language detection ---

function languageExtension(path: string) {
  const ext = path.split(".").pop()?.toLowerCase() || "";
  switch (ext) {
    case "js":
    case "mjs":
    case "cjs":
    case "jsx":
      return javascript({ jsx: true });
    case "ts":
    case "tsx":
      return javascript({ typescript: true, jsx: true });
    case "py":
      return python();
    case "rs":
      return rust();
    case "json":
      return json();
    case "md":
    case "markdown":
      return markdown();
    case "css":
    case "scss":
      return css();
    case "html":
    case "htm":
    case "xml":
      return html();
    default:
      return [];
  }
}

// --- Tab strip rendering ---

function basename(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

function renderStrip(): void {
  if (!_stripHost) return;
  _stripHost.replaceChildren();
  for (const [path, tab] of _tabs) {
    const el = document.createElement("div");
    el.className = "editor-tab" + (path === _activePath ? " is-active" : "");
    el.dataset.path = path;
    const label = document.createElement("span");
    label.className = "editor-tab-label";
    label.textContent = basename(path);
    if (tab.dirty) {
      const dot = document.createElement("span");
      dot.className = "editor-tab-dirty";
      dot.textContent = "●";
      el.appendChild(dot);
    }
    el.appendChild(label);
    if (tab.readOnly) {
      const ro = document.createElement("span");
      ro.className = "editor-tab-ro";
      ro.textContent = "RO";
      el.appendChild(ro);
    }
    const close = document.createElement("button");
    close.className = "editor-tab-close";
    close.textContent = "×";
    close.setAttribute("aria-label", `Close ${basename(path)}`);
    close.addEventListener("click", (e) => {
      e.stopPropagation();
      api.closeTab(path);
    });
    el.appendChild(close);
    el.addEventListener("click", () => api.setActive(path));
    _stripHost.appendChild(el);
  }
}

function showActiveView(): void {
  if (!_paneHost || !_activePath) return;
  // Hide all views, show only the active one.
  for (const [path, tab] of _tabs) {
    tab.view.dom.style.display = path === _activePath ? "" : "none";
  }
}

// --- Editor creation ---

function createView(path: string, content: string, readOnly: boolean): EditorView {
  const isDark = _theme === "dark";
  const extensions = [
    history(),
    lineNumbers(),
    foldGutter(),
    highlightActiveLine(),
    highlightActiveLineGutter(),
    indentOnInput(),
    bracketMatching(),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    keymap.of([
      ...defaultKeymap,
      ...historyKeymap,
      indentWithTab,
      {
        key: "Mod-s",
        preventDefault: true,
        run: (view) => {
          handleSave();
          return true;
        },
      },
    ]),
    EditorView.lineWrapping,
    EditorState.readOnly.of(readOnly),
    lintGutter(),
    // LSP diagnostic linter: returns diagnostics stored per-tab via setDiagnostics.
    linter(async (view) => {
      const tab = Array.from(_tabs.values()).find((t) => t.view === view);
      return tab ? tab.diagnostics : [];
    }),
    EditorView.theme({
      "&": {
        height: "100%",
        fontSize: "13px",
      },
      ".cm-scroller": {
        fontFamily: "var(--mono, ui-monospace, Menlo, monospace)",
        overflow: "auto",
      },
      ".cm-content": { padding: "8px 0" },
      ".cm-gutters": {
        backgroundColor: "transparent",
        borderRight: "1px solid var(--line, #dee2e6)",
      },
    }),
    languageExtension(path),
    // Phase 52: inline edit (Cmd-K) — always active; shows on selection + Cmd-K.
    ...inlineEditExtension(),
    // Phase 51: inline completion (ghost text). Only active if a fetcher is set.
    ...(_completionFetcher
      ? completionExtension(_completionFetcher)
      : []),
    ...(isDark ? [oneDark] : []),
    EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        const tab = _tabs.get(path);
        if (tab && !tab.dirty) {
          tab.dirty = true;
          renderStrip();
        }
      }
    }),
  ];

  const state = EditorState.create({
    doc: content,
    extensions,
  });

  const view = new EditorView({
    state,
    parent: _paneHost || undefined,
  });

  return view;
}

async function handleSave(): Promise<void> {
  if (!_activePath || !_saveHandler) return;
  const tab = _tabs.get(_activePath);
  if (!tab || tab.readOnly) return;
  try {
    await _saveHandler(_activePath, tab.view.state.doc.toString());
    tab.dirty = false;
    renderStrip();
  } catch (err) {
    console.error("[CodinalEditor] save failed:", err);
  }
}

// --- Public API ---

const api: CodinalEditorAPI = {
  hello: () => "ok",

  mount(stripHost: HTMLElement, paneHost: HTMLElement): void {
    _stripHost = stripHost;
    _paneHost = paneHost;
    _paneHost.classList.add("editor-pane");
    _stripHost.classList.add("editor-strip");
  },

  openTab(path: string, content: string, opts?: { readOnly?: boolean }): void {
    // If already open, just focus.
    if (_tabs.has(path)) {
      api.setActive(path);
      return;
    }
    // Remove the empty-state placeholder (if present) before mounting the view.
    _paneHost?.querySelector(".editor-empty")?.remove();
    const bytes = new Blob([content]).size;
    const forceReadOnly = opts?.readOnly || bytes > MAX_EDITABLE_BYTES;
    const view = createView(path, content, forceReadOnly);
    _tabs.set(path, { path, view, dirty: false, readOnly: forceReadOnly, diagnostics: [], diagVersion: 0 });
    api.setActive(path);
    renderStrip();
    showActiveView();
  },

  closeTab(path: string): void {
    const tab = _tabs.get(path);
    if (!tab) return;
    tab.view.destroy();
    _tabs.delete(path);
    if (_activePath === path) {
      const next = _tabs.keys().next();
      _activePath = next.done ? null : next.value;
      showActiveView();
    }
    renderStrip();
    if (_tabs.size === 0) {
      try { _emptyHandler?.(); } catch { /* host error is non-fatal */ }
    }
  },

  setActive(path: string): void {
    if (!_tabs.has(path)) return;
    _activePath = path;
    showActiveView();
    renderStrip();
    // Focus the editor so typing works immediately.
    _tabs.get(path)?.view.focus();
  },

  getContent(path: string): string | null {
    const tab = _tabs.get(path);
    return tab ? tab.view.state.doc.toString() : null;
  },

  hasTab(path: string): boolean {
    return _tabs.has(path);
  },

  onSave(handler: SaveHandler): void {
    _saveHandler = handler;
  },

  onEmpty(handler: EmptyHandler): void {
    _emptyHandler = handler;
  },

  setTheme(theme: "light" | "dark"): void {
    // Theme changes require recreating views (CM6 theme is an extension).
    // For Phase 49 we store the preference; a full theme-swap re-init
    // is deferred to avoid losing undo history on toggle.
    _theme = theme;
  },

  dispose(): void {
    for (const [, tab] of _tabs) {
      tab.view.destroy();
    }
    _tabs.clear();
    _activePath = null;
    if (_stripHost) _stripHost.replaceChildren();
  },

  setDiagnostics(path: string, diagnostics: Diagnostic[]): void {
    const tab = _tabs.get(path);
    if (!tab) return;
    tab.diagnostics = diagnostics;
    tab.diagVersion++;
    // Force CM6 to re-run the liter by dispatching a no-op update.
    tab.view.dispatch({});
  },

  onGotoDef(handler: GotoDefHandler): void {
    _gotoDefHandler = handler;
  },

  async requestHover(path: string): Promise<string | null> {
    // Placeholder — actual hover is dispatched by startup.js via lsp_request.
    // The editor just provides the cursor position; the JS layer calls
    // invoke("lsp_request", ...) and shows a tooltip.
    return null;
  },

  onComplete(fetcher: (doc: string, pos: number) => Promise<string | null>): void {
    _completionFetcher = fetcher;
    // Note: existing views won't get the completion extension until re-created.
    // For Phase 51 this means completion activates on the next file open after
    // onComplete is registered. A full re-init of all views is deferred.
  },

  onInlineEdit(handler: (text: string, instruction: string, from: number, to: number) => Promise<string | null>): void {
    setEditHandler(handler);
  },

  applyEdit(path: string, from: number, to: number, replacement: string): void {
    const tab = _tabs.get(path);
    if (!tab) return;
    applyReplacement(tab.view, from, to, replacement);
  },
};

// Expose the bridge globally (same pattern as xterm.js).
(window as any).CodinalEditor = api;

export default api;
