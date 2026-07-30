from runtime.integrations import render_actions


def test_renderer_emits_only_host_supported_logical_actions():
    rendered = render_actions(
        {"assets": {"skills": [{"name": "review", "content": "Review."}], "mcp": [{"name": "remote", "url": "https://example.test/mcp"}]}},
        supported={"skills"},
    )

    assert rendered.actions == ({"kind": "skills", "name": "review", "content": "Review."},)
    assert rendered.diagnostics == ("host does not support integration action: mcp",)
