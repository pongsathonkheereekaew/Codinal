"""Thin GitHub REST API client over httpx.

All calls are bounded (timeout + response size) and never log the token.
Errors collapse to ``GitHubError`` without echoing the token or the full
response body (only the GitHub message + status).
"""

from __future__ import annotations

from typing import Any, Optional

import httpx


_TIMEOUT_SECONDS = 30.0
_MAX_RESPONSE_BYTES = 1024 * 1024  # 1 MiB


class GitHubError(Exception):
    """Raised on any non-2xx response or transport failure.

    The message never includes the token; only the GitHub API message + status.
    """

    def __init__(self, message: str, *, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class GitHubClient:
    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://api.github.com",
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not isinstance(token, str) or not token:
            raise ValueError("token must be a non-empty string")
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=_TIMEOUT_SECONDS,
            transport=transport,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "codinal/1.0",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        try:
            response = self._client.request(
                method,
                path,
                json=json,
                params=params,
            )
        except httpx.HTTPError as exc:
            raise GitHubError(f"github request failed: {exc.__class__.__name__}") from None
        if len(response.content) > _MAX_RESPONSE_BYTES:
            raise GitHubError("github response exceeded size limit")
        if response.status_code >= 400:
            message = "github api error"
            try:
                body = response.json()
                if isinstance(body, dict) and isinstance(body.get("message"), str):
                    message = body["message"][:200]
            except (ValueError, TypeError):
                pass
            raise GitHubError(message, status=response.status_code)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except (ValueError, TypeError) as exc:
            raise GitHubError("github returned non-JSON response") from exc

    def create_pr(
        self,
        owner: str,
        repo: str,
        *,
        title: str,
        head: str,
        base: str,
        body: str = "",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            json={"title": title, "head": head, "base": base, "body": body},
        )

    def get_pr(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{number}",
        )

    def find_pr(
        self,
        owner: str,
        repo: str,
        head: str,
    ) -> Optional[dict[str, Any]]:
        # head must be in the form owner:branch for the API filter.
        head_filter = head if ":" in head else f"{owner}:{head}"
        result = self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            params={"head": head_filter, "state": "open"},
        )
        if isinstance(result, list) and result:
            return result[0]
        return None

    def list_check_runs(
        self,
        owner: str,
        repo: str,
        ref: str,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/repos/{owner}/{repo}/commits/{ref}/check-runs",
        )
