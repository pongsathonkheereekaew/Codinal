# Provider secret storage

Codinal persists provider API keys in the macOS Keychain through the signed
Rust/Tauri host. The Python runtime never opens the Keychain and never writes a
credential file.

## Boundaries

- Supported Phase 1 providers are `openai`, `anthropic`, and `gemini`.
- Keychain service names are fixed by the host; user input can select only a
  supported provider account.
- Secrets are absent from command-line arguments, environment values, URLs,
  settings JSON, logs, status responses, and WebView storage.
- At startup Rust reads configured Keychain items, serializes only the known
  provider profiles, writes the payload to the sidecar's one-shot stdin pipe,
  closes the pipe, and zeroizes the serialized Rust buffer.
- Python validates the complete bootstrap schema and size before placing
  defensive copies in an in-memory `ProviderSecretService`.
- The sidecar consumes both bootstrap markers and its control-plane token from
  the environment before any future tool subprocess can inherit them.
- Runtime status and mutation responses expose only provider name and
  `configured`; validation errors never echo request values.
- Secret mutation requires a second random sync token carried only in the
  Rust-to-Python stdin bootstrap. The WebView receives the general control-plane
  bearer but never this sync token, so it cannot bypass the Keychain transaction.

## Hot updates

The Tauri command writes the Keychain first and then sends the new value in an
authenticated HTTP request body to the loopback runtime. It never places the
value or either token in the request URL. The request requires both the general
control-plane bearer and the native-only secret-sync header. If runtime
synchronization fails, the host restores the previous Keychain value (or
removes the newly created item) and reports a value-free error.

The in-memory store notifies the provider router after a successful mutation,
which discards only the affected cached SDK client. Listener notification is
transactional: if invalidation fails, the runtime restores its previous
in-memory value and returns a value-free failure so the native host can roll
back Keychain too.

Raw secret reads are not exposed as a Tauri command or control-plane endpoint.
Provider adapters receive the in-memory store through runtime composition and
resolve only the profile they need.

## Rationale

The Python `keyring` project supports macOS, but its own security notes explain
that Python code using the same Python executable may access items created by
that backend without another password prompt. Codinal runs user-directed tools,
so the native signed host is the narrower persistent-secret owner:
<https://pypi.org/project/keyring/#security-considerations>.
