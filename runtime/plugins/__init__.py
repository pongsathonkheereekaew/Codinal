"""Declarative, fail-closed plugin translation contracts."""

from runtime.providers import ModelCapabilities

from .translator import (
    CapabilityMatrix,
    IntegrationCompatibilityError,
    IntegrationTranslation,
    PluginCompatibilityError,
    PluginTranslation,
    translate_integration,
    translate_plugin,
)
from .importer import PluginImport, import_plugin

__all__ = [
    "CapabilityMatrix",
    "IntegrationCompatibilityError",
    "IntegrationTranslation",
    "ModelCapabilities",
    "PluginCompatibilityError",
    "PluginTranslation",
    "PluginImport",
    "import_plugin",
    "translate_plugin",
    "translate_integration",
]
