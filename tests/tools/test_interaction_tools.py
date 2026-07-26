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


def test_plan_tool_exposes_editable_tasks_with_verification_criteria(
    tmp_path,
):
    registry = build_core_registry(
        [RootDir(tmp_path, writable=True)]
    )
    register_interaction_tools(registry)

    plan = registry.get("propose_plan")
    assert plan is not None
    parameters = plan.schema["function"]["parameters"]
    tasks = parameters["properties"]["tasks"]

    assert tasks["type"] == "array"
    assert tasks["minItems"] == 1
    assert tasks["maxItems"] == 20
    assert tasks["items"]["required"] == [
        "id",
        "title",
        "verification",
    ]
    assert tasks["items"]["additionalProperties"] is False
    assert tasks["items"]["properties"]["id"]["pattern"].startswith("^")
    assert tasks["items"]["properties"]["verification"]["maxLength"] == 2048
    assert parameters["required"] == ["plan", "tasks"]
