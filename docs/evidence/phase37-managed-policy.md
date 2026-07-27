# Phase 37 evidence — organization allowlists + managed policy

Date: 2026-07-27
P1 roadmap item: "Add organization model/provider/repository/tool allowlists and managed policy that local users cannot silently weaken."

## What shipped

- **ManagedPolicy** (`runtime/policy/managed.py`): loads from JSON at startup (`CODINAL_MANAGED_POLICY` env path). Carries `allowed_providers`, `allowed_models`, `denied_tools`, `denied_commands`. All optional; absent = unrestricted.
- **Deny precedence** at 2 control points (the highest-leverage ones for v1):
  - **Permission engine** (`runtime/policy/permissions.py`): `evaluate()` short-circuits with a managed-deny BEFORE every allow path (session grants, AUTO mode, standing rules). A tool or command denied by managed policy cannot be overridden by the user.
  - **Provider secrets** (`runtime/secrets/service.py`): `set_api_key` checks `provider_allowed` before accepting. A provider not in the allowlist is rejected.
- **Wiring**: `build_services` loads `ManagedPolicy.from_file(config.managed_policy_path)`; threads into `ProviderSecretService` + `PermissionEngine` (via `compose_runtime` → `build_engine` closure).
- **Route**: `GET /v1/policy` (auth-required) returns the active managed policy or `{active: false}`.

## Verification (fresh, 2026-07-27)

```
$ ./.venv/bin/pytest -q tests/policy/test_managed.py tests/policy/test_managed_deny_precedence.py
............                                                             [100%]
12 passed
```

```
$ CI= ./.venv/bin/pytest -q
847 passed, 1 skipped, 53 warnings in 80.32s
```

`verify.sh`: PASS.

## Non-goals (deferred)

- SSO/SCIM/RBAC (separate auth layer).
- Per-repository allowlists (managed policy is global for v1).
- Policy hot-reload (loaded once at startup).
- Tool-manifest-level pruning + routing-level model filtering (the permission-engine deny covers the user-actionable surface; deeper integration is future work).
