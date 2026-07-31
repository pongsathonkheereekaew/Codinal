# G4 bridge prototype decision

OAuth remains a system-browser flow. The GPUI shell hands only the exact
`codinal://oauth/callback` URL to the existing native parser and relay; it does
not embed provider pages or retain the authorization code in a view model.

Preview is unavailable in the GPUI prototype. A future native preview child is
permitted only when every navigation is checked before it loads:

- scheme is `http` or `https`;
- host is exactly `127.0.0.1`, `::1`, or `[::1]`;
- an explicit port is present;
- redirects and external origins are rejected, not opened externally.

Until that renderer has packaged allow/deny tests, the GPUI shell must show
saved loopback verification evidence only. Tauri remains the release fallback
for interactive preview.
