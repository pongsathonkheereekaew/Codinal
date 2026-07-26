"""Host adapters — render capability manifest into host-real files.

One module per host. Each adapter resolves the host's paths, links policy /
enabled skills / commands, merges native permissions, and returns structured
CapabilityResult verification. Unsupported features are reported, never
silently skipped (locked decision #6).
"""
