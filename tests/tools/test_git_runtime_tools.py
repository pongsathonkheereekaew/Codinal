from pathlib import Path

from runtime.policy import RiskClass, ToolManifest
from runtime.sessions import RootDir
from runtime.tools import (
    build_core_registry,
    register_git_tools,
)


class FakeGit:
    def __init__(self):
        self.calls = []

    def status(self, session_id):
        self.calls.append(("status", session_id))
        return {"ok": True, "clean": False}

    def diff(
        self,
        session_id,
        *,
        staged=False,
        against_base=False,
        path=None,
    ):
        self.calls.append(
            ("diff", session_id, staged, against_base, path)
        )
        return {"ok": True, "diff": "patch"}

    def stage(self, session_id, path="."):
        self.calls.append(("stage", session_id, path))
        return {"ok": True, "path": path}

    def commit(self, session_id, message):
        self.calls.append(("commit", session_id, message))
        return {"ok": True, "commit": "a" * 40}


def test_registers_manifest_risk_and_forwards_session_bound_git_calls(
    tmp_path: Path,
) -> None:
    registry = build_core_registry(
        [RootDir(tmp_path, writable=True)],
        manifest=ToolManifest(),
    )
    service = FakeGit()
    register_git_tools(
        registry,
        service=service,
        session_id="session-1",
    )

    assert registry.execute("git_status") == {"ok": True, "clean": False}
    assert registry.execute(
        "git_diff",
        {"staged": True, "path": "file.py"},
    ) == {"ok": True, "diff": "patch"}
    assert registry.execute(
        "git_stage",
        {"path": "file.py"},
    ) == {"ok": True, "path": "file.py"}
    assert registry.execute(
        "git_commit",
        {"message": "Commit message"},
    ) == {"ok": True, "commit": "a" * 40}
    assert service.calls == [
        ("status", "session-1"),
        ("diff", "session-1", True, False, "file.py"),
        ("stage", "session-1", "file.py"),
        ("commit", "session-1", "Commit message"),
    ]
    for name, risk in {
        "git_status": RiskClass.READ,
        "git_diff": RiskClass.READ,
        "git_stage": RiskClass.WRITE_LOCAL,
        "git_commit": RiskClass.WRITE_LOCAL,
    }.items():
        spec = registry.get(name)
        assert spec is not None
        assert spec.metadata.risk is risk
        assert (
            spec.schema["function"]["parameters"]["additionalProperties"]
            is False
        )
