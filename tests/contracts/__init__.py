"""Contract tests for the cross-agent capability model.

Seam under test: the adapter's public `provision` / `verify` / `inspect` API,
exercised against an isolated temporary HOME. Tests assert observable
filesystem + config state and CapabilityResult statuses — never adapter
internals. The manifest is the real repo `config/hosts.yaml`.
"""
