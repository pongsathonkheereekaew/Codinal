"""JSONC reader + comment-preserving editor.

OpenCode config is JSON-with-comments (`.jsonc`). A naive `json.load` +
`json.dump` round-trip destroys user comments and formatting, which violates
locked decisions #9/#10. This module edits a single top-level key in place,
leaving every other byte (comments, ordering, whitespace) untouched.

Scope: structural editing of *top-level* object keys only — exactly what the
harness needs to manage `permission` / `$schema` / etc. Nested edits are out
of scope; replace the whole top-level value instead.
"""
from __future__ import annotations

import json
from typing import Any

__all__ = ["JsoncError", "loads", "has_top_level_key", "get_top_level_key",
           "set_top_level_key", "insert_top_level_key", "replace_top_level_key"]


class JsoncError(ValueError):
    pass


def _strip(text: str) -> str:
    """Remove // and /* */ comments that are outside strings. Returns text
    suitable for json.loads."""
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    q = ""
    while i < n:
        c = text[i]
        nx = text[i + 1] if i + 1 < n else ""
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(nx)
                i += 2
                continue
            if c == q:
                in_str = False
            i += 1
            continue
        if c in '"\'':
            in_str = True
            q = c
            out.append(c)
            i += 1
            continue
        if c == "/" and nx == "/":
            j = text.find("\n", i)
            if j == -1:
                break
            i = j  # keep newline
            continue
        if c == "/" and nx == "*":
            j = text.find("*/", i + 2)
            if j == -1:
                raise JsoncError("unterminated block comment")
            i = j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def loads(text: str) -> Any:
    try:
        return json.loads(_strip(text))
    except json.JSONDecodeError as e:
        raise JsoncError(f"invalid JSONC: {e}") from e


def has_top_level_key(text: str, key: str) -> bool:
    obj = loads(text)
    return isinstance(obj, dict) and key in obj


def get_top_level_key(text: str, key: str) -> tuple[bool, Any]:
    obj = loads(text)
    if isinstance(obj, dict) and key in obj:
        return True, obj[key]
    return False, None


def _value_end(text: str, i: int) -> int:
    """Index just past a JSON value starting at/after offset i (skipping ws)."""
    n = len(text)
    while i < n and text[i] in " \t\r\n":
        i += 1
    if i >= n:
        return i
    c = text[i]
    if c in "{[":
        open_ch = c
        close_ch = "}" if c == "{" else "]"
        depth = 0
        in_str = False
        q = ""
        while i < n:
            ch = text[i]
            nx = text[i + 1] if i + 1 < n else ""
            if in_str:
                if ch == "\\" and i + 1 < n:
                    i += 2
                    continue
                if ch == q:
                    in_str = False
                i += 1
                continue
            if ch == "/" and nx == "/":
                j = text.find("\n", i)
                i = n if j == -1 else j + 1
                continue
            if ch == "/" and nx == "*":
                j = text.find("*/", i + 2)
                if j == -1:
                    return n
                i = j + 2
                continue
            if ch in '"\'':
                in_str = True
                q = ch
                i += 1
                continue
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return i
    if c in '"\'':
        q = c
        i += 1
        while i < n:
            ch = text[i]
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == q:
                return i + 1
            i += 1
        return i
    # number / keyword / null
    while i < n and text[i] not in ",}]\t\r\n ":
        i += 1
    return i


def _locate_key(text: str, key: str) -> tuple[int, int, int, int] | None:
    """Find a top-level (depth-1) object key.

    Returns (key_start, colon_after, value_end, span_end_incl_comma) or None.
    span_end_incl_comma includes an optional trailing comma + trailing ws so a
    caller can delete the whole statement cleanly.
    """
    i, n = 0, len(text)
    depth = 0
    in_str = False
    q = ""
    needle = json.dumps(key)
    while i < n:
        c = text[i]
        nx = text[i + 1] if i + 1 < n else ""
        if in_str:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == q:
                in_str = False
            i += 1
            continue
        if c == "/" and nx == "/":
            j = text.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        if c == "/" and nx == "*":
            j = text.find("*/", i + 2)
            if j == -1:
                return None
            i = j + 2
            continue
        if c in '"\'':
            in_str = True
            q = c
            if depth == 1 and c == '"' and text.startswith(needle, i):
                # needle already includes both quotes; end_q sits just past the
                # closing quote (verified by startswith).
                end_q = i + len(needle)
                k = end_q
                while k < n and text[k] in " \t\r\n":
                    k += 1
                if k < n and text[k] == ":":
                    value_start = k + 1
                    value_end = _value_end(text, value_start)
                    tail = value_end
                    while tail < n and text[tail] in " \t\r\n":
                        tail += 1
                    span_end = tail + 1 if tail < n and text[tail] == "," else value_end
                    return (i, k + 1, value_end, span_end)
            i += 1
            continue
        if c in "{[":
            depth += 1
            i += 1
            continue
        if c in "}]":
            depth -= 1
            i += 1
            continue
        i += 1
    return None


