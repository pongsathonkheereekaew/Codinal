---
stage: C3
status: implementation-in-progress
date: 2026-08-03
owner: desktop/gpui
authority: user-supplied Codex screenshots, then official Codex documentation
---

# Codex surface parity review

This is the pre-implementation decision record and source audit for the
Codinal native GPUI surface. It records the UX decisions collected during the
grilling pass and separates them from behaviors that are actually present in
the current repository. It is not a claim of parity.

## Intent and authority

Goal: make the Codinal macOS desktop surface match the supplied Codex app
states and interaction anatomy while retaining Codinal branding, native Rust /
GPUI ownership, truthful capability boundaries, and the existing runtime,
approval, receipt, Keychain, and PTY boundaries.

Authority order:

1. The user-supplied screenshots are the visual golden reference for exact
   copy, geometry, state, and interaction evidence.
2. `desktop/gpui/UI_CONTRACT.md` and
   `pixel-parity-contract.md` are the local geometry, token, accessibility,
   and verification contracts.
3. `CONTEXT.md` is the local domain vocabulary for Project context, primary
   source root, Environment/workbench composition, and permission profile.
4. Official OpenAI/Codex documentation is the semantic reference for Projects,
   Chats, local folders, environments, Review, permissions, worktrees, files,
   and notifications.
5. `openai/codex` is the open-source CLI/runtime reference, not the source of
   the desktop UI. It can validate sandbox/config semantics but cannot prove
   desktop pixel geometry.
6. Existing code is evidence of current implementation, not evidence that a
   requested behavior is already complete.

## Locked UX decisions

### Identity, visual target, and responsive behavior

- Match Codex anatomy and interaction as closely as possible; retain Codinal
  name, logo, branding, provider boundary, and Rust/GPUI authority.
- Light mode is the first golden target. Dark mode is a later separate matrix.
- Use the Codex/reference English chrome copy (`New chat`, `Projects`,
  `Chats`, `Review`, `Terminal`, `Browser`, `Files`, `Do anything`, etc.).
  User-authored session content keeps its original language.
- Compare the app window only: include native traffic lights and app content;
  exclude the global macOS menu/status bar.
- Primary viewport is `1710 × 1112` logical px at `2×`; secondary responsive
  profile is `1280 × 720` logical px at `2×`.
- Sidebar and right-rail widths are user-resizable, constrained, persisted,
  and resettable by double-clicking the divider. Navigation default is the
  golden value; workbench uses its golden default and a safe min/max range.
- Narrow windows may collapse navigation, turn the workbench into a right
  overlay, and narrow/move Environment without overlap or clipping.
- Use native SF/system UI and SF Mono; use native SF Symbols where available,
  with custom vector fallback for Codinal-specific icons. Do not use Unicode
  glyphs as semantic icon substitutes.
- Respect system accent, Reduced Motion, Increased Contrast, Reduce
  Transparency, Larger Text, VoiceOver, and keyboard focus order.

### Sidebar, Chats, and Projects

- Sidebar order is `Pinned` → `Projects` → `Chats`. `Pinned` hides when empty;
  `Projects` and `Chats` retain truthful empty states.
- `Chats` replaces `Recents` and contains every session not assigned to a
  project. Project sessions are not duplicated in `Chats`.
- Chats sort by latest activity from non-archived chat messages/results.
  `Show more` expands the bounded initial list and preserves its state.
- A new session is created locally immediately, focuses the composer, and does
  not start a provider turn until Submit.
- Selecting a project chooses its context; its name opens project overview,
  its disclosure control expands sessions, and a session row opens that chat.
  `New chat` under a selected project creates a project chat; selecting
  `Chats` clears project context and makes the next chat unassigned.
- Project overview contains name, source folders, task count, sessions, and
  `New chat`; it never starts work automatically.
- `+` in Projects opens the `Create project` modal. Name is required; source
  folders are optional. No-root projects show `No source configured` and do
  not run until configured.
- Source folder selection is a native multi-select picker. Exact duplicates
  are removed; nested roots warn before save. Missing roots remain visible as
  `Folder unavailable`, disable Run, and offer reselect/Retry.
