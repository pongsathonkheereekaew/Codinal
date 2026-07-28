// Inline edit / Cmd-K — Phase 52.
//
// Highlight code → Cmd-K → type instruction → AI replaces it.
// Based on Aider's SEARCH/REPLACE pattern + Codinal's existing diff review
// (Phase 33/43 selective apply). The model call is delegated to the vanilla
// JS layer via a callback (same pattern as completion).

import { EditorView, Decoration } from "@codemirror/view";
import { StateField, StateEffect } from "@codemirror/state";
import type { Extension } from "@codemirror/state";

// --- Inline edit UI state ---

const showEditBar = StateEffect.define<{ from: number; to: number }>();
const hideEditBar = StateEffect.define<null>();

interface EditBarState {
  active: boolean;
  from: number;
  to: number;
}

const editBarField = StateField.define<EditBarState>({
  create() {
    return { active: false, from: 0, to: 0 };
  },
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(showEditBar)) {
        return { active: true, ...effect.value };
      }
      if (effect.is(hideEditBar)) {
        return { active: false, from: 0, to: 0 };
      }
    }
    // Dismiss on selection change or doc change.
    if (tr.docChanged || tr.selection) {
      return { active: false, from: 0, to: 0 };
    }
    return value;
  },
  provide(field) {
    return EditorView.decorations.from(field, (state) => {
      if (!state.active) return Decoration.none;
      return Decoration.set([
        Decoration.mark({
          from: state.from,
          to: state.to,
          attributes: { class: "cm-inline-edit-highlight" },
        }),
      ]);
    });
  },
});

// --- Keybinding ---

type EditHandler = (
  selectedText: string,
  instruction: string,
  from: number,
  to: number
) => Promise<string | null>;

let _editHandler: EditHandler | null = null;

/** Trigger Cmd-K: if there's a selection, show the edit bar.
 * The vanilla JS layer handles the instruction input UI (a prompt or floating
 * input near the selection). The handler returns the replacement text.
 */
function handleCmdK(view: EditorView) {
  const sel = view.state.selection.main;
  if (sel.from === sel.to) return false; // no selection — no-op
  view.dispatch({
    effects: showEditBar.of({ from: sel.from, to: sel.to }),
  });
  // The actual instruction prompt + model call is handled by startup.js
  // via window.CodinalEditor.requestInlineEdit(path, instruction).
  return true;
}

/** Apply the AI-generated replacement to the document. */
export function applyReplacement(
  view: EditorView,
  from: number,
  to: number,
  replacement: string
) {
  view.dispatch({
    changes: { from, to, insert: replacement },
    effects: hideEditBar.of(null),
  });
  view.focus();
}

/** Dismiss the edit bar without applying. */
export function dismissEditBar(view: EditorView) {
  view.dispatch({ effects: hideEditBar.of(null) });
}

/** Create the inline edit extension bundle. */
export function inlineEditExtension(): Extension[] {
  return [
    editBarField,
    EditorView.domEventHandlers({
      keydown(event: KeyboardEvent, view: EditorView) {
        // Cmd+K / Ctrl+K triggers inline edit.
        if ((event.metaKey || event.ctrlKey) && event.key === "k") {
          event.preventDefault();
          return handleCmdK(view);
        }
        return false;
      },
    }),
  ];
}

/** Register the edit handler (called by startup.js). */
export function setEditHandler(handler: EditHandler) {
  _editHandler = handler;
}

export { _editHandler };
