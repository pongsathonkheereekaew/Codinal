# R2 Slice A conformance

## Slice A scope
- routes: `/v1/version`, `/v1/config`, `/v1/security/status`, `/v1/secrets/providers`, `/v1/health`
- gate: contract parity + auth checks + startup owner model

## Evidence (runtime)
- `cargo test --manifest-path crates/codinal-runtime/Cargo.toml runtime_bootstrap_ -- --nocapture`
  - `tests::runtime_bootstrap_exclusively_owns_its_data_directory` passed
  - `tests::runtime_bootstrap_consumes_the_host_token_environment_value` passed
  - `tests::runtime_bootstrap_reuses_existing_installed_data_directory` passed
  - `tests::runtime_bootstrap_consumes_one_shot_provider_secrets_from_stdin` passed
- Slice-specific route tests in `crates/codinal-runtime/src/lib.rs` passed:
  - `version_route_returns_active_version`
  - `config_route_returns_non_secret_runtime_config`
  - `security_status_route_reports_unavailable`
  - `secrets_provider_status_returns_configured_flag_only`
  - `fresh_runtime_lists_zero_sessions_instead_of_rejecting_request`

## Result
- `Slice A` conformance evidence generated from live runtime assertions on `/v1` handlers.
- status: **PASS**
