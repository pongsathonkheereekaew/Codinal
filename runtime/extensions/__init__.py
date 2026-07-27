"""Extension governance: package manifest + signed provenance registry."""

from .models import ExtensionPackage
from .registry import ExtensionRegistry

__all__ = ["ExtensionPackage", "ExtensionRegistry"]
