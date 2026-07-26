import pytest

from runtime.workers import (
    PROTOCOL_VERSION,
    REQUIRED_CAPABILITIES,
    WorkerHello,
    WorkerProtocolError,
    negotiate,
)


def test_worker_protocol_negotiates_required_local_capabilities():
    capabilities = REQUIRED_CAPABILITIES | {"events.stream"}

    negotiated = negotiate(
        WorkerHello(
            version=PROTOCOL_VERSION,
            worker_kind="local",
            capabilities=capabilities,
        )
    )

    assert negotiated == capabilities


@pytest.mark.parametrize(
    "hello",
    [
        WorkerHello(
            version="codinal.worker.v2",
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
