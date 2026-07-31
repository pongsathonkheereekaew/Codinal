"""Background worker orchestration contracts."""

from .protocol import (
    PROTOCOL_VERSION,
    REQUIRED_CAPABILITIES,
    WorkerHello,
    RemoteLease,
    RemoteLeaseAuthority,
    RemoteArtifact,
    WorkerProtocolError,
    negotiate,
    verify_remote_artifact,
)
from .models import (
    TERMINAL_WORKER_STATES,
    WorkerRecord,
    WorkerState,
)
from .store import WorkerStore
from .coordinator import WorkerCoordinator, worker_to_dict

__all__ = [
    "PROTOCOL_VERSION",
    "REQUIRED_CAPABILITIES",
    "WorkerHello",
    "RemoteLease",
    "RemoteLeaseAuthority",
    "RemoteArtifact",
    "WorkerRecord",
    "WorkerState",
    "WorkerStore",
    "WorkerCoordinator",
    "TERMINAL_WORKER_STATES",
    "WorkerProtocolError",
    "negotiate",
    "verify_remote_artifact",
    "worker_to_dict",
]
