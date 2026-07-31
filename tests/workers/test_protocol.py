from pathlib import Path

import pytest

from runtime.workers import (
    PROTOCOL_VERSION,
    REQUIRED_CAPABILITIES,
    WorkerHello,
    WorkerProtocolError,
    negotiate,
)
from runtime.workers.protocol import normalize_persisted_version
from runtime.workers.protocol import RemoteLeaseAuthority


def test_remote_lease_is_bound_to_worker_revision_and_capabilities():
    authority = RemoteLeaseAuthority(b"x" * 32, now=lambda: 100)
    lease = authority.issue(
        worker_id="worker-abc",
        revision="a" * 40,
        capabilities=REQUIRED_CAPABILITIES,
        connection_fingerprint="c" * 64,
        ttl_seconds=60,
    )

    assert authority.attest(
        lease.token,
        worker_id="worker-abc",
        revision="a" * 40,
        capabilities=REQUIRED_CAPABILITIES,
        connection_fingerprint="c" * 64,
        now=120,
    ) == lease
    with pytest.raises(WorkerProtocolError):
        authority.attest(
            lease.token,
            worker_id="worker-abc",
            revision="a" * 40,
            capabilities=REQUIRED_CAPABILITIES,
            connection_fingerprint="c" * 64,
            now=120,
        )

    with pytest.raises(WorkerProtocolError):
        authority.issue(
            worker_id="worker-abc", revision="z" * 40,
            capabilities=REQUIRED_CAPABILITIES, connection_fingerprint="c" * 64,
            ttl_seconds=60,
        )
    expired = authority.issue(
        worker_id="worker-abc", revision="a" * 40,
        capabilities=REQUIRED_CAPABILITIES, connection_fingerprint="c" * 64,
        ttl_seconds=60,
    )
    with pytest.raises(WorkerProtocolError):
        authority.attest(
            expired.token,
            worker_id="worker-abc",
            revision="b" * 40,
            capabilities=REQUIRED_CAPABILITIES,
            connection_fingerprint="c" * 64,
            now=161,
        )


def test_worker_protocol_negotiates_required_local_capabilities():
    assert PROTOCOL_VERSION == "harness.subagent.v1"
    capabilities = REQUIRED_CAPABILITIES | {"events.stream"}

    negotiated = negotiate(
        WorkerHello(
            version=PROTOCOL_VERSION,
            worker_kind="local",
            capabilities=capabilities,
        )
    )

    assert negotiated == capabilities


def test_legacy_persisted_worker_records_upgrade_but_handshakes_do_not():
    assert normalize_persisted_version("codinal.worker.v1") == PROTOCOL_VERSION
    with pytest.raises(WorkerProtocolError):
        negotiate(
            WorkerHello(
                version="codinal.worker.v1",
                worker_kind="local",
                capabilities=REQUIRED_CAPABILITIES,
            )
        )


def test_release_script_copies_the_canonical_runtime_tree() -> None:
    release_script = (
        Path(__file__).resolve().parents[2] / "scripts/build-macos-release.sh"
    ).read_text(encoding="utf-8")
    assert 'ditto "$ROOT/runtime" "$BUILD_DIR/resources/runtime/runtime"' in release_script


@pytest.mark.parametrize(
    "hello",
    [
        WorkerHello(
            version="harness.subagent.v2",
            worker_kind="local",
            capabilities=REQUIRED_CAPABILITIES,
        ),
        WorkerHello(
            version=PROTOCOL_VERSION,
            worker_kind="browser",
            capabilities=REQUIRED_CAPABILITIES,
        ),
        WorkerHello(
            version=PROTOCOL_VERSION,
            worker_kind="remote",
            capabilities=REQUIRED_CAPABILITIES - {"task.cancel"},
        ),
        WorkerHello(
            version=PROTOCOL_VERSION,
            worker_kind="local",
            capabilities=REQUIRED_CAPABILITIES | {"INVALID CAPABILITY"},
        ),
    ],
)
def test_worker_protocol_fails_closed(hello):
    with pytest.raises(WorkerProtocolError):
        negotiate(hello)
