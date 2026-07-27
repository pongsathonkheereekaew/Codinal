"""Unit tests for the unified-diff hunk parser."""

from __future__ import annotations

import pytest

from runtime.git.diff_parser import parse_diff, reconstruct_patch


SIMPLE_DIFF = """\
diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,4 @@
 line1
+added line
 line2
 line3
@@ -10,3 +11,4 @@
 line10
 line11
+another added line
 line12
"""

MULTI_FILE_DIFF = """\
diff --git a/a.txt b/a.txt
index 1111111..2222222 100644
--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,3 @@
 a1
+a2 added
 a3
diff --git a/b.txt b/b.txt
index 3333333..4444444 100644
--- a/b.txt
+++ b/b.txt
@@ -1,1 +1,2 @@
 b1
+b2 added
"""


def test_parse_single_file_single_hunk() -> None:
    files = parse_diff(SIMPLE_DIFF)
    assert len(files) == 1
    assert files[0].path == "src/app.py"
    assert len(files[0].hunks) == 2
    assert files[0].hunks[0].index == 0
    assert files[0].hunks[1].index == 1
    assert "@@ -1,3 +1,4 @@" in files[0].hunks[0].header
    assert "+added line\n" in files[0].hunks[0].body
    assert "@@ -10,3 +11,4 @@" in files[0].hunks[1].header


def test_parse_multi_file() -> None:
    files = parse_diff(MULTI_FILE_DIFF)
    assert [f.path for f in files] == ["a.txt", "b.txt"]
    assert len(files[0].hunks) == 1
    assert len(files[1].hunks) == 1
    # Hunk index is per-file (resets per file).
    assert files[0].hunks[0].index == 0
    assert files[1].hunks[0].index == 0


def test_reconstruct_selects_one_hunk_of_two() -> None:
    files = parse_diff(SIMPLE_DIFF)
    patch = reconstruct_patch(files, [("src/app.py", 0)])
    # Only the first hunk's added line appears.
    assert "+added line\n" in patch
    assert "+another added line\n" not in patch
    # Header is preserved.
    assert "diff --git a/src/app.py b/src/app.py" in patch
    assert "--- a/src/app.py" in patch
    assert "+++ b/src/app.py" in patch
    # Exactly one hunk header in the reconstructed patch (each ``@@ … @@``
    # header contains two ``@@`` markers, so count by the body line count).
    assert patch.count("\n@@") == 1


def test_reconstruct_selects_hunks_across_files() -> None:
    files = parse_diff(MULTI_FILE_DIFF)
    patch = reconstruct_patch(files, [("a.txt", 0), ("b.txt", 0)])
    assert "+a2 added\n" in patch
    assert "+b2 added\n" in patch
    assert patch.count("diff --git") == 2


def test_reconstruct_preserves_hunk_order_within_file() -> None:
    files = parse_diff(SIMPLE_DIFF)
    # Select both hunks but pass them out of order — output must keep
    # original order (hunk 0 before hunk 1).
    patch = reconstruct_patch(files, [("src/app.py", 1), ("src/app.py", 0)])
    first_hunk_pos = patch.index("@@ -1,3 +1,4 @@")
    second_hunk_pos = patch.index("@@ -10,3 +11,4 @@")
    assert first_hunk_pos < second_hunk_pos


def test_reconstruct_empty_selection_raises() -> None:
    files = parse_diff(SIMPLE_DIFF)
    with pytest.raises(ValueError, match="no hunks selected"):
        reconstruct_patch(files, [])


def test_reconstruct_unknown_path_yields_no_patch() -> None:
    files = parse_diff(SIMPLE_DIFF)
    # A path that doesn't appear in the diff → no hunks → raises.
    with pytest.raises(ValueError, match="no hunks selected"):
        reconstruct_patch(files, [("nonexistent.py", 0)])


def test_parse_empty_string() -> None:
    assert parse_diff("") == []


def test_parse_handles_no_newline_marker() -> None:
    diff = (
        "diff --git a/x.txt b/x.txt\n"
        "index 1..2 100644\n"
        "--- a/x.txt\n"
        "+++ b/x.txt\n"
        "@@ -1 +1,2 @@\n"
        " line1\n"
        "+added\n"
        "\\ No newline at end of file\n"
    )
    files = parse_diff(diff)
    assert len(files[0].hunks) == 1
    assert "\\ No newline at end of file\n" in files[0].hunks[0].body