- Every non-empty project has exactly one `primary` source root. The first
  saved root becomes primary by default; each root exposes `Make primary` in
  the project editor. New project chats, Terminal cwd, Git/review scope, and
  `AGENTS.md`/skills/`config.toml` discovery default to that root. Secondary
  roots remain attached and selectable for multi-root work, but never silently
  replace the primary context. Removing the primary root requires selecting a
  replacement before Save; a zero-root project has no primary and shows
  `No source configured`.
- Hovering a project after a short delay shows its preview card (name, task
  count, roots, `Edit project`); entering the card keeps it open; pointer-out
  or Escape closes it without changing selection.
- Pinning moves a project into a separate `Pinned` section. Unpinning returns
  it to `Projects`, sorted by latest activity, without duplication.
- Project overflow actions are exactly: `Pin project`, `Reveal in Finder`,
  `Create permanent worktree`, `Edit project`, `Archive chats`, `Remove`.
  Unsupported actions remain visible but disabled with a truthful reason.
- `Edit project` matches the supplied modal: prefilled name, removable root
  rows, `Add folder`, red `Remove project`, `Cancel`, and `Save`.
- Removing a project requires confirmation, removes only project metadata,
  returns chats to `Chats`, leaves source folders/files untouched, clears active
  context, and offers a short-lived `Undo`.
- Archive is non-destructive. It confirms the chat count, archives all project
  chats atomically, keeps project/roots, removes chats from normal `Chats`,
  exposes `Archived` under `Chats`, and offers `Restore`/`Undo`.
- Session overflow actions are `Rename`, `Move to project`, `Archive chat`,
  and destructive `Delete`. Move is immediate with Undo; Remove from project
  returns the session to `Chats`; Delete removes session data only and never
  project/source files.

### Main conversation and composer

- Empty workspace has Codex starter cards. Clicking a card expands
  category-specific suggestions, fills the composer, and never auto-submits.
  Existing drafts are preserved and starter text is inserted at the cursor or
  appended.
- Conversation uses a centered max-width column; assistant content stays on
  the reading side, user messages use right-side bubbles, and composer aligns
  with the content column.
- Render Markdown, code blocks, source chips/footnotes, image/file previews,
  links, streaming partial output, receipts, branches, error recovery, and
  jump-to-latest behavior truthfully.
- Composer is sticky, auto-grows to a max height, scrolls internally after the
  max, and supports `Enter` send, `Shift+Enter` newline, `Esc` dismissal, and
  `⌘Enter` fallback.
- Composer footer follows Codex anatomy: `+`, access status, model/effort
  selector, mic, voice mode, and send/Stop/Retry state.
- Permission selector uses the reference options and copy: `Ask for
  approval`, `Approve for me`, `Full access`, `Custom (config.toml)`. New
  project/session defaults to Ask for approval; existing project/session mode
  persists. Elevation confirms scope and risk and syncs Composer/Environment.
- Model picker groups provider/model, effort levels are dynamic per model,
  unsupported effort is replaced by the new model default with a visible
  notice, and model/effort is locked while streaming.
- Mic creates a transcription draft with permission, waveform, Stop/Cancel,
  and no auto-send. Voice mode is separate and exposes listening/thinking/
  speaking/exit states.

### Environment, Sources, Workbench, and safety

- Environment uses Codex section anatomy: Changes, Local, branch, Commit or
  push, Compare branch, and Sources. Sections are independent accordions and
  persist state. The Environment card may remain co-visible with the
  Workbench; the Workbench owns one active detail tool at a time. Approval
  pending forces Environment visible and focus moves into it, then returns to
  the prior trigger/state.
- Sources is a secondary drawer at the far right of the supplied reference;
  it leaves Environment visible, shows filename/path and `Attached to
  conversation`, supports `+`, `View all`, `×`, preview, and source removal
  without deleting original files.
- Workbench tools are Review, Terminal, Browser, Files, with Side chat added
  from `+`/overflow. Tool order is stable; show/hide state persists.
- Review reflects actual Git state, supports multi-repository context and
  read-only branch comparison, and keeps line/file review within the app.
