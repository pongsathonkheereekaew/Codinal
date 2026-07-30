# `codinal.plugin.v1`

`codinal.plugin.v1` is the canonical, declarative plugin exchange format for
Codinal's Mac Solid release gate. It carries content and requirements; it never
carries code to execute.

## Manifest

```json
{
  "schema": "codinal.plugin.v1",
  "id": "acme/review-helper",
  "version": "1.0.0",
  "publisher": "acme",
  "requested_permissions": ["read"],
  "host_requirements": ["skill_discovery"],
  "model_requirements": ["tools", "streaming"],
  "assets": {
    "skills": [{"name": "review", "content": "Review the diff."}],
    "instructions": [{"path": "AGENTS.md", "content": "Be precise."}],
    "mcp": [],
    "agents": []
  }
}
```

Only `skills`, `instructions`, `mcp`, and `agents` are permitted assets. Hooks,
scripts, and executables are rejected at validation time. Imported assets stay
data until a later, policy-backed host adapter elects to install them.

## Compatibility

`runtime.plugins.CapabilityMatrix.from_host_manifest_file()` loads the host
records from `harness/config/hosts.yaml`; hosts embedded in the packaged app
inject the corresponding shipped capability manifest. It combines that SSOT
with `runtime.providers.capabilities_for(model)`.
Each declared host and model requirement must be `supported`/true. `partial`,
`unsupported`, `unverified`, absent capabilities, and unknown hosts produce a
diagnostic and make the result incompatible. Dispatchers must refuse an
incompatible result; no fallback or semantic downgrade is allowed. Dispatchers
call `PluginTranslation.require_compatible()` at their dispatch boundary.

The canonical JSON encoding is SHA-256 hashed and returned as `sha256:<hex>` so
the translation can be recorded with extension provenance and audit evidence.

## Initial test plan

- Canonical valid manifest: stable digest and preserved declarative assets.
- Host/model pair: compatible only when every declared requirement is met.
- Host status `unverified`, missing model capability, and unknown host: reject.
- Executable asset kind or malformed manifest: reject before translation.
- Future host adapters: fixture import/export contracts for Codex, Claude,
  Cursor, Gemini, and OpenCode; adapters may emit gaps but may not grant
  permissions or execute plugin content.
