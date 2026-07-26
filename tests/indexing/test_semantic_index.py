import os
import sqlite3
import subprocess
import threading
import time

import runtime.indexing.semantic as semantic_module
from runtime.indexing import SemanticIndexService


def _git_repo(path):
    path.mkdir()
    subprocess.run(["git", "-C", path, "init", "-q"], check=True)
    return path


def _root(path):
    metadata = path.stat()
    return {
        "path": str(path),
        "label": path.name,
        "available": True,
        "_device": metadata.st_dev,
        "_inode": metadata.st_ino,
    }


def test_local_index_retrieves_synonyms_without_storing_source(tmp_path):
    root = _git_repo(tmp_path / "repo")
    source = root / "auth.py"
    source.write_text(
        "def remove_expired_tokens():\n"
        "    sensitive_literal_never_persist = 'purge old credentials'\n",
        encoding="utf-8",
    )
    service = SemanticIndexService(tmp_path / "data")

    built = service.rebuild([_root(root)])
    result = service.search(
        [_root(root)],
        query="delete stale authentication",
        limit=10,
    )

    assert built["ok"] is True
    assert built["indexed_files"] == 1
    assert built["indexed_chunks"] == 1
    assert result["matches"][0]["path"] == "auth.py"
    assert result["matches"][0]["line"] == 1
    database = (tmp_path / "data" / "semantic-index.sqlite3").read_bytes()
    assert b"sensitive_literal_never_persist" not in database
    assert b"purge old credentials" not in database


