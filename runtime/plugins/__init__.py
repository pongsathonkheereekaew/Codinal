"""Declarative, fail-closed plugin translation contracts."""

from runtime.providers import ModelCapabilities

from .translator import (
    CapabilityMatrix,
    PluginCompatibilityError,
    PluginTranslation,
    translate_plugin,
)

__all__ = [
    "CapabilityMatrix",
    "ModelCapabilities",
    "PluginCompatibilityError",
    "PluginTranslation",
    "translate_plugin",
]
