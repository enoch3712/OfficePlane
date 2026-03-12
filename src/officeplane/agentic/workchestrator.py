"""
Workchestrator planning service.

Applies an explicit plan/delegate/review/takeover state machine on top of the
existing ActionPlan generator so document edits remain structured and auditable.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from officeplane.agentic.settings import OrchestrationSettings
from officeplane.components.planning.generator import PlanGenerator
from officeplane.components.planning.models import ActionPlan, GeneratePlanOutput


class WorkchestratorState(str, Enum):
    RECEIVED = "RECEIVED"
    ANALYZED = "ANALYZED"
    PLANNED = "PLANNED"
    DISPATCHED = "DISPATCHED"
    WORKER_DONE = "WORKER_DONE"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    TAKEN_OVER_BY_ORCHESTRATOR = "TAKEN_OVER_BY_ORCHESTRATOR"
    COMPLETED = "COMPLETED"


class StateTransition(BaseModel):
    state: WorkchestratorState
    action: str
    reason: str = ""
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkchestratorSummary(BaseModel):
    strategy: str = "workchestrator"
    enabled: bool = True
    initial_mode: str
    final_mode: str
    delegated: bool
    worker_attempts: int = 0
    worker_confidence: Optional[float] = None
    takeover_reason: Optional[str] = None
    signals: Dict[str, Any] = Field(default_factory=dict)
    validation_issues: List[str] = Field(default_factory=list)
    transitions: List[StateTransition] = Field(default_factory=list)
    settings_snapshot: Dict[str, Any] = Field(default_factory=dict)


class WorkchestratorResult(BaseModel):
    success: bool
    plan: ActionPlan
    generation_time_ms: int = 0
    error: Optional[str] = None
    orchestration: WorkchestratorSummary


GeneratorFactory = Callable[[str, OrchestrationSettings], PlanGenerator]


class WorkchestratorPlanner:
    """Explicit planner/reviewer/takeover layer over the existing PlanGenerator."""

    def __init__(self, generator_factory: GeneratorFactory) -> None:
        self._generator_factory = generator_factory

    async def plan_edit(
        self,
        *,
        document_outline: str,
        document_id: str,
        document_title: str,
        user_request: str,
        settings: OrchestrationSettings,
    ) -> WorkchestratorResult:
        transitions: List[StateTransition] = [
            StateTransition(
                state=WorkchestratorState.RECEIVED,
                action="receive_request",
                reason="Document edit request received.",
            )
        ]

        signals = self._analyze_request(document_outline=document_outline, user_request=user_request)
        transitions.append(
            StateTransition(
                state=WorkchestratorState.ANALYZED,
                action="analyze_task",
                reason="Computed routing signals for plan generation.",
                metadata=signals,
            )
        )

        if not settings.enabled or settings.strategy == "classic":
            output = await self._run_planner(
                role="worker",
                document_outline=document_outline,
                document_id=document_id,
                document_title=document_title,
                user_request=user_request,
                settings=settings,
            )
            transitions.append(
                StateTransition(
                    state=WorkchestratorState.PLANNED,
                    action="direct_plan",
                    reason="Classic planning selected; skipping worker review and takeover.",
                )
            )
            final_transitions = transitions + [
                StateTransition(
                    state=WorkchestratorState.COMPLETED if output.success else WorkchestratorState.FAILED,
                    action="complete",
                    reason="Classic planner finished.",
                )
            ]
            return WorkchestratorResult(
                success=output.success,
                plan=output.plan,
                generation_time_ms=output.generation_time_ms,
                error=output.error,
                orchestration=WorkchestratorSummary(
                    strategy=settings.strategy,
                    enabled=settings.enabled,
                    initial_mode="direct",
                    final_mode="direct",
                    delegated=False,
                    signals=signals,
                    transitions=final_transitions,
                    settings_snapshot=settings.model_dump(mode="json"),
                ),
            )

        force_takeover = signals["complexity_score"] >= settings.takeover.complexity_takeover_threshold
        initial_mode = "takeover" if force_takeover else "delegate"

        if force_takeover:
            transitions.append(
                StateTransition(
                    state=WorkchestratorState.TAKEN_OVER_BY_ORCHESTRATOR,
                    action="escalate_to_orchestrator",
                    reason="Task complexity exceeded the configured delegation threshold.",
                    metadata={"complexity_score": signals["complexity_score"]},
                )
            )
            output = await self._run_planner(
                role="orchestrator",
                document_outline=document_outline,
                document_id=document_id,
                document_title=document_title,
                user_request=self._build_takeover_request(user_request, signals, []),
                settings=settings,
            )
            final_state = WorkchestratorState.COMPLETED if output.success else WorkchestratorState.FAILED
            transitions.append(
                StateTransition(
                    state=final_state,
                    action="complete",
                    reason="Orchestrator planned the task directly.",
                )
            )
            return WorkchestratorResult(
                success=output.success,
                plan=output.plan,
                generation_time_ms=output.generation_time_ms,
                error=output.error,
                orchestration=WorkchestratorSummary(
                    initial_mode=initial_mode,
                    final_mode="orchestrator",
                    delegated=False,
                    takeover_reason="complexity_threshold",
                    worker_attempts=0,
                    signals=signals,
                    transitions=transitions,
                    settings_snapshot=settings.model_dump(mode="json"),
                ),
            )

        validation_issues: List[str] = []
        last_worker_confidence: Optional[float] = None
        total_generation_ms = 0
        worker_output: Optional[GeneratePlanOutput] = None

        for attempt in range(settings.takeover.max_worker_retries + 1):
            transitions.append(
                StateTransition(
                    state=WorkchestratorState.DISPATCHED,
                    action="delegate_to_worker",
                    reason=f"Delegating attempt {attempt + 1} to worker planner.",
                    metadata={"attempt": attempt + 1},
                )
            )
            worker_output = await self._run_planner(
                role="worker",
                document_outline=document_outline,
                document_id=document_id,
                document_title=document_title,
                user_request=self._build_worker_request(user_request, attempt, validation_issues),
                settings=settings,
            )
            total_generation_ms += worker_output.generation_time_ms
            validation_issues = self._validate_plan(worker_output.plan) if worker_output.success else [worker_output.error or "Worker failed to generate a plan."]
            last_worker_confidence = self._score_worker_confidence(
                worker_output=worker_output,
                signals=signals,
                validation_issues=validation_issues,
            )

            transitions.append(
                StateTransition(
                    state=WorkchestratorState.WORKER_DONE,
                    action="review_worker_output",
                    reason="Worker plan generated and reviewed.",
                    confidence=last_worker_confidence,
                    metadata={
                        "attempt": attempt + 1,
                        "validation_issues": validation_issues,
                    },
                )
            )

            if worker_output.success and last_worker_confidence >= settings.takeover.worker_confidence_threshold and len(validation_issues) <= settings.takeover.max_validation_issues:
                transitions.append(
                    StateTransition(
                        state=WorkchestratorState.VERIFIED,
                        action="accept_worker_plan",
                        reason="Worker plan passed confidence and validation checks.",
                        confidence=last_worker_confidence,
                    )
                )
                transitions.append(
                    StateTransition(
                        state=WorkchestratorState.COMPLETED,
                        action="complete",
                        reason="Worker plan accepted.",
                    )
                )
                return WorkchestratorResult(
                    success=True,
                    plan=worker_output.plan,
                    generation_time_ms=total_generation_ms,
                    orchestration=WorkchestratorSummary(
                        initial_mode=initial_mode,
                        final_mode="worker",
                        delegated=True,
                        worker_attempts=attempt + 1,
                        worker_confidence=last_worker_confidence,
                        signals=signals,
                        validation_issues=validation_issues,
                        transitions=transitions,
                        settings_snapshot=settings.model_dump(mode="json"),
                    ),
                )

        takeover_reason = self._derive_takeover_reason(
            worker_output=worker_output,
            validation_issues=validation_issues,
            confidence=last_worker_confidence,
            settings=settings,
        )

        if not settings.allow_orchestrator_takeover:
            transitions.append(
                StateTransition(
                    state=WorkchestratorState.FAILED,
                    action="fail_without_takeover",
                    reason="Worker plan was rejected and orchestrator takeover is disabled.",
                    confidence=last_worker_confidence,
                    metadata={"validation_issues": validation_issues},
                )
            )
            return WorkchestratorResult(
                success=False,
                plan=worker_output.plan if worker_output else ActionPlan(title=f"Edit Plan for {document_title}", original_prompt=user_request),
                generation_time_ms=total_generation_ms,
                error="Worker planning failed and orchestrator takeover is disabled.",
                orchestration=WorkchestratorSummary(
                    initial_mode=initial_mode,
                    final_mode="worker",
                    delegated=True,
                    worker_attempts=settings.takeover.max_worker_retries + 1,
                    worker_confidence=last_worker_confidence,
                    takeover_reason=takeover_reason,
                    signals=signals,
                    validation_issues=validation_issues,
                    transitions=transitions,
                    settings_snapshot=settings.model_dump(mode="json"),
                ),
            )

        transitions.append(
            StateTransition(
                state=WorkchestratorState.TAKEN_OVER_BY_ORCHESTRATOR,
                action="escalate_to_orchestrator",
                reason=takeover_reason,
                confidence=last_worker_confidence,
                metadata={"validation_issues": validation_issues},
            )
        )

        takeover_output = await self._run_planner(
            role="orchestrator",
            document_outline=document_outline,
            document_id=document_id,
            document_title=document_title,
            user_request=self._build_takeover_request(user_request, signals, validation_issues),
            settings=settings,
        )
        total_generation_ms += takeover_output.generation_time_ms

        takeover_validation_issues = self._validate_plan(takeover_output.plan) if takeover_output.success else [takeover_output.error or "Orchestrator failed to generate a plan."]
        final_state = WorkchestratorState.COMPLETED if takeover_output.success else WorkchestratorState.FAILED
        transitions.append(
            StateTransition(
                state=final_state,
                action="complete",
                reason="Orchestrator takeover finished.",
                metadata={"validation_issues": takeover_validation_issues},
            )
        )

        return WorkchestratorResult(
            success=takeover_output.success,
            plan=takeover_output.plan,
            generation_time_ms=total_generation_ms,
            error=takeover_output.error,
            orchestration=WorkchestratorSummary(
                initial_mode=initial_mode,
                final_mode="orchestrator",
                delegated=True,
                worker_attempts=settings.takeover.max_worker_retries + 1,
                worker_confidence=last_worker_confidence,
                takeover_reason=takeover_reason,
                signals=signals,
                validation_issues=takeover_validation_issues,
                transitions=transitions,
                settings_snapshot=settings.model_dump(mode="json"),
            ),
        )

    async def _run_planner(
        self,
        *,
        role: str,
        document_outline: str,
        document_id: str,
        document_title: str,
        user_request: str,
        settings: OrchestrationSettings,
    ) -> GeneratePlanOutput:
        generator = self._generator_factory(role, settings)
        return await generator.generate_edit_plan(
            document_outline=document_outline,
            user_request=user_request,
            document_id=document_id,
            document_title=document_title,
        )

    def _analyze_request(self, *, document_outline: str, user_request: str) -> Dict[str, Any]:
        outline_lines = [line for line in document_outline.splitlines() if line.strip()]
        request_words = len(user_request.split())
        lower = user_request.lower()
        ambiguous_hits = sum(1 for token in ("maybe", "somehow", "best", "improve", "clean up", "fix", "refine") if token in lower)
        cross_cutting_hits = sum(1 for token in ("across", "throughout", "all sections", "entire document", "every chapter", "restructure", "rewrite") if token in lower)
        dependency_density = min(1.0, (document_outline.count("Section") + document_outline.count("Page")) / 30)
        complexity_score = min(
            1.0,
            0.18
            + min(request_words / 80, 0.28)
            + min(len(outline_lines) / 60, 0.22)
            + ambiguous_hits * 0.08
            + cross_cutting_hits * 0.12
            + dependency_density * 0.12,
        )
        return {
            "request_words": request_words,
            "outline_lines": len(outline_lines),
            "ambiguous_hits": ambiguous_hits,
            "cross_cutting_hits": cross_cutting_hits,
            "dependency_density": round(dependency_density, 3),
            "complexity_score": round(complexity_score, 3),
        }

    def _validate_plan(self, plan: ActionPlan) -> List[str]:
        issues: List[str] = []
        allowed_actions = {"add_chapter", "add_section", "write_page", "edit_page", "delete_page"}
        node_ids = {node.id for node in plan.get_execution_order()}

        if plan.total_nodes == 0:
            issues.append("No actions were generated.")
            return issues

        for node in plan.get_execution_order():
            if node.action_name not in allowed_actions:
                issues.append(f"Unsupported action '{node.action_name}' in node {node.id}.")

            if node.action_name == "add_section":
                chapter_id = node.inputs.get("chapter_id")
                if not chapter_id:
                    issues.append(f"Node {node.id} is missing chapter_id.")
            elif node.action_name == "write_page":
                section_id = node.inputs.get("section_id")
                content = node.inputs.get("content") or node.inputs.get("content_outline")
                if not section_id:
                    issues.append(f"Node {node.id} is missing section_id.")
                if not content:
                    issues.append(f"Node {node.id} is missing page content.")
            elif node.action_name in {"edit_page", "delete_page"} and not node.inputs.get("page_id"):
                issues.append(f"Node {node.id} is missing page_id.")

            for placeholder in node.get_placeholder_dependencies():
                if placeholder.node_id not in node_ids:
                    issues.append(
                        f"Node {node.id} references missing placeholder source '{placeholder.node_id}'."
                    )

        return issues

    def _score_worker_confidence(
        self,
        *,
        worker_output: GeneratePlanOutput,
        signals: Dict[str, Any],
        validation_issues: List[str],
    ) -> float:
        confidence = 0.82 if worker_output.success else 0.28
        confidence -= min(len(validation_issues) * 0.12, 0.48)
        confidence -= signals["cross_cutting_hits"] * 0.06
        confidence -= signals["ambiguous_hits"] * 0.04
        confidence -= max(signals["complexity_score"] - 0.55, 0) * 0.35
        if worker_output.plan.total_nodes == 1:
            confidence -= 0.04
        return max(0.0, min(round(confidence, 3), 1.0))

    def _build_worker_request(self, user_request: str, attempt: int, validation_issues: List[str]) -> str:
        if attempt == 0:
            return user_request
        issues_text = "\n".join(f"- {issue}" for issue in validation_issues) or "- Prior attempt was low-confidence."
        return (
            f"{user_request}\n\n"
            "Retry with a narrower, fully-resolved action plan.\n"
            "Avoid missing IDs and keep edits minimal.\n"
            f"Previous review findings:\n{issues_text}"
        )

    def _build_takeover_request(
        self,
        user_request: str,
        signals: Dict[str, Any],
        validation_issues: List[str],
    ) -> str:
        issues_text = "\n".join(f"- {issue}" for issue in validation_issues) or "- None"
        return (
            f"{user_request}\n\n"
            "You are taking over planning as the senior orchestrator.\n"
            "Produce the safest minimal action plan that satisfies the request.\n"
            "Prefer globally consistent edits over speculative decomposition.\n"
            f"Complexity signals: {signals}\n"
            f"Worker review findings:\n{issues_text}"
        )

    def _derive_takeover_reason(
        self,
        *,
        worker_output: Optional[GeneratePlanOutput],
        validation_issues: List[str],
        confidence: Optional[float],
        settings: OrchestrationSettings,
    ) -> str:
        if not worker_output or not worker_output.success:
            return "worker_failed"
        if len(validation_issues) > settings.takeover.max_validation_issues:
            return "validation_failed"
        if confidence is not None and confidence < settings.takeover.worker_confidence_threshold:
            return "worker_low_confidence"
        return "worker_retries_exhausted"
