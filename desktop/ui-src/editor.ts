// Codinal editor surface — Phase 48 build-infrastructure spike.
//
// This file proves the esbuild → dist/editor.js → <script src> →
// window.CodinalEditor bridge works under Tauri's CSP before any real
// editor code lands (Phase 49). The global is the same bridge pattern
// xterm.js uses: vanilla JS in startup.js calls into it.
//
// Phase 49 will replace this stub with a real CodeMirror 6 multi-file editor.

interface CodinalEditor {
  /** Phase 48 health check. Returns "ok" once the bundled module loaded. */
  hello(): string;
  /** Phase 49+ will add openTab / closeTab / setActive / getContent / onSave. */
}

declare global {
  interface Window {
    CodinalEditor: CodinalEditor;
  }
}

// esbuild's `globalName: "CodinalEditor"` + `format: "iife"` assigns the
// module's default export to window.CodinalEditor. We also set it explicitly
// so the bridge works regardless of how the script is loaded.
const api: CodinalEditor = {
  hello: () => "ok",
};

window.CodinalEditor = api;

export default api;
