# OAuth callback security

Codinal receives provider redirects through the native
`codinal://oauth/callback` scheme. A callback carries an authorization code or
a provider error; it never carries an access token, refresh token, API key, or
installation credential.

## Flow

1. A registered provider handler begins a flow. The runtime creates a
   cryptographically random URL-safe state, binds it to the flow and metadata,
   and keeps it in memory for at most ten minutes.
2. The provider redirects to the statically registered custom scheme.
3. The Rust host accepts only the exact scheme, host, path, and query schema.
   Duplicate or unknown parameters, fragments, invalid flow/state values, and
   ambiguous code/error results are rejected without logging their values.
4. Rust posts the validated callback in a JSON body to loopback. The request
   requires the process bearer and the native-only sync token; neither token is
   put in the URL or exposed to the WebView.
5. Python atomically consumes the matching state before invoking the injected
   provider handler. Expired, unknown, wrong-flow, and replayed callbacks fail.

## Threat model

Custom schemes can be invoked by another local process and must not be treated
as proof of origin. Security comes from strict parsing plus a strong,
flow-bound, expiring, single-use state. The native-only relay token prevents
WebView JavaScript—which has the general control-plane bearer—from consuming a
valid state with a forged code.

The pending-state registry is bounded to limit memory use. Consumption is
lock-protected so concurrent callbacks have exactly one winner. Provider errors
also consume state. Handler failures do not restore state and responses expose
only a generic result and flow identifier; authorization codes are zeroized in
the native relay object and never included in error text.

Provider handlers are injected through runtime composition. They exchange the
code server-to-server and resolve persistent credentials through the native
Keychain boundary described in `docs/security/secret-storage.md`.

Tauri requires desktop custom schemes to be configured statically:
<https://v2.tauri.app/plugin/deep-linking/>.
