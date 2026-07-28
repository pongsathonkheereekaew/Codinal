// Inline ghost-text completion — Phase 51.
//
// Based on the Continue/dev pattern (research: oss-completion-inline-edit-survey.md):
// - 350ms debounce after last keystroke
// - Request-ID supersede: a new keystroke cancels the previous pending request
// - Ghost text rendered via CM6 Decoration.widget({side: 1}) + custom WidgetType
// - Tab to accept (inserts the suggestion), Esc to dismiss
//
// The actual model call is delegated to the vanilla JS layer via a callback
// (window.CodinalEditor.onComplete) so routing/failover/providers are handled
// by the existing Python runtime, not the editor bundle.

import {
  ViewPlugin,
  Decoration,
  WidgetType,
  EditorView,
} from "@codemirror/view";
import { StateField, StateEffect } from "@codemirror/state";
import type { Extension } from "@codemirror/state";

// --- Ghost text widget ---

class GhostTextWidget extends WidgetType {
  constructor(readonly text: string) {
    super();
  }
  toDOM() {
    const span = document.createElement("span");
    span.className = "cm-ghost-text";
    span.textContent = this.text;
    span.style.color = "var(--faint, #999)";
    span.style.opacity = "0.6";
    span.style.fontStyle = "italic";
    span.style.whiteSpace = "pre-wrap";
    return span;
  }
  ignoreEvent() {
    return true;
  }
}

// --- State ---

const setGhostText = StateEffect.define<{ pos: number; text: string } | null>();

interface GhostState {
  pos: number;
  text: string;
}

const ghostField = StateField.define<GhostState | null>({
  create() {
    return null;
  },
  update(value, tr) {
    // Clear on any doc change (the user typed → old suggestion is stale).
    if (tr.docChanged) return null;
    // Clear on selection change (cursor moved).
    if (tr.selection) return null;
    for (const effect of tr.effects) {
      if (effect.is(setGhostText)) {
        return effect.value;
      }
    }
    return value;
  },
  provide(field) {
    return EditorView.decorations.from(field, (ghost) => {
      if (!ghost) return Decoration.none;
      return Decoration.set([
        Decoration.widget({
          pos: ghost.pos,
          side: 1,
          widget: new GhostTextWidget(ghost.text),
        }),
      ]);
    });
  },
});

// --- Completion trigger ---

const DEBOUNCE_MS = 350;

type CompletionFetcher = (
  doc: string,
  pos: number
) => Promise<string | null>;

let _fetcher: CompletionFetcher | null = null;
let _debounceTimer: ReturnType<typeof setTimeout> | null = null;
let _currentRequestId = 0;

function scheduleCompletion(view: EditorView) {
  if (!_fetcher) return;
  if (_debounceTimer) clearTimeout(_debounceTimer);
  _debounceTimer = setTimeout(async () => {
    const requestId = ++_currentRequestId;
    const pos = view.state.selection.main.head;
    const doc = view.state.doc.toString();
    try {
      const suggestion = await _fetcher(doc, pos);
      // Supersede check: if a newer request started, discard this result.
      if (requestId !== _currentRequestId) return;
      if (suggestion && suggestion.trim()) {
        view.dispatch({
          effects: setGhostText.of({ pos, text: suggestion }),
        });
      } else {
        view.dispatch({ effects: setGhostText.of(null) });
      }
    } catch {
      // Silent — completion failures shouldn't disrupt editing.
      view.dispatch({ effects: setGhostText.of(null) });
    }
  }, DEBOUNCE_MS);
}

// Plugin that triggers completion on doc changes.
const completionPlugin = ViewPlugin.fromClass(
  class {
    update(update: any) {
      if (update.docChanged) {
        scheduleCompletion(update.view);
      }
    }
  }
);

// Keybindings: Tab to accept, Esc to dismiss.
function completionKeymap(): Extension {
  return EditorView.domEventHandlers({
    keydown(event: KeyboardEvent, view: EditorView) {
      const ghost = view.state.field(ghostField, false);
      if (!ghost) return false;
      if (event.key === "Tab") {
        event.preventDefault();
        // Insert the ghost text at the cursor.
        view.dispatch(view.state.replaceSelection(ghost.text));
        view.dispatch({ effects: setGhostText.of(null) });
        return true;
      }
      if (event.key === "Escape") {
        view.dispatch({ effects: setGhostText.of(null) });
        return true;
      }
      return false;
    },
  });
}

// --- Public extension ---

/** Create the completion extension bundle for a CM6 editor.
 * Pass a fetcher that returns a suggestion string (or null for no suggestion).
 */
export function completionExtension(fetcher: CompletionFetcher): Extension[] {
  _fetcher = fetcher;
  return [ghostField, completionPlugin, completionKeymap()];
}

/** Clear any visible ghost text (called on tab switch, save, etc.). */
export function clearCompletion(view: EditorView) {
  view.dispatch({ effects: setGhostText.of(null) });
}
