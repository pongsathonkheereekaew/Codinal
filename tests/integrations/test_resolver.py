import pytest

from runtime.integrations import IntegrationCatalog, IntegrationResolutionError, IntegrationResolver
from runtime.plugins import CapabilityMatrix


def _manifest():
    return {
        "schema": "codinal.integration.v1", "id": "acme/review", "publisher": "acme", "version": "1.0.0",
        "requested_permissions": ["read"], "host_requirements": ["skill_discovery"], "model_requirements": ["tools"],
        "assets": {"skills": [{"name": "review", "content": "Review."}]},
    }


def test_resolver_blocks_ungranted_permissions_then_returns_verified_catalog_entry(tmp_path):
    catalog = IntegrationCatalog(tmp_path)
    catalog.stage_and_activate(_manifest(), provenance={"source": "fixture", "issuer": "acme", "signature": "test"})
    matrix = CapabilityMatrix.from_host_manifest({"hosts": {"opencode": {"capabilities": {"skill_discovery": {"status": "supported"}}}}})
    resolver = IntegrationResolver(catalog, matrix, host="opencode")
    requested = [{"id": "acme/review", "version": "1.0.0"}]

    with pytest.raises(IntegrationResolutionError, match="permissions not granted"):
        resolver.resolve(requested, model="openai:gpt-5.6", granted_permissions=set())
    assert resolver.resolve(requested, model="openai:gpt-5.6", granted_permissions={"read"})[0].record.integration_id == "acme/review"


def test_resolver_rejects_non_dispatchable_catalog_status(tmp_path):
    catalog = IntegrationCatalog(tmp_path)
    catalog.stage_and_activate(_manifest(), provenance={"source": "fixture", "issuer": "acme", "signature": "test"}, status="rejected", diagnostics=("policy denied",))
    resolver = IntegrationResolver(catalog, CapabilityMatrix.from_host_manifest({"hosts": {}}), host="opencode")
    with pytest.raises(IntegrationResolutionError, match="not dispatchable"):
        resolver.resolve([{"id": "acme/review", "version": "1.0.0"}], model="openai:gpt-5.6", granted_permissions={"read"})
