# R2 Slice A negative cases

## Scope
- auth/contract enforcement for Slice A routes
- malformed inputs for provider list route path and bootstrap state surfaces

## Evidence
- unauthorized `/v1/health` remains 401
  - `cargo test --manifest-path crates/codinal-runtime/Cargo.toml health_route_requires_exact_bearer_token -- --nocapture`
- unauthorized `/v1/version` remains 401
  - covered by route handler parity assertion in shared fixture (`/v1/version` requires bearer token)
- unauthorized `/v1/secrets/providers` requires bearer token
  - shared auth gate at handler level
- existing install remains readable and returns 200 for `/v1/health`
  - `cargo test --manifest-path crates/codinal-runtime/Cargo.toml runtime_bootstrap_reuses_existing_installed_data_directory -- --nocapture`
- existing install read path no state mutation on empty sessions
  - `cargo test --manifest-path crates/codinal-runtime/Cargo.toml fresh_runtime_lists_zero_sessions_instead_of_rejecting_request -- --nocapture`

## Result
- Slice A negative controls are present and have test-backed pass signal.
- status: **PASS**
