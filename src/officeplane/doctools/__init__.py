"""
Document manipulation tools with batch operations, transactions, and structured errors.

This module provides high-level document manipulation capabilities:
- DocumentEditor: Context manager for batch operations
- Transaction support with rollback
- Structured Result types (no more string returns)
- Planning/action phases for agentic workflows

Architecture:
    ┌────────────────────────────────────────────────────────────┐
    │  High-Level API (what agents call)                         │
    │  ├── DocumentEditor     → Open/close with context manager  │
    │  ├── StructureReader    → Parse chapters, sections, TOC    │
    │  ├── ContentModifier    → Insert/delete/replace            │
    │  └── TableBuilder       → Create/modify tables             │
    ├────────────────────────────────────────────────────────────┤
    │  Core Operations (python-docx + lxml)                      │
    ├────────────────────────────────────────────────────────────┤
    │  Result Types & Transactions                               │
    │  ├── Result[T]          → Success/Failure with data        │
    │  └── Transaction        → Batch with rollback              │
    └────────────────────────────────────────────────────────────┘
"""

from officeplane.doctools.result import (
    Result,
    Ok,
    Err,
    DocError,
    ErrorCode,
)
from officeplane.doctools.editor import DocumentEditor, EditSession
from officeplane.doctools.operations import (
    StructureReader,
    ContentModifier,
    TableBuilder,
)
from officeplane.doctools.planner import (
    DocumentPlan,
    PlanPhase,
    ActionStep,
    PlanExecutor,
)
from officeplane.doctools.chat import (
    format_plan_for_chat,
    format_step_progress,
    format_execution_result,
    execute_with_progress,
    detect_approval,
    is_approval,
    is_rejection,
    ApprovalResponse,
    get_agent_instructions,
)

__all__ = [
    # Result types
    "Result",
    "Ok",
    "Err",
    "DocError",
    "ErrorCode",
    # Editor
    "DocumentEditor",
    "EditSession",
    # Operations
    "StructureReader",
    "ContentModifier",
    "TableBuilder",
    # Planner
    "DocumentPlan",
    "PlanPhase",
    "ActionStep",
    "PlanExecutor",
    # Chat workflow
    "format_plan_for_chat",
    "format_step_progress",
    "format_execution_result",
    "execute_with_progress",
    "detect_approval",
    "is_approval",
    "is_rejection",
    "ApprovalResponse",
    "get_agent_instructions",
]
