"""Provider-neutral runtime contracts and adapters."""

from runtime.policy import ToolCall

from .base import (
    AssistantTurn,
    ModelCapabilities,
    ProviderClient,
    StreamChunk,
)
from .conformance import ProviderConformanceAdapter
from .openai_provider import OpenAIProvider, resolve_api_key

__all__ = [
    "AssistantTurn",
    "ModelCapabilities",
    "OpenAIProvider",
    "ProviderClient",
    "ProviderConformanceAdapter",
    "StreamChunk",
    "ToolCall",
    "resolve_api_key",
]
