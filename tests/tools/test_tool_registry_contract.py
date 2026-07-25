import pytest

from runtime.policy import ToolManifest
from runtime.tools import ToolRegistry


READ_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
}


def test_registry_accepts_only_manifest_declared_explicit_schema() -> None:
    registry = ToolRegistry(ToolManifest())

    def read_file(path):
        return {"path": path}

    spec = registry.register(read_file, schema=READ_SCHEMA)

    assert spec.name == "read_file"
    assert registry.names() == ["read_file"]
    assert registry.schemas() == [READ_SCHEMA]
    assert registry.execute("read_file", {"path": "README.md"}) == {
        "path": "README.md"
    }


def test_registry_rejects_undeclared_tools_and_schema_name_mismatch() -> None:
    registry = ToolRegistry(ToolManifest())

    def hidden_tool():
        return None

    with pytest.raises(ValueError, match="^tool is not declared in manifest$"):
        registry.register(
            hidden_tool,
            schema={
                "type": "function",
                "function": {
                    "name": "hidden_tool",
                    "description": "hidden",
                    "parameters": {"type": "object"},
                },
            },
        )

    def read_file(path):
        return path

    mismatch = {
        **READ_SCHEMA,
        "function": {**READ_SCHEMA["function"], "name": "other"},
    }
    with pytest.raises(ValueError, match="^invalid tool schema$"):
        registry.register(read_file, schema=mismatch)


def test_registry_rejects_duplicate_registration_and_unknown_execution() -> None:
    registry = ToolRegistry(ToolManifest())

    def read_file(path):
        return path

    registry.register(read_file, schema=READ_SCHEMA)
    with pytest.raises(ValueError, match="^tool already registered$"):
        registry.register(read_file, schema=READ_SCHEMA)
    with pytest.raises(KeyError, match="Tool not registered"):
        registry.execute("write_file", {})
