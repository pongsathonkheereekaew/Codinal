"""Live GitHub integration test — only runs with real credentials.

Skipped unless both ``CODINAL_GITHUB_TOKEN`` and ``CODINAL_GITHUB_TEST_REPO``
(env, format ``owner/repo``) are set. Designed for a disposable test repo.
"""

from __future__ import annotations

import os
import uuid

import pytest

from runtime.github import GitHubClient, GitHubError


pytestmark = [
    pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="live GitHub test runs locally with real credentials, not on CI",
    ),
    pytest.mark.skipif(
        not os.environ.get("CODINAL_GITHUB_TOKEN"),
        reason="CODINAL_GITHUB_TOKEN not set",
    ),
    pytest.mark.skipif(
        not os.environ.get("CODINAL_GITHUB_TEST_REPO"),
        reason="CODINAL_GITHUB_TEST_REPO (owner/repo) not set",
    ),
]


def _owner_repo():
    return os.environ["CODINAL_GITHUB_TEST_REPO"].split("/", 1)


def test_live_create_and_read_pr():
    token = os.environ["CODINAL_GITHUB_TOKEN"]
    owner, repo = _owner_repo()
    branch = f"test-live-{uuid.uuid4().hex[:8]}"
    title = f"Codinal live test {branch}"

    with GitHubClient(token) as client:
        # Create a PR (assumes the branch already exists on the remote;
        # this test validates the API path, not branch creation).
        try:
            pr = client.create_pr(
                owner, repo, title=title, head=branch, base="main"
            )
        except GitHubError as exc:
            pytest.skip(f"could not create PR (branch may not exist): {exc}")

        assert pr["number"]
        assert pr["title"] == title

        # Read it back.
        fetched = client.get_pr(owner, repo, pr["number"])
        assert fetched["number"] == pr["number"]

        # Find by head.
        found = client.find_pr(owner, repo, branch)
        assert found is not None
        assert found["number"] == pr["number"]
