"""First-party, explicit Codex runtime backend for a ``codex_runtime`` action."""
from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Callable


class CodexBackendError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class CodexRuntimeBackend:
    executable: str = "codex"
    timeout_seconds: float = 120.0
    runner: Runner = subprocess.run

    def execute(self, prompt: str, *, workspace: str) -> str:
        """Invoke Codex as a distinct backend through a fixed argv contract."""
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("codex_runtime prompt must be non-empty")
        completed = self.runner(
            [self.executable, "exec", "--json", prompt],
            cwd=workspace,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            raise CodexBackendError(completed.stderr.strip() or "codex_runtime failed")
        return completed.stdout
