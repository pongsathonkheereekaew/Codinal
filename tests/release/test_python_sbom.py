import json

from scripts.generate_python_sbom import build_sbom, components_from_lock


LOCK = """\
alpha_package==1.2.3 \\
    --hash=sha256:aaaaaaaa \\
    --hash=sha256:bbbbbbbb
bravo==2.0.0 \\
    --hash=sha256:cccccccc
"""


def test_sbom_components_are_normalized_and_keep_locked_hashes():
    components = components_from_lock(LOCK)

    assert components[0] == {
        "type": "library",
        "name": "alpha-package",
        "version": "1.2.3",
        "purl": "pkg:pypi/alpha-package@1.2.3",
        "hashes": [
            {"alg": "SHA-256", "content": "aaaaaaaa"},
            {"alg": "SHA-256", "content": "bbbbbbbb"},
        ],
    }
    assert components[1]["purl"] == "pkg:pypi/bravo@2.0.0"


def test_sbom_is_deterministic_cyclonedx_json():
    first = build_sbom(LOCK, "1.2.3")
    second = build_sbom(LOCK, "1.2.3")

    assert first == second
    assert first["bomFormat"] == "CycloneDX"
    assert first["specVersion"] == "1.5"
    assert first["serialNumber"].startswith("urn:uuid:")
    assert first["metadata"]["component"]["version"] == "1.2.3"
    json.dumps(first)
