# Phase 39 evidence — GitHub merge + review comments + post-merge cleanup

Date: 2026-07-27
Completes the GitHub PR item from P1 ship loop (started in Phase 34).

## What shipped

- **GitHub client**: `merge_pr` (PUT /pulls/{n}/merge), `add_review_comment` (POST /pulls/{n}/reviews), `delete_branch` (DELETE /git/refs/heads/{branch}).
- **GitHub service**: `merge_pr`, `add_review_comment`, `post_merge_cleanup` — all resolve PAT + owner/repo from the session's source worktree.
- **Routes**: `POST /v1/sessions/{id}/github/merge` (squash/merge/rebase, `mutate_when_idle` gated, audited), `POST /v1/sessions/{id}/github/comment` (review comment), `POST /v1/sessions/{id}/github/cleanup` (post-merge branch delete, audited).
- **GitHubControl Protocol** extended with `merge_pr`, `add_review_comment`, `post_merge_cleanup`.

## Verification

```
$ ./.venv/bin/pytest -q tests/github/test_client.py tests/control_plane/test_session_routes.py -k github
.................                                                        [100%]
17 passed
```

```
$ CI= ./.venv/bin/pytest -q
862 passed, 1 skipped
```

`verify.sh`: PASS (Codinal verify).