- Terminal is an inline real PTY with visible cwd, streaming output, history,
  copy/clear, receipt, and policy/approval boundary. Active project primary
  root is its default cwd.
- Browser is an in-app browser with address/search, back/forward/reload, and
  visible network/permission status; external browser is an explicit option.
- Files is an active-root file tree with multi-root switcher and main-pane
  preview/editor; unsupported previews show metadata and Reveal in Finder.
- Side chat is a persistent child conversation in the right rail, uses parent
  context, has a separate composer, and is not a top-level Chats/task count.
- Approval review is inline, full-diff/path/risk/expiry aware, sticky, focus
  trapped/restored, and blocks Run. No mutation occurs from a palette or
  disabled-looking control without the runtime approval boundary.

## Fixture manifest

All window fixtures are source screenshots supplied by the user. Their source
window includes the macOS menu/status bar; parity comparison must crop the app
window according to the contract. The permissions image is an intentional
overlay crop, not a full-window fixture.

| State | Fixture | Pixels | SHA-256 |
|---|---|---:|---|
| Primary chat + Environment | `golden/window/primary-chat-environment-1710x1112@2x.png` | 3420×2224 | `04d9ec2d8a97d6196f970ca0309306fc8a17c6f997076291ef50267fd936b694` |
| Empty workspace + Workbench | `golden/window/empty-workspace-workbench-1710x1112@2x.png` | 3420×2224 | `dfed1673b6052c6c8138848fa26320f669e7566062b4ef24546bfbde597dec94` |
| Starter build suggestions | `golden/window/starter-build-suggestions-1710x1112@2x.png` | 3420×2224 | `3bc89cb4d912294ae164d73385745030de6e13b7aa3aefda6a0f56a1b180b836` |
| Create project modal | `golden/window/create-project-modal-1710x1112@2x.png` | 3420×2224 | `e36b53da873fa8582b7238b7a54d5d25d6bea4f39a0f984fe2f8ee7cf26fadea` |
| Project hover preview | `golden/window/project-hover-preview-1280x720@2x.png` | 2560×1440 | `60baf62f5a85a9f16b2d6908312ec68c4a0721e9d80846467719b6251475658e` |
| Project overflow menu | `golden/window/project-overflow-menu-1280x720@2x.png` | 2560×1440 | `36a6f1fdf9738fc29dc43bbf150492b848d7215f12f850d724dad5cd8b8c4f74` |
| Edit project modal | `golden/window/edit-project-modal-1280x720@2x.png` | 2560×1440 | `a735d77841d53935f107f4c586dc9932001940e2d621b18af9d95cf91519d813` |
| Sources list + Environment | `golden/window/sources-list-environment-1280x720@2x.png` | 2560×1440 | `844a57dd5827bc9773a054d1049be11837f550ee067af5d5a118b8d5a7271115` |
| Sources drawer | `golden/window/sources-drawer-1280x720@2x.png` | 2560×1440 | `e2c03d1f185cd306564f374c9c23d3f93aa8b8223a999860fc489d434a9cc08f` |
| Permission selector | `golden/overlay/permissions-popover-844x311.png` | 844×311 | `47193892aedb056db559b60c3dd3f4d85b87344c157918a7cb916e613956aec0` |
| Side chat added | `golden/window/side-chat-workbench-1280x720@2x.png` | 2560×1440 | `63b3f7d9e8a0ec23612dd7ddf973a4e968a6232fdc5c739e9b2bd40033718ba1` |

## Official-source audit

