---
stage: UI-0
owner: desktop/gpui
status: active
source: tests/desktop_ui/test_ui_contract.py
---

# Legacy UI contract classification

This manifest covers all 49 tests in the legacy HTML/JS contract. The tests
remain in the verifier until UI-7; classification is not permission to delete
coverage. `migrate` means the behavior belongs in a Rust/GPUI or UI-model
replacement. `defer` means the runtime/UI plan explicitly does not ship the
capability yet and requires a truthful unavailable/negative test. `legacy`
means the assertion is about an implementation that UI-7 retires. `split`
contains both supported and deferred assertions and must be decomposed before
the legacy test is removed.

| Test | Class | Rust/GPUI replacement or rationale |
|---|---|---|
| `test_desktop_ui_has_native_three_pane_product_structure` | migrate | `shell_layout`, `UI_CONTRACT.md`, and GPUI shell tests |
| `test_desktop_ui_has_accessibility_floor` | migrate | `workbench` accessibility projections plus manual VoiceOver evidence |
| `test_desktop_ui_has_diagnostics_and_audit_surface` | split | Runtime status/readiness migrates; unsupported audit routes stay negative until implemented |
| `test_desktop_ui_toasts_are_interactive_and_announce_errors` | migrate | Native status/error projections with GPUI accessibility roles |
| `test_desktop_ui_defers_editor_bundle_until_a_file_is_opened` | defer | Editor/LSP parity is explicitly out of scope; retain a no-editor-bundle release assertion |
| `test_desktop_ui_defers_terminal_bundle_until_terminal_is_needed` | legacy | JavaScript xterm loader is retired; native PTY presentation owns this behavior |
| `test_terminal_stays_out_of_the_initial_conversation_layout` | migrate | Native terminal pane state and shell layout tests |
| `test_wide_mac_layout_uses_a_codex_style_reading_column` | migrate | `shell_layout` geometry contract |
| `test_environment_panel_is_a_codex_style_right_utility_rail` | migrate | GPUI context/workbench shell projection |
| `test_utility_rail_has_separate_environment_and_subagents_views` | migrate | Typed dock/pane state; unsupported subagent routes remain disabled |
| `test_empty_task_uses_codex_style_quiet_chrome` | migrate | GPUI empty-state projection |
| `test_task_workspace_keeps_conversation_context_visible_before_messages` | migrate | GPUI conversation/context projection |
| `test_workspace_picker_uses_a_native_dialog_not_an_apple_script_bridge` | migrate | Native host workspace picker contract |
| `test_sidebar_uses_quiet_codex_navigation_primitives` | migrate | GPUI navigation renderer and shell tokens |
| `test_sidebar_controls_stay_pinned_and_primary_panes_are_resizable` | migrate | `shell_layout` resize/persistence tests |
| `test_workspace_editor_and_terminal_are_vertically_resizable` | migrate | GPUI split-pane state and terminal presentation tests |
| `test_macos_overlay_reserves_a_safe_traffic_control_zone` | migrate | Native titlebar/window layout contract |
| `test_header_and_composer_use_compact_mac_primitives` | migrate | GPUI shell/composer contract |
| `test_settings_general_uses_functional_codex_style_rows` | migrate | Native provider/update/settings projections |
| `test_settings_exposes_only_real_ecosystem_controls` | migrate | Capability-backed settings controls; no fake routes |
| `test_composer_preserves_all_controls_at_the_minimum_macos_window_width` | migrate | GPUI composer layout tests |
| `test_every_visible_titlebar_zone_supports_native_window_zoom` | migrate | Native GPUI window action tests |
| `test_app_icon_uses_a_dock_safe_margin_around_the_monochrome_tile` | migrate | Release asset/process evidence |
| `test_settings_use_a_full_page_mac_layout_not_a_small_modal` | migrate | GPUI settings presentation |
| `test_empty_workspace_hides_secondary_sidebar_and_routing_chrome` | migrate | Typed shell/dock state |
| `test_no_project_empty_state_invites_a_conversation_without_a_workspace` | migrate | Read-only GPUI empty-state projection |
| `test_terminal_bundle_loader_retries_and_preserves_xterm_load_order` | legacy | JavaScript/xterm implementation is removed; native PTY lifecycle tests replace it |
| `test_editor_bundle_loader_loads_once_and_exposes_the_bridge` | legacy | Legacy editor bundle/bridge is retired; editor parity is deferred |
| `test_streaming_deltas_are_frame_batched_without_rerendering_history` | migrate | GPUI bounded stream reducer and frame-coalescing contract |
| `test_persisted_conversation_messages_reuse_rendered_dom` | legacy | DOM cache is retired; typed timeline replay is the replacement |
| `test_message_render_cache_prunes_removed_history` | legacy | DOM cache is retired; bounded `WorkbenchState` transcript tests replace it |
| `test_streaming_frame_batcher_updates_only_the_live_message` | migrate | GPUI live-block coalescing tests |
| `test_boot_does_not_block_first_paint_on_noncritical_settings` | migrate | Rust bootstrap/readiness sequencing and startup evidence |
| `test_session_model_wins_over_late_global_settings` | migrate | Typed session/provider projection precedence |
| `test_conversation_history_is_committed_in_one_dom_batch` | legacy | DOM batching is retired; bounded Rust timeline snapshots replace it |
| `test_editor_has_native_find_replace_keybindings` | defer | Editor/LSP parity is outside this cutover |
| `test_editor_enables_native_multi_cursor_selection` | defer | Editor/LSP parity is outside this cutover |
| `test_lsp_diagnostics_are_scoped_to_the_active_workspace` | defer | LSP routes/editor are explicitly deferred |
| `test_lsp_symbol_pickers_use_scoped_native_requests_and_shortcuts` | defer | LSP routes/editor are explicitly deferred |
| `test_settings_offer_local_stirling_configuration_and_health_check` | defer | External Stirling integration is not a Rust-native UI capability in this plan |
| `test_settings_offer_loopback_ollama_model_discovery` | defer | New provider/runtime paths are out of scope for this UI cutover |
| `test_editor_exposes_exact_lsp_range_navigation` | defer | Editor/LSP parity is outside this cutover |
| `test_command_palette_has_separate_quick_open_and_safe_commands` | defer | Reintroduce only with a typed GPUI action registry and capability-backed commands |
| `test_artifact_preview_uses_typed_local_renderers` | defer | Artifact routes are not currently implemented; show unavailable truth |
| `test_composer_mentions_create_bounded_project_context_not_attachments` | split | Bounded local context may migrate; unsupported attachment/editor behavior stays negative |
| `test_desktop_client_wires_runtime_approval_diff_and_shortcuts` | split | Approval/read-only core migrates; GitHub/MCP/artifact/editor/worker routes remain explicit negatives |
| `test_desktop_csp_does_not_allow_inline_script_or_styles` | legacy | CSP is irrelevant after the WebView/HTML path is retired; Rust-only package audit replaces it |
| `test_security_scan_is_explicit_and_shows_only_bounded_summary` | defer | Runtime security-scan route is unavailable; preserve an unavailable-state test |
| `test_motion_system_uses_shared_tokens_and_respects_reduce_motion` | migrate | GPUI appearance/reduced-motion state and accessibility matrix |

## Removal rule

No legacy test is removed until its row has a named Rust/GPUI replacement test
or an explicit negative/unavailable test, and the replacement runs in the
canonical C3/UI command set. Mixed `split` rows must be divided into focused
tests first. The legacy HTML/JS source remains evidence only until UI-7’s
release/process/SBOM gate and the runtime plan’s editor-bundle reconciliation
pass.
