"""
Chat-based document manipulation workflow.

This module provides tools for displaying document plans in chat
and managing the approval workflow.

Usage in agent conversation:

    User: "Add a conclusion to report.docx"

    Agent:
        plan = create_plan_from_request(user_request, document_path)
        formatted = format_plan_for_chat(plan)
        # Display formatted plan and ask for approval

    User: "yes"

    Agent:
        if is_approval(user_response):
            result = execute_with_progress(plan, editor, on_step=print_step)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Union

from officeplane.doctools.planner import (
    ActionStep,
    ActionType,
    DocumentPlan,
    PlanPhase,
    PlanExecutor,
)
from officeplane.doctools.editor import DocumentEditor
from officeplane.doctools.result import Result, Ok, Err, DocError, ErrorCode


# =============================================================================
# Plan Formatting for Chat
# =============================================================================


def format_plan_for_chat(
    plan: DocumentPlan,
    style: str = "box",
    show_details: bool = True,
) -> str:
    """
    Format a DocumentPlan as markdown for chat display.

    Args:
        plan: The plan to format
        style: Display style - "box", "simple", or "detailed"
        show_details: Whether to show step parameters

    Returns:
        Formatted markdown string
    """
    if style == "box":
        return _format_box_style(plan, show_details)
    elif style == "simple":
        return _format_simple_style(plan)
    elif style == "detailed":
        return _format_detailed_style(plan)
    else:
        return _format_simple_style(plan)


def _format_box_style(plan: DocumentPlan, show_details: bool) -> str:
    """Format plan with a box border."""
    lines = []

    # Calculate width
    title = f"Plan: {plan.name}"
    step_lines = []
    for i, step in enumerate(plan.steps):
        desc = _get_step_description(step)
        step_lines.append(f"{i + 1}. [ ] {desc}")

    max_width = max(
        len(title),
        max(len(line) for line in step_lines) if step_lines else 20,
        30
    )
    box_width = max_width + 4

    # Build box
    lines.append("```")
    lines.append("┌" + "─" * box_width + "┐")
    lines.append("│ " + title.ljust(box_width - 2) + " │")
    lines.append("│" + " " * box_width + "│")

    for step_line in step_lines:
        lines.append("│ " + step_line.ljust(box_width - 2) + " │")

    lines.append("│" + " " * box_width + "│")

    # Summary line
    summary = f"Steps: {len(plan.steps)} | Rollback: Yes"
    lines.append("│ " + summary.ljust(box_width - 2) + " │")

    lines.append("└" + "─" * box_width + "┘")
    lines.append("```")

    return "\n".join(lines)


def _format_simple_style(plan: DocumentPlan) -> str:
    """Format plan as simple markdown list."""
    lines = [
        f"**Plan: {plan.name}**",
        "",
    ]

    if plan.description:
        lines.append(f"_{plan.description}_")
        lines.append("")

    for i, step in enumerate(plan.steps):
        desc = _get_step_description(step)
        lines.append(f"{i + 1}. {desc}")

    lines.append("")
    lines.append(f"_Total: {len(plan.steps)} steps | Rollback on failure: Yes_")

    return "\n".join(lines)


def _format_detailed_style(plan: DocumentPlan) -> str:
    """Format plan with full details."""
    lines = [
        f"## Plan: {plan.name}",
        "",
    ]

    if plan.description:
        lines.append(f"> {plan.description}")
        lines.append("")

    lines.append("### Steps")
    lines.append("")

    for i, step in enumerate(plan.steps):
        desc = _get_step_description(step)
        lines.append(f"**Step {i + 1}:** {desc}")

        if step.params:
            lines.append("```json")
            import json
            lines.append(json.dumps(step.params, indent=2))
            lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append(f"**Total steps:** {len(plan.steps)}")
    lines.append("**Rollback protection:** Enabled")

    return "\n".join(lines)


def _get_step_description(step: ActionStep) -> str:
    """Get a human-readable description for a step."""
    if step.description:
        return step.description

    action = step.action
    action_str = action.value if isinstance(action, ActionType) else str(action)
    params = step.params

    descriptions = {
        "add_paragraph": lambda p: f"Add paragraph: \"{_truncate(p.get('text', ''), 40)}\"",
        "add_heading": lambda p: f"Add heading (H{p.get('level', 1)}): \"{p.get('text', '')}\"",
        "add_table": lambda p: f"Add table ({p.get('rows', '?')}x{p.get('cols', '?')})",
        "create_data_table": lambda p: f"Add data table ({len(p.get('data', []))} rows)",
        "create_key_value_table": lambda p: f"Add key-value table ({len(p.get('data', {}))} entries)",
        "insert_after_heading": lambda p: f"Insert after \"{p.get('heading_text', '')}\": \"{_truncate(str(p.get('content', '')), 30)}\"",
        "insert_before_heading": lambda p: f"Insert before \"{p.get('heading_text', '')}\"",
        "replace_text": lambda p: f"Replace \"{_truncate(p.get('old_text', ''), 20)}\" → \"{_truncate(p.get('new_text', ''), 20)}\"",
        "replace_in_section": lambda p: f"In \"{p.get('heading_text', '')}\": replace \"{_truncate(p.get('old_text', ''), 15)}\"",
        "delete_paragraph": lambda p: f"Delete paragraph at index {p.get('index', '?')}",
        "delete_section": lambda p: f"Delete section \"{p.get('heading_text', '')}\"",
        "append_to_section": lambda p: f"Append to \"{p.get('heading_text', '')}\"",
        "set_cell": lambda p: f"Set cell [{p.get('row', '?')},{p.get('col', '?')}] = \"{_truncate(p.get('text', ''), 20)}\"",
        "fill_table": lambda p: f"Fill table {p.get('table_index', '?')} with data",
    }

    formatter = descriptions.get(action_str)
    if formatter:
        try:
            return formatter(params)
        except Exception:
            pass

    return f"{action_str}"


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


# =============================================================================
# Execution Progress Display
# =============================================================================


@dataclass
class StepProgress:
    """Progress information for a step."""
    step_number: int
    total_steps: int
    description: str
    status: str  # "pending", "running", "completed", "failed"
    error: Optional[str] = None


def format_step_progress(progress: StepProgress) -> str:
    """Format a step's progress for chat display."""
    icons = {
        "pending": "○",
        "running": "◐",
        "completed": "✓",
        "failed": "✗",
    }
    icon = icons.get(progress.status, "?")

    line = f"{icon} Step {progress.step_number}/{progress.total_steps}: {progress.description}"

    if progress.status == "failed" and progress.error:
        line += f"\n  └─ Error: {progress.error}"

    return line


