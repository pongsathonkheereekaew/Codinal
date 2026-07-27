# Phase 34 evidence — GitHub PR + CI status integration

Date: 2026-07-27
P1 roadmap item: "Add GitHub PR creation/review, review comments, CI status/logs, opt-in auto-fix, merge, and post-merge cleanup through scoped credentials." (PR create + CI read done; review comments/auto-fix/merge/post-merge cleanup deferred.)

## What shipped

- **Credential**: `provider:github` added to `SUPPORTED_PROVIDERS` (Python + Rust). A GitHub fine-grained PAT flows through the existing Keychain → stdin bootstrap → `ProviderSecretService` (same plumbing as LLM provider keys).
- **GitHub client** (`runtime/github/client.py`): httpx-based REST client. `create_pr`, `get_pr`, `find_pr`, `list_check_runs`. Bounded (30s timeout, 1 MiB response cap). Token never logged; errors collapse to `GitHubError` without echoing the token.
- **GitHub service** (`runtime/github/service.py`): resolves PAT + parses `owner/repo` from the session's `git remote get-url origin`; delegates to client; returns secret-safe summaries.
- **Routes**: `POST /v1/sessions/{id}/github/pr` (create), `GET .../github/pr` (current PR), `GET .../github/checks` (CI status). All auth-required; PR create gated by `mutate_when_idle`.
- **Desktop UI**: "Create PR" button next to Push; PR-status line with link + CI summary; `loadPullRequest`/`createPullRequest`/`loadChecks`.

## Verification (fresh, 2026-07-27)

Client tests (mocked httpx):

```
$ ./.venv/bin/pytest -q tests/github/test_client.py
.......                                                                   [100%]
7 passed
```

Service tests (mocked client + real git remote parsing):

```
$ ./.venv/bin/pytest -q tests/github/test_service.py
......                                                                    [100%]
6 passed
```

Route tests (fake github service):

```
$ ./.venv/bin/pytest -q tests/control_plane/test_session_routes.py -k github
.....                                                                     [100%]
5 passed
```

UI contract:

```
$ ./.venv/bin/pytest -q tests/desktop_ui/test_ui_contract.py
.....                                                                     [100%]
5 passed
```

Full local suite (live test skips without creds):

```
$ CI= ./.venv/bin/pytest -q
815 passed, 1 skipped, 53 warnings in 76.96s
```

`verify.sh`: PASS.

## Token-safety proof

`test_error_does_not_echo_token` mocks a 403 response and asserts the test token string never appears in the `GitHubError` message. Service tests assert `"token" not in str(result)` for every return value.

## Non-goals (deferred)

- Review comments / inline review (needs diff-position mapping).
- Opt-in auto-fix (needs contents:write live testing).
- Merge / post-merge branch cleanup (needs PR write + live testing).
- GitHub Actions log streaming (checks:read gives status; full log streaming separate).
