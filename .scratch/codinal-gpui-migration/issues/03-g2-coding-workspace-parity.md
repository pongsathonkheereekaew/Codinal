Status: resolved
Type: prototype
Blocked by: 02

## Question

What GPUI workspace architecture supplies streamed conversation, terminal,
diff, file tree, command palette, keyboard/focus navigation, and measurable
performance parity against Tauri while consuming only the G0 contract?

## Answer

The native layout model is viable: the `desktop/gpui` crate
builds a four-surface workspace (files, conversation, review, terminal) while
the cutover proceeds. Production work must retain this split: a native shell
owns `ControlPlaneClient`; pane reducers receive decoded events only; terminal,
tree, and diff require virtualized elements; commands and focus are root-window
actions. On macOS, builds require `TOOLCHAINS=Metal` until the Xcode default
toolchain includes Metal again. The former prototype has been promoted into
the production GPUI crate.