def format_execution_result(plan: DocumentPlan) -> str:
    """Format the final execution result for chat display."""
    lines = []

    if plan.phase == PlanPhase.COMPLETED:
        lines.append("**✓ Plan executed successfully!**")
        lines.append("")

        completed = sum(1 for s in plan.steps if s.status == "completed")
        lines.append(f"Completed: {completed}/{len(plan.steps)} steps")

    elif plan.phase == PlanPhase.FAILED:
        lines.append("**✗ Plan failed - changes rolled back**")
        lines.append("")

        # Find the failed step
        for i, step in enumerate(plan.steps):
            if step.status == "failed":
                lines.append(f"Failed at step {i + 1}: {_get_step_description(step)}")
                if step.error:
                    lines.append(f"Error: {step.error}")
                break

        lines.append("")
        lines.append("_All changes have been rolled back. Document is unchanged._")

    else:
        lines.append(f"Plan status: {plan.phase.name}")

    return "\n".join(lines)


def execute_with_progress(
    plan: DocumentPlan,
    editor: DocumentEditor,
    on_step: Optional[Callable[[StepProgress], None]] = None,
) -> Result[DocumentPlan]:
    """
    Execute a plan with progress callbacks.

    Args:
        plan: The plan to execute
        editor: Open document editor
        on_step: Callback for each step progress update

    Returns:
        Result containing the executed plan
    """
    total = len(plan.steps)

    def handle_start(step: ActionStep):
        if on_step:
            idx = plan.steps.index(step) + 1
            on_step(StepProgress(
                step_number=idx,
                total_steps=total,
                description=_get_step_description(step),
                status="running",
            ))

    def handle_complete(step: ActionStep, result: Any):
        if on_step:
            idx = plan.steps.index(step) + 1
            on_step(StepProgress(
                step_number=idx,
                total_steps=total,
                description=_get_step_description(step),
                status="completed",
            ))

    def handle_failed(step: ActionStep, error: DocError):
        if on_step:
            idx = plan.steps.index(step) + 1
            on_step(StepProgress(
                step_number=idx,
                total_steps=total,
                description=_get_step_description(step),
                status="failed",
                error=str(error.message),
            ))

    executor = (PlanExecutor(editor)
        .on_step_start(handle_start)
        .on_step_complete(handle_complete)
        .on_step_failed(handle_failed))

    return executor.execute(plan)


# =============================================================================
# Approval Detection
# =============================================================================


