"""
Action plan tree system for document authoring.

Provides planning capabilities for generating structured action plans
from high-level prompts before execution.
"""

from officeplane.components.planning.models import (
    ActionNode,
    ActionPlan,
    GeneratePlanInput,
    GeneratePlanOutput,
    NodeStatus,
    PlaceholderID,
    PlanSummary,
)
from officeplane.components.planning.generator import (
    ChapterSpec,
    DocumentSpec,
    GeminiPlanAdapter,
    MockPlanLLM,
    PageSpec,
    PlanGenerator,
    SectionSpec,
    create_plan_from_outline,
)
from officeplane.components.planning.display import PlanDisplayer

__all__ = [
    # Core models
    "PlaceholderID",
    "NodeStatus",
    "ActionNode",
    "ActionPlan",
    # Input/Output models
    "GeneratePlanInput",
    "GeneratePlanOutput",
    "PlanSummary",
    # Spec models for outlines
    "PageSpec",
    "SectionSpec",
    "ChapterSpec",
    "DocumentSpec",
    # Generator
    "PlanGenerator",
    "GeminiPlanAdapter",
    "MockPlanLLM",
    "create_plan_from_outline",
    # Display
    "PlanDisplayer",
]
