import subprocess

import pytest

from runtime.integrations import CodexBackendError, CodexRuntimeBackend


def test_codex_backend_uses_fixed_argv_and_returns_its_own_backend_output(tmp_path):
    calls = []
    def runner(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0, stdout='{"type":"done"}', stderr="")

    backend = CodexRuntimeBackend(runner=runner)
    assert backend.execute("Review this.", workspace=str(tmp_path)) == '{"type":"done"}'
    assert calls[0][0][0] == ["codex", "exec", "--json", "Review this."]
    assert calls[0][1]["shell"] is False


def test_codex_backend_surfaces_a_separate_backend_failure(tmp_path):
    backend = CodexRuntimeBackend(runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout="", stderr="denied"))
    with pytest.raises(CodexBackendError, match="denied"):
        backend.execute("Review this.", workspace=str(tmp_path))
