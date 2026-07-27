# Phase 35 evidence — dev-server preview + console evidence + element annotation

Date: 2026-07-27
P1 roadmap item: "Add browser/dev-server preview, screenshots, console/network evidence, and element/area annotation." (URL detection + iframe preview + console evidence + annotation done; native screenshot capture + automatic network capture deferred.)

## What shipped

- **Dev-server URL detection** (`runtime/preview/detector.py`): scans terminal stdout/stderr for `http://localhost:PORT` / `http://127.0.0.1:PORT`; de-duplicated, bounded. The terminal route response is enriched with `devserver_urls`.
- **Preview evidence store** (`runtime/preview/evidence.py`): SQLite (`preview.db`, schema v1) storing console-evidence + annotation entries per session. Same migration/backup/corrupt-recovery primitives.
- **Routes**: `POST /v1/sessions/{id}/preview/evidence` (add), `GET .../preview/evidence` (list), `DELETE .../preview/evidence` (clear). Terminal `POST .../terminal/run` response now carries `devserver_urls`.
- **CSP**: `frame-src http://127.0.0.1:* http://localhost:*` added so localhost dev servers render in an iframe.
- **Desktop UI**:
  - Preview panel (`#preview-panel`): URL input + Open + Annotate + Attach console buttons; detected-URL chips; sandboxed `<iframe>`; annotation overlay.
  - `renderDevserverChips`, `openPreview`, `loadPreviewEvidence`, `attachConsoleEvidence`, `toggleAnnotation`, `startAnnotationOverlay` (pointer-draw rectangle + note prompt → saves to evidence store).

## Verification (fresh, 2026-07-27)

```
$ ./.venv/bin/pytest -q tests/preview/
.............                                                            [100%]
13 passed
```

```
$ ./.venv/bin/pytest -q tests/control_plane/test_session_routes.py -k preview
...                                                                      [100%]
3 passed
```

```
$ ./.venv/bin/pytest -q tests/desktop_ui/test_ui_contract.py
.....                                                                     [100%]
5 passed
```

Full local suite:

```
$ CI= ./.venv/bin/pytest -q
831 passed, 1 skipped, 53 warnings in 77.88s
```

`verify.sh`: PASS.

## Non-goals (deferred)

- Native screenshot capture (needs platform APIs / `tauri-plugin-screenshot`).
- Automatic console/network capture from the iframe (cross-origin; needs second Tauri webview + JS injection).
- Dev-server lifecycle management (background-process model).
