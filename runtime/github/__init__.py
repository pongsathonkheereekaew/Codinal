"""GitHub connector — PR creation + CI status over scoped credentials."""

from .client import GitHubClient, GitHubError
from .service import GitHubService

__all__ = ["GitHubClient", "GitHubError", "GitHubService"]
