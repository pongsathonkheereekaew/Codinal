from runtime.policy import RiskClass
from runtime.sessions import RootDir
from runtime.tools import (
    build_core_registry,
    register_interaction_tools,
)


def test_interaction_tools_are_manifest_bound_with_intrinsic_risk(tmp_path):
    registry = build_core_registry(
        [RootDir(tmp_path, writable=True)]
    )

    register_interaction_tools(registry)

    assert registry.names()[-3:] == [
        "ask_user",
        "propose_plan",
        "request_directory",
    ]
    for name, risk in {
        "ask_user": RiskClass.READ,
        "propose_plan": RiskClass.EXTERNAL,
        "request_directory": RiskClass.EXTERNAL,
    }.items():
        spec = registry.get(name)
        assert spec is not None
        assert spec.metadata.risk is risk
        assert spec.metadata.category == "interactive"
        assert (
            spec.schema["function"]["parameters"][
                "additionalProperties"
            ]
            is False
        )