def _line_indent(text: str, pos: int) -> str:
    line_start = text.rfind("\n", 0, pos) + 1
    indent = []
    j = line_start
    while j < pos and text[j] in " \t":
        indent.append(text[j])
        j += 1
    return "".join(indent)


def _serialize_value(value: Any, indent: str) -> str:
    """Pretty value: first line bare, following lines indented by indent."""
    raw = json.dumps(value, indent=2, ensure_ascii=False)
    lines = raw.split("\n")
    if len(lines) == 1:
        return lines[0]
    out = [lines[0]]
    for ln in lines[1:]:
        out.append((indent + "  " + ln[2:]) if ln.startswith("  ") else (indent + ln))
    return "\n".join(out)


def _last_close_brace(text: str) -> int:
    """Index of the closing brace of the root object, or -1."""
    i, n = 0, len(text)
    depth = 0
    in_str = False
    q = ""
    last = -1
    while i < n:
        c = text[i]
        nx = text[i + 1] if i + 1 < n else ""
        if in_str:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == q:
                in_str = False
            i += 1
            continue
        if c == "/" and nx == "/":
            j = text.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        if c == "/" and nx == "*":
            j = text.find("*/", i + 2)
            if j == -1:
                break
            i = j + 2
            continue
        if c in '"\'':
            in_str = True
            q = c
            i += 1
            continue
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0 and c == "}":
                last = i
        i += 1
    return last


def _ensure_root_object(text: str) -> str:
    stripped = _strip(text).strip()
    if stripped:
        # validate
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as e:
            raise JsoncError(f"invalid JSONC: {e}") from e
        if not isinstance(obj, dict):
            raise JsoncError("root is not a JSON object")
        return text
    return "{}"


def insert_top_level_key(text: str, key: str, value: Any) -> str:
    """Insert a new top-level key. Raises if the key already exists or the
    document is malformed. Preserves all comments/formatting elsewhere."""
    text = _ensure_root_object(text)
    if has_top_level_key(text, key):
        raise JsoncError(f"key already present: {key}")
    close = _last_close_brace(text)
    if close == -1:
        # empty document -> seed
        indent = ""
        block = "{\n" + indent + "  " + json.dumps(key) + ": " + _serialize_value(value, indent + "  ") + "\n}"
        return block
    insert_at = close
    indent = _line_indent(text, close)
    # find end of the last non-ws content before close
    k = close - 1
    while k >= 0 and text[k] in " \t\r\n":
        k -= 1
    need_comma = k >= 0 and text[k] not in "{,"
    serialized = _serialize_value(value, indent + "  ")
    new_line = "\n" + indent + "  " + json.dumps(key) + ": " + serialized
    if need_comma:
        new_text = text[:k + 1] + "," + new_line + text[k + 1:insert_at] + text[insert_at:]
    else:
        # object was empty `{}`
        new_text = text[:insert_at] + new_line + "\n" + indent + text[insert_at:]
    # validate result
    loads(new_text)
    return new_text


def replace_top_level_key(text: str, key: str, value: Any) -> str:
    """Replace an existing top-level key's value in place. Raises if absent."""
    text = _ensure_root_object(text)
    loc = _locate_key(text, key)
    if loc is None:
        raise JsoncError(f"key not present: {key}")
    _key_start, colon_after, value_end, _span_end = loc
    indent = _line_indent(text, _key_start)
    serialized = _serialize_value(value, indent + "  ")
    # Splice only the value region; text[value_end:] already carries the
    # original trailing comma (or none, if this was the last entry).
    new_text = text[:colon_after] + " " + serialized + text[value_end:]
    loads(new_text)
    return new_text


def set_top_level_key(text: str, key: str, value: Any) -> str:
    """Insert or replace a top-level key. Caller should detect value-conflicts
    before replacing user data (see merge policy)."""
    if has_top_level_key(text, key):
        return replace_top_level_key(text, key, value)
    return insert_top_level_key(text, key, value)
