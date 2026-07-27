"""GitHub service — resolves credentials + repo identity, delegates to the client.

Reads the GitHub PAT from ``ProviderSecretService`` (the ``provider:github``
profile) and parses ``owner/repo`` from the session's source worktree remote.
Returns secret-safe dicts — the PAT never appears in any return value or error.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Optional

from runtime.secrets import ProviderSecretService

from .client import GitHubClient, GitHubError


_REMOTE_SSH = re.compile(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$")
_REMOTE_HTTPS = re.compile(r"https://github\.com/([^/]+)/(.+?)(?:\.git)?$")


class GitHubNotConfiguredError(RuntimeError):
    """No GitHub PAT is configured."""


def parse_owner_repo(remote_url: str) -> Optional[tuple[str, str]]:
    """Extract (owner, repo) from a GitHub remote URL (ssh or https)."""
    if not isinstance(remote_url, str):
        return None
    for pattern in (_REMOTE_SSH, _REMOTE_HTTPS):
        match = pattern.match(remote_url.strip())
        if match:
            return match.group(1), match.group(2)
    return None


class GitHubService:
    def __init__(
        self,
        secrets: ProviderSecretService,
        *,
        client_factory=None,
    ) -> None:
        self._secrets = secrets
        self._client_factory = client_factory or (
            lambda token: GitHubClient(token)
        )

    def _resolve_token(self) -> str:
        profile = self._secrets.get("provider:github")
        if profile is None or not profile.get("api_key"):
            raise GitHubNotConfiguredError(
                "no GitHub token configured"
            )
        return profile["api_key"]

    def _resolve_owner_repo(
        self,
        source_root: Path,
        remote: str = "origin",
    ) -> tuple[str, str]:
        result = subprocess.run(
            ["git", "-C", str(source_root), "remote", "get-url", remote],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise GitHubError(
                "unable to read git remote; is this a GitHub repository?"
            )
        parsed = parse_owner_repo(result.stdout)
        if parsed is None:
            raise GitHubError(
                "git remote is not a GitHub repository"
            )
        return parsed

    def create_pr(
        self,
        source_root: Path,
        session_branch: str,
        *,
        title: str,
        body: str = "",
        base: str = "",
        remote: str = "origin",
    ) -> dict[str, Any]:
        token = self._resolve_token()
        owner, repo = self._resolve_owner_repo(source_root, remote)
        with self._client_factory(token) as client:
            pr = client.create_pr(
                owner,
                repo,
                title=title,
                head=session_branch,
                base=base or self._default_base(source_root),
                body=body,
            )
        return _summarize_pr(pr)

    def find_pr(
        self,
        source_root: Path,
        session_branch: str,
        *,
        remote: str = "origin",
    ) -> dict[str, Any]:
        token = self._resolve_token()
        owner, repo = self._resolve_owner_repo(source_root, remote)
        with self._client_factory(token) as client:
            pr = client.find_pr(owner, repo, session_branch)
        if pr is None:
            return {"open": False}
        return _summarize_pr(pr)

    def list_checks(
        self,
        source_root: Path,
        ref: str,
        *,
        remote: str = "origin",
    ) -> dict[str, Any]:
        token = self._resolve_token()
        owner, repo = self._resolve_owner_repo(source_root, remote)
        with self._client_factory(token) as client:
            payload = client.list_check_runs(owner, repo, ref)
        runs = payload.get("check_runs", []) if isinstance(payload, dict) else []
        return {
            "total": payload.get("total_count", len(runs)) if isinstance(payload, dict) else 0,
            "runs": [
                {
                    "name": run.get("name", ""),
                    "status": run.get("status", ""),
                    "conclusion": run.get("conclusion"),
                    "url": run.get("html_url", ""),
                }
                for run in runs
            ],
        }

    def _default_base(self, source_root: Path) -> str:
        result = subprocess.run(
            ["git", "-C", str(source_root), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("/")[-1]
        return "main"

    def merge_pr(
        self,
        source_root: Path,
        session_branch: str,
        *,
        method: str = "squash",
        remote: str = "origin",
    ) -> dict[str, Any]:
        token = self._resolve_token()
        owner, repo = self._resolve_owner_repo(source_root, remote)
        with self._client_factory(token) as client:
            pr = client.find_pr(owner, repo, session_branch)
            if pr is None:
                return {"ok": False, "error": "no open PR for this branch"}
            result = client.merge_pr(owner, repo, pr["number"], method=method)
        return {
            "ok": result.get("merged", False),
            "sha": result.get("sha", ""),
            "message": result.get("message", ""),
        }

    def add_review_comment(
        self,
        source_root: Path,
        session_branch: str,
        *,
        body: str,
        remote: str = "origin",
    ) -> dict[str, Any]:
        token = self._resolve_token()
        owner, repo = self._resolve_owner_repo(source_root, remote)
        with self._client_factory(token) as client:
            pr = client.find_pr(owner, repo, session_branch)
            if pr is None:
                return {"ok": False, "error": "no open PR for this branch"}
            client.add_review_comment(owner, repo, pr["number"], body=body)
        return {"ok": True}

    def post_merge_cleanup(
        self,
        source_root: Path,
        session_branch: str,
        *,
        remote: str = "origin",
    ) -> dict[str, Any]:
        """Delete the remote session branch after merge (post-merge cleanup)."""
        token = self._resolve_token()
        owner, repo = self._resolve_owner_repo(source_root, remote)
        with self._client_factory(token) as client:
            deleted = client.delete_branch(owner, repo, session_branch)
        return {"ok": deleted, "branch": session_branch}


def _summarize_pr(pr: dict[str, Any]) -> dict[str, Any]:
    return {
        "open": pr.get("state") == "open",
        "number": pr.get("number"),
        "title": pr.get("title", ""),
        "url": pr.get("html_url", ""),
        "head": pr.get("head", {}).get("ref", ""),
        "base": pr.get("base", {}).get("ref", ""),
        "draft": pr.get("draft", False),
        "mergeable": pr.get("mergeable"),
    }