| Source evidence | Implication for this surface | Current decision/status |
|---|---|---|
| OpenAI desktop overview: projects, local folders, parallel agents, worktrees, skills, automations, and secure-by-default behavior | Codex is a command center, not only a transcript shell | Anatomy is targeted; Skills/Automations/multi-agent surfaces must remain visible-but-disabled until Codinal has a truthful backend |
| Projects docs: project Chats/Sources, local projects, multiple attached folders, primary folder, `Make primary`, project archive | Project folder scope needs a primary root and project Chats/Sources model | Multi-root/Chats/archive/primary-root semantics are locked; implementation must persist the primary root and use it for default cwd/discovery |
| Environments docs: Local, Worktree, Cloud | Context must identify execution location, not only Local/branch | Local is in the target copy; Worktree/Cloud need visible truthful disabled states or later implementation |
| Worktrees docs: permanent worktree is a new persistent project and can host multiple chats | `Create permanent worktree` has a defined future behavior | Current plan keeps it disabled until Codinal runtime supports it; this is not parity with an enabled Codex capability |
| Sandbox/approvals docs: Ask for approval, Approve for me, Full access, custom profiles; modes map to sandbox + approval policy | Permission copy must map to real policy, not to `start_turn` readiness | Desired selector is locked; current GPUI only derives a label from capabilities |
| Code review docs: actual Git state, unstaged/staged/commit/branch/last turn, multi-repo selector, inline comments, stage/revert | Review is more than a status string and raw diff | Current Review is a bounded read-only partial implementation |
| Files docs: desktop previews documents/presentations/spreadsheets/PDF/HTML alongside chat | Files needs typed preview states and fallback metadata | Current Files only previews bounded UTF-8 text/binary metadata |
| Notifications docs: Activity shows unread/running/waiting and supports Mark all as read and a shortcut | Bell needs an activity model, not a decorative icon | Activity now has a typed runtime list/read projection; the unread marker is persisted in the Rust runtime store and resets when a new turn/approval arrives |
| `openai/codex` GitHub README/source | CLI/runtime semantics can inform sandbox/config; desktop UI is not in this repository | Use as runtime reference only; do not infer desktop geometry from it |

## Current code-path parity audit

Status meanings: `partial` means an isolated slice exists; `major gap` means
the requested surface/state is absent or materially different; `blocked` means
the visual claim cannot be proven because capture/backend evidence is absent.

| Surface | Current trace | Status |
|---|---|---|
| Shell geometry | `shell_layout.rs:8-21,96-169` has native panel constants, persisted resizable navigation/workbench/file-tree widths, and dock/overlay resolution | partial; structural contract exists, but navigation min and native golden capture still need review |
| Sidebar | `navigation.rs` renders the Codex-like primary surfaces, Pinned/Projects/Chats, project session lists, project create/edit/hover/overflow states, typed New chat, Search/Activity controls, and GPUI vector icon assets | partial; unsupported primary surfaces remain visible with truthful disabled reasons, while Search and Activity use authenticated runtime routes and native capture is pending |
| Session data | `control-plane-client/src/lib.rs` exposes project membership, archive/pin/rename/delete mutations and typed side-chat origin metadata | partial; the unread marker is durable, while activity still exposes only current running/waiting items rather than a richer remote history |
| Projects backend | runtime exposes v1 project CRUD, pin, membership, task counts, primary-root persistence, and project-chat archive | partial; permanent worktree and richer project actions remain disabled |
| Composer | `composer.rs` renders the Codex-like footer, access profile popover, typed model-profile picker, model/status labels, run/interrupt states, auto-grow, Enter/Shift+Enter behavior, and typed disabled reasons | partial; the picker is limited to the runtime's typed OpenCode/DeepSeek catalogue and mic/voice remain visibly unavailable |
| Environment/approval | `context_panel.rs` renders Changes/Local/runtime/branch/commit/compare/source anatomy with truthful disabled states; approval remains capability-gated | partial; Git projection is bounded read-only, while source attachments now support attach/list/retry/remove/preview and exact empty-workspace capture remains |
| Workbench tabs | `side_panel.rs:14-104` defines Review/Terminal/Browser/Files/SideChat; `dock.rs` persists tabs per session | partial; empty runtime and project overview open the native tool picker, while richer reference actions remain capability-gated |
| Review | `side_panel.rs:118-405` reads bounded status/unstaged/staged diff and extracts changed paths; `dock_view.rs:164-330` renders branch/status/scope/files/raw diff and read-only action boundaries | partial; multi-repo, inline comments, file/hunk mutations, and reference layout still require runtime routes |
| Terminal | `terminal_view.rs` owns a native PTY projection and cwd label | partial; useful runtime path exists, but composer/policy/cwd picker/receipt anatomy is not Codex parity |
| Browser | `dock_view.rs` explicitly labels the native system-browser fallback and keeps embedded WebView disabled | partial/disabled; in-app Browser still needs a safe native implementation |
| Files | `side_panel.rs:153-239` and `dock_view.rs:303-466` inspect the selected project root with a root switcher, bounded text/binary preview, and `Reveal in Finder` | partial; no typed document/image viewer |
| Side chat | `dock_view.rs` renders a parent-scoped child tree and parent action; storage/runtime persist `origin=side_chat`, and navigation excludes it from Pinned/Chats | partial; dedicated side-chat navigation now exists, while richer child transcript/remote activity remains bounded to the normal session projection |
| Permission/model | runtime health exposes typed provider/model/effort profiles with configured/probe/ready state; GPUI renders a selectable model-profile menu and sends the selected profile with each session/turn | partial; the catalogue is intentionally bounded to bundled provider profiles and does not yet expose arbitrary authenticated catalogue administration |
| Sources/attachments/notifications/search | Sources has typed attach/list/retry/remove/preview lifecycle and a secondary drawer; Search is a native GPUI palette backed by the runtime search route; Activity has unread/running/waiting items and Mark all as read | partial; Activity history is limited to current running/waiting items and rich attachment viewers remain bounded metadata/text |
| Session actions | Header overflow exposes rename, pin/unpin, move to project, remove from project, archive, and delete with confirmation; project overflow confirms chat count before archive and removes projects safely | partial; permanent worktree and cloud/remote actions remain visibly unavailable |
| Pixel proof | `scripts/verify-gpui-pixel-parity.py` compares dimensions/diff/overlay; `scripts/capture-gpui-pixel-parity.py` launches an isolated native GPUI fixture, waits for a window, focuses it, settles, captures, and cleans up the exact process group | blocked for exact parity; the latest post-change seeded `1280×720@2×` capture is 2560×1440 but fails visual diff (`MAE 0.023809`, `>16/255 13.0402%`); the primary golden still requires a 3420×2224 reference display and app-window crop |

