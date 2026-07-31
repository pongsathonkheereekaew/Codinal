Status: resolved
Type: prototype
Blocked by: 02

## Question

What GPUI workspace architecture supplies streamed conversation, terminal,
diff, file tree, command palette, keyboard/focus navigation, and measurable
performance parity against Tauri while consuming only the G0 contract?

## Answer

The native layout model is viable: the isolated `desktop/gpui-prototype` crate
builds a four-surface workspace (files, conversation, review, terminal) while
leaving Tauri untouched. Production work must retain this split: a native shell
owns `ControlPlaneClient`; pane reducers receive decoded events only; terminal,
tree, and diff require virtualized elements; commands and focus are root-window
actions. On macOS, builds require `TOOLCHAINS=Metal` until the Xcode default
toolchain includes Metal again. The prototype is explicitly disposable and
must be absorbed into a production GPUI crate before G3 begins.