def test_rebuild_removes_deleted_and_ignored_files(tmp_path):
    root = _git_repo(tmp_path / "repo")
    (root / "keep.py").write_text(
        "def build_release():\n    return True\n",
        encoding="utf-8",
    )
    removed = root / "removed.py"
    removed.write_text(
        "def erase_legacy_account():\n    return True\n",
        encoding="utf-8",
    )
    ignored = root / "private.py"
    ignored.write_text("def delete_secret():\n    pass\n", encoding="utf-8")
    (root / ".gitignore").write_text("private.py\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("def delete_external():\n    pass\n", encoding="utf-8")
    os.symlink(outside, root / "linked.py")
    service = SemanticIndexService(tmp_path / "data")

    service.rebuild([_root(root)])
    removed.unlink()
    rebuilt = service.rebuild([_root(root)])
    result = service.search(
        [_root(root)],
        query="delete account secret external",
        limit=10,
    )

    assert rebuilt["indexed_files"] == 1
    assert result["matches"] == []
    status = service.status([_root(root)])
    assert status["roots"][0]["files"] == 1


def test_stale_modified_chunk_is_not_returned_before_rebuild(tmp_path):
    root = _git_repo(tmp_path / "repo")
    source = root / "service.py"
    source.write_text(
        "def authenticate_customer():\n    return True\n",
        encoding="utf-8",
    )
    service = SemanticIndexService(tmp_path / "data")
    service.rebuild([_root(root)])
    source.write_text(
        "def render_dashboard():\n    return True\n",
        encoding="utf-8",
    )

    result = service.search(
        [_root(root)],
        query="login customer",
        limit=10,
    )

    assert result["matches"] == []
    assert result["stale_chunks"] == 1


def test_clear_securely_deletes_root_index(tmp_path):
    root = _git_repo(tmp_path / "repo")
    (root / "service.py").write_text(
        "def repair_database():\n    pass\n",
        encoding="utf-8",
    )
    service = SemanticIndexService(tmp_path / "data")
    service.rebuild([_root(root)])

    cleared = service.clear([_root(root)])

    assert cleared["deleted_roots"] == 1
    assert cleared["deleted_chunks"] == 1
    assert service.status([_root(root)])["state"] == "empty"
    assert service.search(
        [_root(root)],
        query="fix database",
        limit=10,
    )["matches"] == []


def test_incompatible_schema_is_rebuilt_without_retaining_old_bytes(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    database = data / "semantic-index.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE legacy(payload TEXT);
        INSERT INTO legacy VALUES ('legacy_source_must_disappear');
        PRAGMA user_version = 999;
        """
    )
    connection.close()

    service = SemanticIndexService(data)

    assert service.status([])["schema_version"] == 1
    assert b"legacy_source_must_disappear" not in database.read_bytes()


def test_unknown_v0_and_corrupt_databases_are_recreated(tmp_path):
    for name, payload in (
        ("v0", None),
        ("corrupt", b"not a sqlite database legacy_source"),
    ):
        data = tmp_path / name
        data.mkdir()
        database = data / "semantic-index.sqlite3"
        if payload is None:
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE legacy(payload TEXT);
                INSERT INTO legacy VALUES ('v0_source_must_disappear');
                """
            )
            connection.close()
        else:
            database.write_bytes(payload)

        service = SemanticIndexService(data)
        assert service.status([])["schema_version"] == 1
        stored = database.read_bytes()
        assert b"v0_source_must_disappear" not in stored
        assert b"legacy_source" not in stored
        service.close()


def test_database_symlink_is_replaced_without_touching_target(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    outside = tmp_path / "outside.sqlite3"
    outside.write_bytes(b"external data must remain")
    os.symlink(outside, data / "semantic-index.sqlite3")

    service = SemanticIndexService(data)

    assert not service.path.is_symlink()
    assert outside.read_bytes() == b"external data must remain"


def test_malformed_v1_constraints_are_recreated(tmp_path):
    variants = {
        "missing-check": (
            "path TEXT NOT NULL",
            "truncated INTEGER NOT NULL",
            "",
        ),
        "extra-foreign-key": (
            "path TEXT NOT NULL UNIQUE",
            "truncated INTEGER NOT NULL CHECK (truncated IN (0, 1))",
            (
                ", FOREIGN KEY(path) REFERENCES roots(path) "
                "ON DELETE RESTRICT"
            ),
        ),
    }
    for name, (path_column, truncated_column, extra_foreign_key) in (
        variants.items()
    ):
        data = tmp_path / name
        data.mkdir()
        database = data / "semantic-index.sqlite3"
        connection = sqlite3.connect(database)
        connection.executescript(
            f"""
            CREATE TABLE roots (
                root_key TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                {path_column},
                device INTEGER NOT NULL,
                inode INTEGER NOT NULL,
                label TEXT NOT NULL,
                indexed_at REAL NOT NULL,
                files INTEGER NOT NULL,
                chunks INTEGER NOT NULL,
                {truncated_column}
            );
            CREATE TABLE chunks (
                root_key TEXT NOT NULL
                    REFERENCES roots(root_key) ON DELETE CASCADE,
                path TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                digest TEXT NOT NULL,
                vector BLOB NOT NULL,
                PRIMARY KEY (root_key, path, start_line)
                {extra_foreign_key}
            );
            CREATE INDEX chunks_root ON chunks(root_key);
            CREATE INDEX roots_scope_path ON roots(scope, path);
            PRAGMA user_version = 1;
            """
        )
        connection.close()

        service = SemanticIndexService(data)

        roots_sql = service._connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name = 'roots'
            """
        ).fetchone()[0]
        foreign_keys = list(
            service._connection.execute("PRAGMA foreign_key_list(chunks)")
        )
        assert "CHECK (truncated IN (0, 1))" in roots_sql
        assert len(foreign_keys) == 1
        service.close()


def test_partial_first_root_does_not_starve_later_root(tmp_path):
    first = _git_repo(tmp_path / "first")
    second = _git_repo(tmp_path / "second")
    (first / "oversized.txt").write_text(
        "x" * (8 * 1024 + 1),
        encoding="utf-8",
    )
    (second / "service.py").write_text(
        "def repair_authentication():\n    return True\n",
        encoding="utf-8",
    )
    service = SemanticIndexService(tmp_path / "data")

    built = service.rebuild([_root(first), _root(second)])
    status = service.status([_root(first), _root(second)])
    result = service.search(
        [_root(first), _root(second)],
        query="fix login",
        limit=10,
    )

    assert built["indexed_roots"] == 2
    assert status["roots"][0]["state"] == "partial"
    assert status["roots"][1]["state"] == "ready"
    assert result["matches"][0]["path"] == "service.py"


def test_project_status_includes_new_empty_root_and_unavailable_rows(tmp_path):
    first = _git_repo(tmp_path / "first")
    second = _git_repo(tmp_path / "second")
    (first / "service.py").write_text(
        "def repair_database():\n    pass\n",
        encoding="utf-8",
    )
    service = SemanticIndexService(tmp_path / "data")
    service.rebuild([_root(first)], scope="session")

    status = service.project_status(
        [_root(first), _root(second)],
        scope="session",
    )
    unavailable = service.project_status([], scope="session")

    assert status["state"] == "partial"
    assert [root["state"] for root in status["roots"]] == ["ready", "empty"]
    assert unavailable["state"] == "partial"
    assert unavailable["roots"][0]["state"] == "unavailable"


def test_recreated_root_replaces_old_scope_path_row(tmp_path):
    root = _git_repo(tmp_path / "repo")
    (root / "old.py").write_text(
        "def repair_old_database():\n    pass\n",
        encoding="utf-8",
    )
    service = SemanticIndexService(tmp_path / "data")
    service.rebuild([_root(root)], scope="session")
    moved = tmp_path / "moved"
    root.rename(moved)
    root.mkdir()
    subprocess.run(["git", "-C", root, "init", "-q"], check=True)
    (root / "new.py").write_text(
        "def repair_new_database():\n    pass\n",
        encoding="utf-8",
    )

    service.rebuild([_root(root)], scope="session")
    status = service.status_scope("session")

    assert len(status["roots"]) == 1
    assert service.search(
        [_root(root)],
        scope="session",
        query="repair new database",
        limit=10,
    )["matches"][0]["path"] == "new.py"


def test_global_chunk_budget_evicts_oldest_indexed_scope(
    tmp_path,
    monkeypatch,
):
    first = _git_repo(tmp_path / "first")
    second = _git_repo(tmp_path / "second")
    (first / "one.py").write_text("def repair_one():\n    pass\n")
    (second / "two.py").write_text("def repair_two():\n    pass\n")
    service = SemanticIndexService(tmp_path / "data")
    monkeypatch.setattr(semantic_module, "_MAX_GLOBAL_CHUNKS", 1)

    service.rebuild([_root(first)], scope="old")
    service.rebuild([_root(second)], scope="new")

    assert service.status_scope("old")["state"] == "empty"
    assert service.status_scope("new")["state"] == "ready"


def test_single_megabyte_line_is_skipped_within_build_budget(tmp_path):
    root = _git_repo(tmp_path / "repo")
    (root / "minified.js").write_text(
        "authentication" * 70_000,
        encoding="utf-8",
    )
    service = SemanticIndexService(tmp_path / "data")

    started = time.monotonic()
    built = service.rebuild([_root(root)])

    assert time.monotonic() - started < 2
    assert built["indexed_chunks"] == 0
    assert built["truncated"] is True


def test_query_reads_each_ranked_file_once(tmp_path, monkeypatch):
    root = _git_repo(tmp_path / "repo")
    (root / "large.py").write_text(
        "\n".join(
            f"repair_authentication_database_{index} = True"
            for index in range(7_200)
        ),
        encoding="utf-8",
    )
    service = SemanticIndexService(tmp_path / "data")
    service.rebuild([_root(root)])
    calls = 0
    original = semantic_module._read_file_bounded

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(semantic_module, "_read_file_bounded", counted)
    result = service.search(
        [_root(root)],
        query="fix login database",
        limit=100,
    )

    assert result["count"] == 100
    assert result["files_scanned"] == 1
    assert calls == 1


def test_query_deadline_bounds_database_lock_wait(tmp_path):
    root = _git_repo(tmp_path / "repo")
    service = SemanticIndexService(tmp_path / "data")
    locked = threading.Event()
    release = threading.Event()

    def hold_lock():
        with service._lock:
            locked.set()
            release.wait(timeout=1)

    holder = threading.Thread(target=hold_lock)
    holder.start()
    assert locked.wait(timeout=1)
    started = time.monotonic()
    result = service.search(
        [_root(root)],
        query="repair",
        limit=10,
        deadline=time.monotonic() + 0.1,
    )
    elapsed = time.monotonic() - started
    release.set()
    holder.join(timeout=1)

    assert elapsed < 0.3
    assert result["truncated"] is True


def test_cancelled_rebuild_preserves_previous_complete_root(
    tmp_path,
    monkeypatch,
):
    root = _git_repo(tmp_path / "repo")
    source = root / "service.py"
    source.write_text(
        "\n".join(f"repair_value_{index} = True" for index in range(120)),
        encoding="utf-8",
    )
    service = SemanticIndexService(tmp_path / "data")
    initial = service.rebuild([_root(root)], scope="session")
    initial_chunks = initial["indexed_chunks"]
    cancelled = threading.Event()
    original = semantic_module._embed
    calls = 0

    def cancel_after_first(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        calls += 1
        if calls == 1:
            cancelled.set()
        return result

    monkeypatch.setattr(semantic_module, "_embed", cancel_after_first)
    rebuilt = service.rebuild(
        [_root(root)],
        scope="session",
        cancelled=cancelled.is_set,
    )

    assert initial_chunks >= 3
    assert rebuilt["cancelled"] is True
    assert service.status_scope("session")["roots"][0]["chunks"] == (
        initial_chunks
    )


def test_scopes_isolate_shared_roots_and_rebuild_scrubs_deleted_paths(tmp_path):
    root = _git_repo(tmp_path / "repo")
    sensitive = root / "private_removed_path.py"
    sensitive.write_text(
        "def repair_authentication():\n    return True\n",
        encoding="utf-8",
    )
    service = SemanticIndexService(tmp_path / "data")
    service.rebuild([_root(root)], scope="session-a")
    service.rebuild([_root(root)], scope="session-b")

    service.clear_scope("session-a", paths=[str(root)])
    retained = service.search(
        [_root(root)],
        scope="session-b",
        query="fix login",
        limit=10,
    )
    cleared = service.search(
        [_root(root)],
        scope="session-a",
        query="fix login",
        limit=10,
    )
    sensitive.unlink()
    service.rebuild([_root(root)], scope="session-b")

    assert retained["count"] == 1
    assert cleared["matches"] == []
    artifacts = b""
    for candidate in (
        service.path,
        service.path.with_name(service.path.name + "-wal"),
        service.path.with_name(service.path.name + "-shm"),
    ):
        if candidate.exists():
            artifacts += candidate.read_bytes()
    assert b"private_removed_path.py" not in artifacts


def test_index_build_honors_expired_deadline_without_opening_git(
    tmp_path,
    monkeypatch,
):
    root = _git_repo(tmp_path / "repo")
    service = SemanticIndexService(tmp_path / "data")

    def unexpected_popen(*_args, **_kwargs):
        raise AssertionError("expired index build spawned Git")

    monkeypatch.setattr(subprocess, "Popen", unexpected_popen)
    result = service.rebuild(
        [_root(root)],
        deadline=time.monotonic() - 1,
    )

    assert result["indexed_files"] == 0
    assert result["truncated"] is True
