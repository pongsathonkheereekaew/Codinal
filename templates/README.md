# [Plugin Name]

[Short description of the plugin and features]

## Project Context
- **Stack**: C++20 / JUCE
- **Target Platform**: macOS (Apple Silicon & Intel)
- **Active Curves**: ES-Q's orange active curves (UI)
- **Labeling Fonts**: 10px standard UI labels
- **Realtime Audio Invariants**: No dynamic allocations in audio thread, lock-free operations.

## Developer & Workflow Settings
- **SSOT (Single Source of Truth)**: Rules for UI styling, copywriting (em dash `—`, no marketing fluff), and C++ DSP code safety are defined in `~/.cursor/rules/`.
- **Headless Verification Gate**: Test suite runs automatically on code modifications via local script.
- **Smart Test Runner**: Trigger and verify tests by running:
  ```bash
  ./verify.sh
  ```
