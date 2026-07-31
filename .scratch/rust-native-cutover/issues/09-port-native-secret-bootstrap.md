Type: task
Status: resolved
Blocked by: 07

## Question

Can the native host transfer Keychain provider profiles directly to the Rust
runtime once through bounded stdin without environment/argv exposure, retain
them only in zeroizing memory, and keep secret values out of diagnostics?

## Answer

Yes. `codinal-providers` validates the existing `stdin-v1` document with exact
fields, provider IDs, URL rules, and byte/count limits, then owns API keys and
the sync token in zeroizing memory with redacted Debug output. The native host
uses a piped stdin only for the bootstrap write, and GPUI now loads Keychain
profiles and launches the real Rust shadow runtime through that path. Unit and
real-binary integration tests cover valid, malformed, oversized, and redaction
behavior without printing secret values.