## Rust+GPUI implementation target

The implementation must be native Rust/GPUI and projection-driven. Do not add a
visual-only mock layer or infer durable state from labels.

- Rust domain/control-plane projections: `ProjectRecord` (roots plus exactly
  one primary root), `SessionSummary` (project/archive/pin/activity/branch),
  `SourceAttachment`, `PermissionProfile`, `EnvironmentProjection`, and
  `ActivityItem`. Storage and API mutations must be atomic and return typed
  receipts/errors.
- GPUI shell projections: Sidebar (`Pinned`/`Projects`/`Chats`), project
  overview/modals, Composer, Environment/Sources, and Workbench consume those
  projections and expose disabled states only when the runtime reports the
  capability as unavailable.
- Primary-root routing: all default cwd/Git/review/discovery operations take
  the persisted primary root; explicit secondary-root selection is visible in
  the UI and included in the request scope.
- Platform surfaces stay native: macOS traffic lights/SF Symbols, native
  multi-select file picker, Keychain/permission bridge, and PTY. The Browser
  tab keeps the target in-app anatomy but remains disabled with a truthful
  reason until an approved native platform bridge exists; the current external
  `System browser` action is not relabeled as parity and no WebView is used as
  the application shell.
- Verification is a separate deterministic GPUI capture/diff harness. It
  seeds local projections, freezes unstable time/provider data, waits for
  layout/animation idle, captures at both golden profiles, and emits actual,
  diff, overlay, metrics, and bounds without overwriting goldens.

## Native macOS + GPUI preflight

The target is a native Mac application, not a web layout rendered inside a
window. The supplied screenshot remains the pixel authority when a generic
macOS guideline conflicts with it.

