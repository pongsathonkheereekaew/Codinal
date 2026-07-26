"""Stable durable-state startup errors."""


class UnsupportedSchemaVersionError(RuntimeError):
    """A durable store was written by a newer, incompatible Codinal."""


class ExportTooLargeError(RuntimeError):
    """A conversation export exceeds its memory safety bound."""
