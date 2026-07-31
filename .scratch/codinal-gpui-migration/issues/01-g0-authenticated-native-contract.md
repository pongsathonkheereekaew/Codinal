Status: resolved
Type: task

## Question

Can the GPUI migration begin from a versioned Rust client contract without
exposing the loopback bearer token in URLs or UI logs?

## Answer

Yes. Commit `0da14a4` provides the versioned authenticated native contract,
REST/event fixtures, route coverage for the migration surfaces, and loopback
transport tests. The next ticket must connect that contract to a real GPUI
shell while retaining Tauri in release builds.
