# R0 negative contract cases

## Scope
Reference control plane (runtime/control_plane/app.py)

## HTTP
- GET /v1/health without authorization must return 401 with `www-authenticate: Bearer`.
- GET /v1/version without authorization must return 401 with `www-authenticate: Bearer`.
- GET /v1/secrets/providers without authorization must return 401.
- random /v1/ghost returns 404.
- invalid payload on write routes returns 4xx and no state mutation.

## WebSocket
- /ws/events missing protocol closes with 4401.
- /ws/events untrusted origin closes with 4403.
- /ws/session/{session_id} requires valid token.

## Event stream
- reconnect never emits pre-checkpoint events.
- event sequence order is deterministic per stream.