| Native concern | Required behavior | Rust/GPUI rule | Proof before parity claim |
|---|---|---|---|
| Window chrome | Traffic lights, title/drag zone, app header, and resize edges remain native and uncluttered | Use native window/titlebar integration; do not fake traffic lights with content glyphs | 2× crop includes traffic lights and records app-window bounds |
| Sidebar and rails | Sidebar is collapsible/resizable; Environment and Workbench preserve context; narrow windows avoid overlap | Keep persisted width preferences separate from responsive clamps; compose Environment as a floating context card | Primary and narrow geometry fixtures plus resize/focus tests |
| Popovers and modals | Anchored access/source/project/confirmation/command surfaces dismiss with Escape and restore focus | Use GPUI focus scopes, modal backdrop, dirty-state guard, and trigger identity; no toast-only mutation | Keyboard/focus matrix and modal screenshots |
| Keyboard | Standard shortcuts, visible hints, IME-safe text entry, Enter/Shift+Enter, Escape, and command search | Route shortcuts through typed actions; do not consume text/IME events in the shell | Unit routing tests plus manual keyboard/VoiceOver pass |
| Files and drag/drop | Native file/folder picker, Finder drop-in, source preview, Reveal in Finder, safe remove | Keep project roots and conversation attachments distinct; scope every path through runtime policy | Picker/drop fixture, path-boundary tests, receipt/error states |
| Motion and preferences | 150–250 ms transitions, Reduced Motion, contrast/transparency/larger text, persisted panel state | Store semantic state, derive animation from preference, and never persist a narrow-window clamp | Reduced-motion/appearance matrix and live macOS capture |
| Iconography and type | SF Symbols/system UI/SF Mono, stable roles, no Unicode semantic substitutes | Keep accessibility labels separate from icon assets and use native icon components | Token/typography checks and VoiceOver labels |
| Browser capability | Browser tab anatomy exists; unsupported in-app engine is visibly disabled and explained | Do not relabel the current external `System browser`; native bridge is a separate capability | Capability snapshot and disabled-state fixture |

## Pre-implementation surface matrix

Every visible surface must have a typed projection, a GPUI owner, a runtime or
platform boundary, and a fixture/state proof. A row without all four is not
ready for feature implementation.

| Surface | Typed projection | GPUI owner | Runtime/platform boundary | First proof |
|---|---|---|---|---|
| Window/sidebar chrome | `ShellProjection`, `PanelWidthPreference` | `shell.rs`, `shell_layout.rs`, `navigation.rs` | Native window + local preference store | Primary and narrow geometry fixtures |
| Projects/Chats | `ProjectRecord`, `SessionSummary`, `ActivityItem` | Sidebar, project overview, create/edit modals | Atomic project/session mutations and receipts | Create/hover/menu/edit/archive/remove fixtures |
| Primary root | `PrimarySourceRoot` inside `ProjectRecord` | Project editor, cwd/branch selectors | Root validation, dedupe, missing-root and replacement rules | Multi-root/primary/missing-root tests |
| Conversation | `ConversationProjection`, `TurnReceipt` | `conversation.rs`, message blocks | Ordered stream, retry/stop/branch receipts | Ready/stream/error/branch fixtures |
| Composer | `ComposerState`, `PermissionProfile`, `ModelSelection` | `composer.rs` | Approval policy, provider/model/effort readiness | Empty/access/model/streaming fixtures |
| Environment | `EnvironmentProjection`, `ApprovalRequest` | `context_panel.rs` and section views | Git/provider/runtime/approval truth | Changes/Local/approval/commit fixtures |
| Sources | `SourceAttachment`, `SourceLoadState` | Environment Sources + secondary drawer | Conversation-scoped attach/remove/preview | Sources list/drawer/loading/error fixtures |
| Review | `ReviewProjection`, `ReviewScope` | Review workbench | Real Git scope, branch compare, approval for mutation | Unstaged/staged/multi-root review fixtures |
| Terminal | `TerminalProjection`, `TerminalReceipt` | `terminal_view.rs` | Native PTY, cwd, policy, cancellation | Stream/interrupt/receipt/reconnect fixtures |
| Browser/Files | `BrowserCapability`, `FileProjection` | Browser and Files workbench | Native browser capability or disabled reason; root-bound preview | Browser disabled + file preview fixtures |
| Side chat | `ChildConversationProjection` | Side-chat workbench | Parent/session relationship, exclusion from Chats | Parent/child/count persistence test |
| Activity/commands | `ActivityItem`, `CommandAction` | Bell, command palette, shortcuts | Notification persistence and approval confirmation | Unread/running/waiting/command fixtures |
| Pixel verification | `FixtureState`, `CaptureReport` | Separate capture/diff harness | Deterministic local seed; no production mocks | Actual/diff/overlay/metrics artifact |

