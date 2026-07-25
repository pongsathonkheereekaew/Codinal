"""Repo-root pytest conftest.

Presence at repo root makes pytest put the repo root on sys.path, so the
``runtime`` package (Codinal Python sidecar) and ``harness`` content are
importable from tests. Per-package fixtures live under tests/<area>/.
"""
