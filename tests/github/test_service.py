"""GitHub service tests — owner/repo parsing + secret-safe delegation."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.github import GitHubError, GitHubService
from runtime.github.service import GitHubNotConfiguredError, parse_owner_repo
from runtime.secrets import ProviderSecretService


def test_parse_owner_repo_handles_ssh_and_https():
    assert parse_owner_repo("git@github.com:owner/repo.git") == ("owner", "repo")
    assert parse_owner_repo("https://github.com/owner/repo.git") == ("owner", "repo")
    assert parse_owner_repo("https://github.com/owner/repo") == ("owner", "repo")
    assert parse_owner_repo("git@gitlab.com:owner/repo.git") is None
    assert parse_owner_repo("not a url") is None


def _secrets_with_github_token(token: str = "ghp_test-1234567890") -> ProviderSecretService:
    service = ProviderSecretService()
    service.set_api_key("github", token)
    return service


class _FakeClient:
    def __init__(self, _token):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None

    def create_pr(self, owner, repo, *, title, head, base, body=""):
        self.calls.append(("create_pr", owner, repo, title, head, base, body))
        return {
            "number": 1,
            "title": title,
            "state": "open",
            "html_url": f"https://github.com/{owner}/{repo}/pull/1",
            "head": {"ref": head},
            "base": {"ref": base},
            "draft": False,
            "mergeable": True,
        }

    def find_pr(self, owner, repo, head):
        self.calls.append(("find_pr", owner, repo, head))
        return {
            "number": 1,
            "title": "Existing",
            "state": "open",
            "html_url": f"https://github.com/{owner}/{repo}/pull/1",
            "head": {"ref": head},
            "base": {"ref": "main"},
            "draft": False,
            "mergeable": None,
        }

    def list_check_runs(self, owner, repo, ref):
        self.calls.append(("list_check_runs", owner, repo, ref))
        return {
            "total_count": 1,
            "check_runs": [
                {"name": "CI", "status": "completed", "conclusion": "success", "html_url": "u"},
            ],
        }


def _repo_with_remote(tmp_path: Path, remote_url: str) -> Path:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"])
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"])
    (repo / "f.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", remote_url], check=True)
    return repo


def test_create_pr_resolves_owner_repo_and_returns_secret_safe_summary(tmp_path):
    repo = _repo_with_remote(tmp_path, "git@github.com:acme/widget.git")
    fake = _FakeClient("ignored")
    service = GitHubService(_secrets_with_github_token(), client_factory=lambda _t: fake)

    result = service.create_pr(repo, "feature", title="Add thing", body="body", base="main")

    assert result["open"] is True
    assert result["number"] == 1
    assert result["url"] == "https://github.com/acme/widget/pull/1"
    assert "token" not in str(result)
    assert fake.calls[0] == (
        "create_pr", "acme", "widget", "Add thing", "feature", "main", "body"
    )


def test_find_pr_returns_open_false_when_none(tmp_path):
    repo = _repo_with_remote(tmp_path, "https://github.com/acme/widget.git")

    class _NoPrClient(_FakeClient):
        def find_pr(self, owner, repo, head):
            return None

    service = GitHubService(
        _secrets_with_github_token(),
        client_factory=lambda _t: _NoPrClient("ignored"),
    )

    result = service.find_pr(repo, "feature")

    assert result == {"open": False}


def test_list_checks_returns_summarized_runs(tmp_path):
    repo = _repo_with_remote(tmp_path, "git@github.com:acme/widget.git")
    fake = _FakeClient("ignored")
    service = GitHubService(_secrets_with_github_token(), client_factory=lambda _t: fake)

    result = service.list_checks(repo, "abc123")

    assert result["total"] == 1
    assert result["runs"][0]["name"] == "CI"
    assert result["runs"][0]["conclusion"] == "success"


def test_missing_token_raises_not_configured(tmp_path):
    repo = _repo_with_remote(tmp_path, "git@github.com:acme/widget.git")
    service = GitHubService(ProviderSecretService(), client_factory=lambda _t: _FakeClient("ignored"))

    with pytest.raises(GitHubNotConfiguredError):
        service.create_pr(repo, "feature", title="x")


def test_non_github_remote_raises_error(tmp_path):
    repo = _repo_with_remote(tmp_path, "git@gitlab.com:acme/widget.git")
    service = GitHubService(_secrets_with_github_token(), client_factory=lambda _t: _FakeClient("ignored"))

    with pytest.raises(GitHubError, match="not a GitHub repository"):
        service.create_pr(repo, "feature", title="x")
