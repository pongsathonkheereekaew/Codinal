# CEDIA market performance baseline

Date: 2026-08-08. Machine: single macOS arm64 host. Model:
`opencode-go/deepseek-v4-flash` (local opencode router at `127.0.0.1:4120/v1`).
Source: `docs/evidence/market/a2/{cedia,opencode}.json`.

## Results

| Case | Agent | wall_ms | pass | cache fields |
| --- | --- | --- | --- | --- |
| hello-ts | cedia | 87738 | yes | not exposed by runner yet |
| refactor-py | cedia | 33537 | yes | not exposed by runner yet |
| docs-md | cedia | 34103 | yes | not exposed by runner yet |
| hello-ts | opencode | n/a | no | CLI unavailable |
| refactor-py | opencode | n/a | no | CLI unavailable |
| docs-md | opencode | n/a | no | CLI unavailable |

## Caveats

- This is one machine run, not a general benchmark. Warm/cold caches, router
  state, and model availability change results.
- `opencode` binary is not installed on this machine; its row is an honest
  `not_exposed`/unavailable result, not a comparison.
- Cache-hit percentages require provider usage fields; A2 records them when
  `--usage-file` exposes them and otherwise leaves them `null`.
- The first `hello-ts` run includes model/router cold start.

## Reproduce

```bash
cd ~/CEDIA
bash scripts/bench/run-bench.sh
```
