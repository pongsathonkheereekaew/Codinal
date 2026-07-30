"""Declarative, fail-closed plugin translation contracts."""

from runtime.providers import ModelCapabilities

from .translator import (
    CapabilityMatrix,
    PluginCompatibilityError,
    PluginTranslation,
    translate_plugin,
)
from .importer import PluginImport, import_plugin

__all__ = [
    "CapabilityMatrix",
    "ModelCapabilities",
    "PluginCompatibilityError",
    "PluginTranslation",
    "PluginImport",
    "import_plugin",
    "translate_plugin",
]