class ApprovalResponse(Enum):
    """Types of user responses to a plan."""
    APPROVE = auto()
    REJECT = auto()
    MODIFY = auto()
    UNCLEAR = auto()


APPROVAL_PATTERNS = [
    r"^yes\b",
    r"^y\b",
    r"^ok\b",
    r"^okay\b",
    r"^sure\b",
    r"^go\s*ahead",
    r"^do\s*it",
    r"^proceed",
    r"^execute",
    r"^run\s*(it)?",
    r"^approve",
    r"^confirm",
    r"^lgtm",
    r"^looks?\s*good",
    r"^perfect",
    r"^great",
    r"^👍",
    r"^✓",
]

REJECTION_PATTERNS = [
    r"^no\b",
    r"^n\b",
    r"^cancel",
    r"^stop",
    r"^abort",
    r"^don'?t",
    r"^reject",
    r"^nevermind",
    r"^never\s*mind",
    r"^forget\s*it",
    r"^👎",
    r"^✗",
]

MODIFICATION_PATTERNS = [
    r"^change\b",
    r"^modify\b",
    r"^update\b",
    r"^edit\b",
    r"^instead\b",
    r"^actually\b",
    r"^wait\b",
    r"^but\b",
    r"can\s*you\s*(change|modify|update)",  # Matches anywhere in string
    r"but\s*(can\s*you\s*)?(change|modify|update)",  # "but change", "but can you change"
    r"step\s*\d+",
    r"^remove\s*step",
    r"^add\s*(a\s*)?step",
    r"change\s*['\"]",  # "change 'something'"
    r"change\s+the\b",  # "change the..."
]


def detect_approval(user_message: str) -> ApprovalResponse:
    """
    Detect if a user message is approving, rejecting, or modifying a plan.

    Args:
        user_message: The user's response message

    Returns:
        ApprovalResponse indicating the type of response
    """
    text = user_message.strip().lower()

    # Check approval patterns
    for pattern in APPROVAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return ApprovalResponse.APPROVE

    # Check rejection patterns
    for pattern in REJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return ApprovalResponse.REJECT

    # Check modification patterns
    for pattern in MODIFICATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return ApprovalResponse.MODIFY

    return ApprovalResponse.UNCLEAR


def is_approval(user_message: str) -> bool:
    """Simple check if message is an approval."""
    return detect_approval(user_message) == ApprovalResponse.APPROVE


def is_rejection(user_message: str) -> bool:
    """Simple check if message is a rejection."""
    return detect_approval(user_message) == ApprovalResponse.REJECT


# =============================================================================
# Agent Instructions (for prompts)
# =============================================================================


AGENT_INSTRUCTIONS = """
## Document Manipulation Workflow

When a user asks you to modify a document, follow this workflow:

### Step 1: Understand the Request
- Parse what changes the user wants
- Identify the target document
- Clarify any ambiguities before planning

### Step 2: Create a Plan
Use the DocumentPlan API to create a plan:

```python
from officeplane.doctools import DocumentPlan

plan = (DocumentPlan("Description of changes")
    .add_heading("New Section", level=1)
    .add_paragraph("Content here...")
    .add_table([["Col1", "Col2"], ["A", "B"]]))
```

### Step 3: Show the Plan
Format and display the plan for user approval:

```python
from officeplane.doctools.chat import format_plan_for_chat

formatted = format_plan_for_chat(plan)
# Display to user and ask: "Should I proceed?"
```

### Step 4: Wait for Approval
- If user approves ("yes", "go ahead", etc.) → Execute
- If user rejects ("no", "cancel") → Abort
- If user wants changes → Modify plan and show again

### Step 5: Execute with Progress
```python
from officeplane.doctools import DocumentEditor
from officeplane.doctools.chat import execute_with_progress, format_execution_result

with DocumentEditor(document_path) as editor:
    result = execute_with_progress(plan, editor, on_step=print_progress)

print(format_execution_result(plan))
```

### Key Principles
1. **Always show the plan first** - Never modify documents without user approval
2. **Be specific** - Show exactly what will change
3. **Rollback protection** - All changes are atomic; failures roll back
4. **Progress updates** - Show each step as it executes

### Example Conversation

User: "Add a summary section to report.docx"

You: "I'll add a summary section. Here's my plan:
[formatted plan]
Should I proceed?"

User: "Yes"

You: "Executing...
✓ Step 1/2: Add heading "Summary" (H1)
✓ Step 2/2: Add paragraph with summary text

Done! Document saved successfully."
"""


def get_agent_instructions() -> str:
    """Get the agent instructions for document manipulation."""
    return AGENT_INSTRUCTIONS
