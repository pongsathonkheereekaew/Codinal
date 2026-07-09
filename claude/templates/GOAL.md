# GOAL
<one-line objective for this loop>

## Definition of done
- [ ] <verifiable criterion>
- [ ] <verifiable criterion>

## Non-goals (will NOT do)
- <explicit out-of-scope — curbs scope creep>

## Constraints / never-touch
- Stack / files in scope: <...>
- Denylist (never edit without asking): `.env*`, `**/secrets/**`, `**/*_key*`, `auth/**`, `payments/**`, `billing/**`, `**/migrations/**`, `k8s/production/**`
- Human-gate — STOP + ask before: security/auth, payments/PII, infra, dependency upgrades, any change touching >10 files, or the 3rd failed attempt.

## Progress log
<!-- append one line per session: YYYY-MM-DD — done X — next Y. PRUNE finished items so a resumed session never re-does them. -->
- Attempts: 0/3   (escalate to human at 3)
- Last run: <YYYY-MM-DD>

## Next step
<the single concrete action a fresh session should take first>
