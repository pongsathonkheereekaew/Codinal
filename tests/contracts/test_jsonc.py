"""JSONC editor contract — comment preservation, insert/replace, malformed
rejection. Independent of any adapter."""
from __future__ import annotations

import pytest

from lib import jsonc


def test_strip_comments_outside_strings():
    text = '{\n  // line\n  "a": "http://x", /* block */ "b": 1\n}\n'
    obj = jsonc.loads(text)
    assert obj == {"a": "http://x", "b": 1}


def test_malformed_raises():
    with pytest.raises(jsonc.JsoncError):
        jsonc.loads('{ "a" 1 }')


def test_insert_preserves_comments_and_order():
    text = ('{\n'
            '  // top comment\n'
            '  "$schema": "https://opencode.ai/config.json",\n'
            '  "name": "orig"\n'
            '}\n')
    out = jsonc.insert_top_level_key(text, "permission", {"*": "ask"})
    assert "// top comment" in out
    assert '"$schema": "https://opencode.ai/config.json"' in out
    assert '"name": "orig"' in out
    assert '"permission"' in out
    # $schema must still come before permission (order preserved)
    assert out.index("$schema") < out.index("permission")
    assert jsonc.loads(out)["permission"] == {"*": "ask"}


def test_insert_into_empty_object():
    out = jsonc.insert_top_level_key("{}", "permission", {"read": "allow"})
    assert jsonc.loads(out) == {"permission": {"read": "allow"}}


def test_insert_existing_key_raises():
    with pytest.raises(jsonc.JsoncError):
        jsonc.insert_top_level_key('{"a": 1}', "a", 2)


def test_replace_value_preserves_siblings_and_comments():
    text = ('{\n  // c\n  "a": 1,\n  "b": 2\n}\n')
    out = jsonc.replace_top_level_key(text, "b", {"x": "y"})
    assert "// c" in out
    assert '"a": 1' in out
    assert jsonc.loads(out) == {"a": 1, "b": {"x": "y"}}


def test_set_inserts_when_absent_replaces_when_present():
    base = '{"a": 1}'
    one = jsonc.set_top_level_key(base, "permission", {"*": "ask"})
    assert jsonc.loads(one) == {"a": 1, "permission": {"*": "ask"}}
    two = jsonc.set_top_level_key(one, "permission", {"*": "deny"})
    assert jsonc.loads(two) == {"a": 1, "permission": {"*": "deny"}}


def test_nested_object_value_span_detected():
    # ensure brace-aware span detection (not fooled by nested {} or commas)
    text = ('{\n'
            '  "permission": {\n'
            '    "*": "ask",\n'
            '    "bash": {"*": "ask", "rm *": "deny"}\n'
            '  },\n'
            '  "name": "x"\n'
            '}\n')
    out = jsonc.replace_top_level_key(text, "name", "y")
    parsed = jsonc.loads(out)
    assert parsed["permission"]["bash"]["rm *"] == "deny"
    assert parsed["name"] == "y"
