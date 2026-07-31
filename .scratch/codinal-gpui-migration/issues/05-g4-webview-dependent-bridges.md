Status: resolved
Type: prototype
Blocked by: 02, 04

## Question

Which constrained native mechanisms can replace WebView-dependent OAuth and
preview paths while preserving fail-closed loopback-only navigation?

## Answer

OAuth reuses the existing system-browser `codinal://oauth/callback` parser and
native relay. The prototype exposes no interactive preview: it may show only
saved evidence until a native child renderer proves explicit loopback-only
allow/deny behaviour in packaged tests. Tauri remains the interactive preview
fallback in the meantime.
