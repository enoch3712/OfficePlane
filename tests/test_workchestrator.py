from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pytest

from officeplane.agentic.settings import OrchestrationSettings
from officeplane.agentic.workchestrator import WorkchestratorPlanner
from officeplane.components.planning.models import ActionNode, ActionPlan, GeneratePlanOutput


@dataclass
class FakeGenerator:
    outputs: List[GeneratePlanOutput]
    call_count: int = 0

    async def generate_edit_plan(
        self,
        document_outline: str,
        user_request: str,
        document_id: str,
        document_title: str,
    ) -> GeneratePlanOutput:
        index = min(self.call_count, len(self.outputs) - 1)
        self.call_count += 1
        return self.outputs[index]


def _valid_plan() -> ActionPlan:
    return ActionPlan(
        title="Edit Plan for Sample",
        original_prompt="Add a conclusion.",
        roots=[
            ActionNode(
                id="node_0",
                action_name="add_chapter",
                description="Add conclusion chapter",
                inputs={
                    "document_id": "11111111-1111-1111-1111-111111111111",
                    "title": "Conclusion",
                    "order_index": 2,
                },
            )
        ],
    )


def _invalid_worker_plan() -> ActionPlan:
    return ActionPlan(
        title="Broken Plan",
        original_prompt="Update the document.",
        roots=[
            ActionNode(
                id="node_0",
                action_name="write_page",
                description="Write page without section id",
                inputs={"content": "Missing the target section."},
            )
        ],
    )


def _generator_factory(role_outputs: Dict[str, List[GeneratePlanOutput]]) -> tuple[WorkchestratorPlanner, Dict[str, FakeGenerator]]:
    generators: Dict[str, FakeGenerator] = {}

    def factory(role: str, settings: OrchestrationSettings) -> FakeGenerator:
        if role not in generators:
            generators[role] = FakeGenerator(outputs=role_outputs[role])
        return generators[role]

    return WorkchestratorPlanner(factory), generators


@pytest.mark.asyncio
async def test_workchestrator_accepts_worker_plan():
    worker_output = GeneratePlanOutput(plan=_valid_plan(), success=True, generation_time_ms=12)
    planner, generators = _generator_factory(
        {"worker": [worker_output], "orchestrator": [worker_output]}
    )

    result = await planner.plan_edit(
        document_outline="Document: Sample\n- Chapter 1: Intro",
        document_id="11111111-1111-1111-1111-111111111111",
        document_title="Sample",
        user_request="Add a conclusion chapter.",
        settings=OrchestrationSettings(),
    )

    assert result.success is True
    assert result.orchestration.final_mode == "worker"
    assert result.orchestration.worker_attempts == 1
    assert generators["worker"].call_count == 1


@pytest.mark.asyncio
async def test_workchestrator_takes_over_after_worker_validation_failure():
    worker_output = GeneratePlanOutput(plan=_invalid_worker_plan(), success=True, generation_time_ms=8)
    orchestrator_output = GeneratePlanOutput(plan=_valid_plan(), success=True, generation_time_ms=15)
    planner, generators = _generator_factory(
        {
            "worker": [worker_output, worker_output],
            "orchestrator": [orchestrator_output],
        }
    )
    settings = OrchestrationSettings()
    settings.takeover.max_worker_retries = 0
    settings.takeover.max_validation_issues = 0

    result = await planner.plan_edit(
        document_outline="Document: Sample\n- Chapter 1: Intro",
        document_id="11111111-1111-1111-1111-111111111111",
        document_title="Sample",
        user_request="Update the document with a new summary page.",
        settings=settings,
    )

    assert result.success is True
    assert result.orchestration.final_mode == "orchestrator"
    assert result.orchestration.takeover_reason == "validation_failed"
    assert generators["worker"].call_count == 1
    assert generators["orchestrator"].call_count == 1


@pytest.mark.asyncio
async def test_workchestrator_skips_worker_for_high_complexity_requests():
    orchestrator_output = GeneratePlanOutput(plan=_valid_plan(), success=True, generation_time_ms=20)
    planner, generators = _generator_factory(
        {
            "worker": [GeneratePlanOutput(plan=_valid_plan(), success=True, generation_time_ms=1)],
            "orchestrator": [orchestrator_output],
        }
    )
    settings = OrchestrationSettings()
    settings.takeover.complexity_takeover_threshold = 0.3

    result = await planner.plan_edit(
        document_outline="\n".join(
            [
                "Document: Sample",
                "- Chapter 1: Intro",
                "  - Section 1: Overview",
                "    - Page 1",
                "- Chapter 2: Analysis",
                "  - Section 1: Details",
                "    - Page 1",
            ]
        ),
        document_id="11111111-1111-1111-1111-111111111111",
        document_title="Sample",
        user_request="Rewrite the entire document across all sections and harmonize the structure.",
        settings=settings,
    )

    assert result.success is True
    assert result.orchestration.initial_mode == "takeover"
    assert result.orchestration.final_mode == "orchestrator"
    assert "worker" not in generators or generators["worker"].call_count == 0
    assert generators["orchestrator"].call_count == 1
