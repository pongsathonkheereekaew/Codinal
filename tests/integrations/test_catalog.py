import json

import pytest

from runtime.integrations import IntegrationCatalog


def _manifest(**overrides):
    value = {
        "schema": "codinal.integration.v1",
        "id": "acme/reviewer",
        "publisher": "acme",
        "version": "1.0.0",
        "requested_permissions": ["read"],
        "host_requirements": ["skill_discovery"],
        "model_requirements": [],
        "assets": {"skills": [{"name": "review", "content": "Review."}]},
    }
    value.update(overrides)
    return value


def _provenance():
    return {"source": "fixture", "issuer": "acme", "signature": "fixture-signature"}


def test_activate_writes_immutable_versioned_catalog_and_derived_index(tmp_path):
    catalog = IntegrationCatalog(tmp_path)

    record = catalog.stage_and_activate(_manifest(), provenance=_provenance())

    assert record.status == "enabled-compatible"
    assert record.digest.startswith("sha256:")
    assert record.path == tmp_path / "acme" / "reviewer" / "1.0.0"
    assert json.loads((record.path / "integration.json").read_text())["schema"] == "codinal.integration.v1"
    assert catalog.get("acme/reviewer", "1.0.0") == record
    with pytest.raises(FileExistsError, match="immutable"):
        catalog.stage_and_activate(_manifest(), provenance=_provenance())


def test_rebuilds_derived_index_from_canonical_catalog_and_rolls_back_failed_stage(tmp_path):
    catalog = IntegrationCatalog(tmp_path)
    record = catalog.stage_and_activate(_manifest(), provenance=_provenance())
    catalog.close()
    (tmp_path / ".catalog-index.sqlite3").unlink()

    reopened = IntegrationCatalog(tmp_path)
    assert reopened.get("acme/reviewer", "1.0.0") == record
    with pytest.raises(ValueError, match="schema must be codinal.integration.v1"):
        reopened.stage_and_activate(_manifest(schema="invalid"), provenance=_provenance())
    assert not list((tmp_path / ".staging").iterdir())
    reopened.close()


def test_rejects_catalog_identity_that_can_escape_its_publisher_directory(tmp_path):
    catalog = IntegrationCatalog(tmp_path)
    with pytest.raises(ValueError, match="publisher must contain one safe name segment"):
        catalog.stage_and_activate(_manifest(publisher="../acme"), provenance=_provenance())
    catalog.close()


def test_rejects_unsafe_version_and_tampered_catalog_content(tmp_path):
    catalog = IntegrationCatalog(tmp_path)
    with pytest.raises(ValueError, match="version must contain one safe name segment"):
        catalog.stage_and_activate(_manifest(version="../outside"), provenance=_provenance())
    record = catalog.stage_and_activate(_manifest(), provenance=_provenance())
    (record.path / "integration.json").write_text(json.dumps(_manifest(assets={"hooks": []})))
    catalog.close()
    with pytest.raises(ValueError, match="unsupported executable content"):
        IntegrationCatalog(tmp_path)
