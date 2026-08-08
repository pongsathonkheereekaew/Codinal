# Cursor adapter verification

```bash
bash harness/scripts/adapters/cursor-verify.sh
```

Result: PASS. The smoke asserts the generated `agents-policy.mdc` contract:

- `~/.cursor/rules/agents-policy.mdc` exists
- frontmatter contains `alwaysApply: true`
- `~/.cursor/skills` and `~/.cursor/commands` resolve

`native_permissions` stays `unsupported` because Cursor has no enforceable
native permission mechanism in the harness contract.
