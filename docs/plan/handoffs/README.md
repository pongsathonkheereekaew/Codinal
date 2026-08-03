# Durable Handoffs

Store session transitions here when the next session needs durable context.
Temporary `/tmp` handoffs are intake inputs and must be copied or summarized
into a dated file before handoff-out.

Each handoff should contain:

- goal and current scope
- changed files and verified commands
- constraints, rollback boundaries, and sensitive-data status
- unresolved findings and exact next actions
- source handoff path and freshness timestamp

Use `YYYY-MM-DD-topic.md` naming. Do not include credentials, bearer tokens,
provider keys, approval tokens, or PII.
