import pytest

from runtime.plans import (
    LEGACY_VERIFICATION_PLACEHOLDER,
    PlanApproval,
    PlanContent,
)


def test_plan_requires_unique_tasks_with_verification():
    with pytest.raises(ValueError):
        PlanContent.parse({"plan": "No tasks", "tasks": []})
    with pytest.raises(ValueError):
        PlanContent.parse(
            {
                "plan": "Duplicate",
                "tasks": [
                    {
                        "id": "same",
                        "title": "First",
                        "verification": "First check",
                    },
                    {
                        "id": "same",
                        "title": "Second",
                        "verification": "Second check",
                    },
                ],
            }
        )


def test_plan_approval_materializes_only_selected_tasks():
    current = {
        "plan": "Two tasks",
        "tasks": [
            {
                "id": "one",
                "title": "One",
                "verification": "One passes",
            },
            {
                "id": "two",
                "title": "Two",
                "verification": "Two passes",
            },
        ],
    }

    response = PlanApproval.parse(
        {
            "approved": True,
            "mode": "interactive",
            "selected_task_ids": ["two"],
        },
        current,
    ).to_response()

    assert response["selected_task_ids"] == ["two"]
    assert response["selected_tasks"] == [current["tasks"][1]]


def test_legacy_plan_placeholder_cannot_be_approved():
    with pytest.raises(ValueError):
        PlanApproval.parse(
            {
                "approved": True,
                "selected_task_ids": ["legacy-plan"],
            },
            {
                "plan": "Legacy plan",
                "tasks": [
                    {
                        "id": "legacy-plan",
                        "title": "Legacy plan",
                        "verification": (
                            LEGACY_VERIFICATION_PLACEHOLDER
                        ),
                    }
                ],
            },
        )
