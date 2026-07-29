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
