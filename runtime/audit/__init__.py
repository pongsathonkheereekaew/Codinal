"""Tamper-evident audit ledger shared across domains (MCP, workers, ...)."""

from .ledger import AuditLedger

__all__ = ["AuditLedger"]
