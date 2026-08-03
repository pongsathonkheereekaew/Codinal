---
stage: C3
owner: desktop/gpui
status: pending
fixture: native GPUI workbench; local unit contracts plus macOS observation
---

# C3 accessibility and interaction matrix

This matrix distinguishes executable local contracts from live macOS evidence.
A static assertion or accessibility-tree observation does not stand in for a
VoiceOver announcement/focus traversal or target-hardware performance run.

| Surface | Local evidence | Result | Remaining evidence |
|---|---|---|---|
| Keyboard-only safety actions | `safety_controls_accept_only_keyboard_activation_keys`; keyboard-operable approval/diff controls in the local UI observation | passed locally | fresh end-to-end traversal record |
| VoiceOver labels and announcements | GPUI labels/ARIA descriptions are present in the renderer and safety projections | pending | fresh VoiceOver session with announcements recorded |
| Focus restoration | `changing_side_tools_requires_a_stable_focus_handoff`; approval identity/focus contract tests | passed locally | fresh manual focus traversal and restoration record |
| Contrast | `light_text_contrast_meets_accessibility_floor` | passed statically | target-theme visual review |
| Light/Dark state | `WorkbenchState` appearance projection and semantic token tests | passed as contract | fresh live Light/Dark visual matrix |
| Reduced motion | `scroll_anchor_and_reduced_motion_are_explicit_state` | passed as contract | live reduced-motion interaction record |
| Reconnect and receipt reload | `readiness_loss_reconnects_and_cannot_be_restarted_locally`; session replay/receipt tests | passed locally | fresh packaged-app reconnect observation |
| Transcript scale/scrolling | bounded transcript and scroll-anchor tests | passed as bounded contract | target-hardware usability and latency run |
| Typing/input-to-paint | no numeric target-hardware sample | pending | P95 input-to-paint and typing sample |
| Frame time/idle wakeups/RSS | no target-hardware telemetry | pending | 60/120 Hz frame, idle-wakeup, and RSS trace |

The current Apple M3 MacBook Air host exposed no 120 Hz display mode. No fresh
VoiceOver or target-120-Hz result is claimed. See
[`measurement-ticket.md`](measurement-ticket.md) for frozen numeric budgets.

Implementation refresh (2026-08-03): the signed candidate adds visible
keyboard-focus styling to the previously unstyled reachable controls and
exposes the composer as an AX `TextInput` labeled `Composer input`. Computer
Use now lists that text field, but still reports only the window as focused
after Tab/click checks; VoiceOver traversal/announcements therefore remain
pending.

Latest control-surface refresh (2026-08-03): updater actions, provider
credential/edit/delete actions, capability probing, workspace-tool tabs, file
rows, and the workspace-tool add control now expose button semantics/labels,
tab stops where applicable, and visible keyboard-focus styling. The fresh AX
tree lists these controls and `Composer input` as a text field. The bridge
still cannot report focused-child traversal after Tab/click checks, so this is
implementation and AX-tree evidence only; formal VoiceOver evidence remains
pending.

Fresh current-worktree AX recheck (2026-08-03): after six unmodified `Tab`
presses, the Computer Use bridge still reported `0 standard window Codinal`
as the focused element. The same tree exposed `Composer input` as a text field
and the updater/provider controls as labeled buttons. This reproduces the
bridge limitation and does not promote the result to VoiceOver evidence.

Latest live keyboard recheck (2026-08-03): the signed candidate binds GPUI
`tab`/`shift-tab` actions globally. `Tab` then `Return` hid the navigation
sidebar in the installed app, and the sidebar was restored, proving keyboard
focus traversal/activation at the app behavior level. The AX bridge still
reported `0 standard window Codinal` as focused, so child focus and VoiceOver
announcements remain unverified. The current host's Keychain timeout is now
bounded; the UI visibly reports provider status unavailable and remains
read-only rather than asserting a configured provider.

Latest installed candidate recheck (2026-08-03): the corrected release was
rebuilt and installed. The AX tree still exposes labeled provider/updater
controls and `Composer input`; the live `Tab`+`Return` check hid navigation and
the sidebar was restored. The bridge still reports only the window as focused,
so formal VoiceOver traversal/announcements remain pending. The Keychain
timeout continues to render an explicit unavailable-provider state and keeps
the run control disabled.

Final installed-candidate recheck (2026-08-03): the current packaged app
exposed `Composer input`, labeled updater/provider controls, and the disabled
`Run turn` state. `Tab` followed by `Return` hid the navigation sidebar and the
sidebar was restored. The Computer Use bridge still reports only the window
as focused, so this remains app-behavior/AX-tree evidence rather than formal
VoiceOver evidence.

Fresh hardware recheck (2026-08-03): `system_profiler SPDisplaysDataType`
reports only the built-in Apple M3 Color LCD display; no external or 120-Hz
target display is connected. The formal VoiceOver and target-refresh/frame/
input/RSS rows therefore remain pending rather than being inferred from the
local AX tree or 60-Hz host.
