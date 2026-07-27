"""GitHub client tests — mocked httpx transport, no real API calls."""

from __future__ import annotations

import json

import httpx
import pytest

from runtime.github import GitHubClient, GitHubError


def _client(transport: httpx.BaseTransport) -> GitHubClient:
    return GitHubClient(
        token="ghp_test-token-not-real-1234567890",
        transport=transport,
    )


def _mock(handler, *, status=200, body=None) -> httpx.MockTransport:
    if body is not None:
        return httpx.MockTransport(handler)
    return httpx.MockTransport(handler)


def test_create_pr_returns_summarized_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization", "")
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "number": 42,
                "title": "Add feature",
                "state": "open",
                "html_url": "https://github.com/owner/repo/pull/42",
                "head": {"ref": "feature"},
                "base": {"ref": "main"},
                "draft": False,
                "mergeable": True,
            },
        )

    with _client(_mock(handler)) as client:
        result = client.create_pr(
            "owner", "repo", title="Add feature", head="feature", base="main"
        )

    assert result["number"] == 42
    assert captured["auth"] == "Bearer ghp_test-token-not-real-1234567890"
    assert "/repos/owner/repo/pulls" in captured["url"]
    assert captured["body"]["title"] == "Add feature"


def test_get_pr_returns_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"number": 7, "title": "pr", "state": "open"},
        )

    with _client(_mock(handler)) as client:
        result = client.get_pr("owner", "repo", 7)

    assert result["number"] == 7


def test_find_pr_returns_first_open_pr():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"number": 1}, {"number": 2}],
        )

    with _client(_mock(handler)) as client:
        result = client.find_pr("owner", "repo", "feature")

    assert result["number"] == 1


def test_find_pr_returns_none_when_no_open_pr():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with _client(_mock(handler)) as client:
        result = client.find_pr("owner", "repo", "feature")

    assert result is None


def test_list_check_runs_returns_check_runs():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total_count": 2,
                "check_runs": [
                    {"name": "CI", "status": "completed", "conclusion": "success", "html_url": "u1"},
                    {"name": "Lint", "status": "completed", "conclusion": "failure", "html_url": "u2"},
                ],
            },
        )

    with _client(_mock(handler)) as client:
        result = client.list_check_runs("owner", "repo", "abc123")

    assert result["total_count"] == 2
    assert result["check_runs"][0]["name"] == "CI"
    assert result["check_runs"][1]["conclusion"] == "failure"


def test_error_does_not_echo_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"message": "Bad credentials"},
        )

    with _client(_mock(handler)) as client:
        with pytest.raises(GitHubError) as exc_info:
            client.get_pr("owner", "repo", 1)

    assert "ghp_test-token-not-real" not in str(exc_info.value)
    assert exc_info.value.status == 403


def test_transport_failure_raises_github_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with _client(_mock(handler)) as client:
        with pytest.raises(GitHubError, match="request failed"):
            client.get_pr("owner", "repo", 1)


def test_merge_pr_sends_put_merge():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"sha": "abc123", "merged": True, "message": "Pull request successfully merged"})

    with _client(_mock(handler)) as client:
        result = client.merge_pr("owner", "repo", 42, method="squash")

    assert captured["method"] == "PUT"
    assert "/repos/owner/repo/pulls/42/merge" in captured["url"]
    assert captured["body"]["merge_method"] == "squash"
    assert result["merged"] is True


def test_add_review_comment_posts_review():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 1, "state": "COMMENTED"})

    with _client(_mock(handler)) as client:
        client.add_review_comment("owner", "repo", 42, body="LGTM")

    assert "/repos/owner/repo/pulls/42/reviews" in captured["url"]
    assert captured["body"]["body"] == "LGTM"
    assert captured["body"]["event"] == "COMMENT"


def test_delete_branch_returns_true_on_204():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    with _client(_mock(handler)) as client:
        result = client.delete_branch("owner", "repo", "feature")

    assert result is True


def test_delete_branch_returns_false_on_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "not found"})

    with _client(_mock(handler)) as client:
        with pytest.raises(GitHubError):
            client.delete_branch("owner", "repo", "missing")
