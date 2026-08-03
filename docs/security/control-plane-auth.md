# Local control-plane authentication

Codinal's desktop UI talks to its Python runtime over a random loopback port.
Loopback binding limits network exposure but is not authentication: another
local process can still issue requests. Every desktop process therefore gets a
new 256-bit bearer token minted by the Rust host.

## Contract

- The Python server binds only to `127.0.0.1`.
- Rust passes the token through the child environment, never through argv. The
  sidecar consumes and removes that environment entry during startup so tool
  subprocesses cannot inherit it.
- The token remains in WebView memory; it is not written to local or session
  storage.
- Every HTTP request, including unknown/future routes, requires the exact
  `Authorization: Bearer <token>` header.
- Browser WebSockets request both `codinal.v1` and
  `codinal.auth.<token>` subprotocols. The server selects only `codinal.v1`.
- Tokens in query strings are not accepted.
- Missing or invalid HTTP credentials return `401` with
  `WWW-Authenticate: Bearer`; WebSockets close with `4401`.
- A supplied WebSocket Origin outside the native client/development allowlist
  closes with `4403`. Missing Origin remains valid for authenticated native
  clients.
- CORS preflight is allowed without bearer only for configured origins.
- FastAPI documentation and OpenAPI routes are disabled.

The token is process-scoped, not a user identity or authorization model.
Tool execution still passes through `PermissionEngine`; control-plane auth
does not replace risk classification, approval, workspace scoping, or the
Phase 3 shell sandbox.

Git review routes are read-only. The authenticated Apply-back route is an
explicit host action and refuses active turns, changed source branches, dirty
source/session worktrees, and missing session bindings. It never pushes.
Conflicts return only after `git merge --abort` restores and verifies the
recorded source HEAD and a clean status.

## Verification

Run:

```bash
python -m pip install -r requirements-dev.txt
bash verify.sh
```

The suite includes negative coverage for missing, malformed, wrong, and
query-string credentials; unknown future HTTP routes; CORS preflight; allowed
and denied WebSocket origins; protocol-token authentication; token format; and
the Rust spawn boundary.
