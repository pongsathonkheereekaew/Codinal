"""macOS Seatbelt-backed command execution."""

from .shell import (
    InvalidCommandError,
    SandboxedShell,
    SandboxResult,
    SandboxUnavailableError,
)

__all__ = [
    "InvalidCommandError",
    "SandboxedShell",
    "SandboxResult",
    "SandboxUnavailableError",
]
