import json

import pytest

from runtime.plugins import import_plugin


def test_imports_codex_skills_and_reports_hooks(tmp_path):
    (tmp_path / ".codex-plugin").mkdir()
    (tmp_path / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "portable", "version": "1.0.0", "author": {"name": "acme"}})
    )
    skill = tmp_path / "skills" / "review"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: review\ndescription: Review\n---\nReview carefully.")
    (tmp_path / "hooks").mkdir()

    result = import_plugin(tmp_path, host="codex")

    assert result.status == "translated_with_gaps"
    assert result.manifest["schema"] == "codinal.integration.v1"
    assert result.manifest["assets"]["skills"][0]["name"] == "review"
    assert result.diagnostics == ("rejected executable plugin content: hooks",)


def test_rejects_unknown_plugin_host(tmp_path):
    with pytest.raises(ValueError, match="unsupported plugin host: cursor"):
        import_plugin(tmp_path, host="cursor")
