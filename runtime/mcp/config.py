# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Andrew Ng
# Adapted from andrewyng/openworker:
# coworker/mcp/config.py @ 54b4bfd82d75704a4079ecea4f8f622aa152dbde.
"""Validated, non-secret MCP server definitions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class MCPServerDef:
    name: str
    transport: str
    command: Optional[str] = None
    args: list[str] = field(default_factory=list)
    cwd: Optional[str] = None
    url: Optional[str] = None
    include_tools: Optional[list[str]] = None
    exclude_tools: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _NAME.fullmatch(self.name) is None:
            raise ValueError("invalid MCP server name")
        if self.transport not in {"stdio", "http"}:
            raise ValueError("invalid MCP transport")
        _validate_filters(self.include_tools, self.exclude_tools)
        if self.transport == "http":
            if self.command is not None or self.args or self.cwd is not None:
                raise ValueError("invalid MCP HTTP definition")
            _validate_http_url(self.url)
            return
        if self.url is not None:
            raise ValueError("invalid MCP stdio definition")
        if (
            not isinstance(self.command, str)
            or not 1 <= len(self.command) <= 4096
            or any(character.isspace() for character in self.command)
            or "\x00" in self.command
        ):
            raise ValueError("invalid MCP command")
        if (
            not isinstance(self.args, list)
            or len(self.args) > 256
            or any(
                not isinstance(argument, str)
                or len(argument) > 16_384
                or "\x00" in argument
                for argument in self.args
            )
        ):
            raise ValueError("invalid MCP arguments")
        if self.cwd is not None:
            directory = Path(self.cwd).expanduser()
            if not directory.is_absolute() or not directory.is_dir():
                raise ValueError("invalid MCP working directory")


def _validate_http_url(value: Optional[str]) -> None:
    try:
        parsed = urlsplit(value or "")
        port = parsed.port
    except (TypeError, ValueError):
        raise ValueError("invalid MCP HTTP URL") from None
    secure_remote = parsed.scheme == "https" and bool(parsed.hostname)
    local_http = (
        parsed.scheme == "http"
        and parsed.hostname in _LOOPBACK
        and port is not None
        and 1 <= port <= 65535
    )
    if (
        not (secure_remote or local_http)
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid MCP HTTP URL")


def _validate_filters(
    include: Optional[list[str]],
    exclude: list[str],
) -> None:
    for values in (include, exclude):
        if values is None:
            continue
        if (
            not isinstance(values, list)
            or len(values) > 1_000
            or any(
                not isinstance(value, str)
                or not 1 <= len(value) <= 256
                for value in values
            )
        ):
            raise ValueError("invalid MCP tool filter")