## Scrutinize pass

### Intent

The goal is load-bearing: the current native shell has safety/runtime seams,
but its visible UI is still a task-oriented prototype while the target is a
Codex Projects/Chats/workbench surface. A smaller visual-only patch would not
achieve the goal because the missing project/source/permission state is absent
from the control-plane model and runtime routes.

### Trace surprises and risks

1. The original `SessionSummary` had no project/archive/activity fields, so a
   sidebar-only implementation would have had to invent membership and
   sorting. This risk is resolved by the typed projections/storage now in use;
   keep deriving the UI from those projections rather than workspace strings.
2. Project/session/source mutations now route through the Rust-owned
   control-plane contract. Permanent worktrees, cloud environments, and rich
   remote activity history remain disabled until their real routes exist.
3. `start_turn == true` currently renders the string `Full access`; readiness
   is not a permission profile. Decouple policy/profile state before exposing
   the selector or the UI will claim unrestricted access when it is not true.
4. The supplied `side-chat-workbench` screenshot and the existing `CONTEXT.md`
   define the intended composition: Environment is an independent floating
   context card that may remain co-visible with the Workbench; only the active
   Workbench detail tool is exclusive. The old “one shared rail” wording is
   superseded by this domain term.
5. The primary-root gap is now resolved: one persisted primary root, explicit
   `Make primary`, and no silent replacement. This removes ambiguity for
   default cwd, Git, `AGENTS.md`, skills, and `config.toml` discovery.
6. The existing Browser explicitly opens an external/system browser, so simply
   relabeling it `Browser` would be a false parity claim.

### Simpler alternative

Do not add visual façade controls for project/source/permission operations
until their typed runtime projections exist. The smallest safe implementation
slice is: establish project/session/source/permission projections and a
deterministic fixture mode, then render the shell anatomy against those
projections. This avoids a large UI-only mock layer and preserves the current
security boundary.

## Implementation gate

The design decisions are now closed for implementation: primary-root routing
is locked, Environment/Workbench composition is locked, and unsupported
capabilities remain visible but disabled with truthful reasons. The remaining
gates are evidence and capability gates, not visual guesses:

1. Keep the deterministic capture/diff command and fixture seed alongside every
   visual change; never overwrite a golden from the actual capture.
2. Keep typed project/session/source/permission projections and atomic receipts
   as the only source for visible state; do not render façade state from labels
   or workspace strings.
3. Continue closing shell/chrome, sidebar, conversation/composer,
   Environment/Sources, and Workbench gaps with one fixture per state
   transition.
4. Keep Browser disabled until a native bridge is actually available; keep
   permanent-worktree/cloud actions disabled while those runtime routes remain
   unavailable. Project/session/source mutations must stay behind the Rust
   writer and return typed errors.
5. Run accessibility, reduced-motion, focus, responsive, and image-diff gates
   for every fixture before reporting parity.

Parity gate remains separate from `verify.sh`. Use the existing contract
   thresholds: structural edges ≤2 logical px, flat tokens ≤1 RGB code, MAE
   ≤0.02, and no more than 2% of pixels differing by >16/255. Never report
   exact parity while the native capture runner or a state fixture is missing.

## Source links

- [Introducing the Codex app](https://openai.com/index/introducing-the-codex-app/)
- [Codex in ChatGPT](https://openai.com/codex/)
- [ChatGPT desktop app / Codex Learn index](https://learn.chatgpt.com/docs/app)
- [Projects and chats](https://learn.chatgpt.com/docs/projects)
- [Code review](https://learn.chatgpt.com/docs/code-review)
- [Codex environments](https://learn.chatgpt.com/docs/environments/modes)
- [Local environments](https://learn.chatgpt.com/docs/environments/local-environment)
- [Worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees)
- [Sandboxing](https://learn.chatgpt.com/docs/sandboxing)
- [Agent approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Work with files](https://learn.chatgpt.com/docs/artifacts-viewer)
- [Notifications](https://learn.chatgpt.com/docs/notifications)
- [openai/codex](https://github.com/openai/codex)
