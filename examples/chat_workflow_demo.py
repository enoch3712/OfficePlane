#!/usr/bin/env python3
"""
Demo: Chat-based document manipulation workflow.

This script simulates how an agent would interact with a user
to modify a document with plan approval.

Run: python examples/chat_workflow_demo.py
"""

import tempfile
from pathlib import Path

from officeplane.doctools import (
    DocumentEditor,
    DocumentPlan,
    format_plan_for_chat,
    format_execution_result,
    execute_with_progress,
    is_approval,
    is_rejection,
    detect_approval,
    ApprovalResponse,
)
from officeplane.doctools.chat import format_step_progress, StepProgress


def print_agent(message: str):
    """Print message from agent perspective."""
    print(f"\n🤖 Agent: {message}")


def print_user(message: str):
    """Print message from user perspective."""
    print(f"\n👤 User: {message}")


def print_divider():
    print("\n" + "=" * 60)


def demo_basic_workflow():
    """Demo: Basic plan-approve-execute workflow."""
    print_divider()
    print("DEMO 1: Basic Plan-Approve-Execute Workflow")
    print_divider()

    # Create a temp document path (file doesn't exist yet)
    doc_path = Path(tempfile.mkdtemp()) / "demo_report.docx"

    # Initialize document
    with DocumentEditor(doc_path, create_if_missing=True) as editor:
        editor.add_heading("My Report", level=1)
        editor.add_paragraph("This is the introduction.")
        editor.save()

    # Simulate conversation
    print_user("Add a conclusion section to my report with a summary")

    # Agent creates a plan
    plan = (DocumentPlan("Add conclusion section")
        .add_heading("Conclusion", level=1)
        .add_paragraph("In summary, this report has covered the key findings and recommendations.")
        .add_paragraph("Thank you for reading."))

    # Agent shows the plan
    print_agent("I'll add a conclusion section. Here's my plan:")
    print()
    print(format_plan_for_chat(plan, style="box"))
    print()
    print_agent("Should I proceed?")

    # User approves
    user_response = "yes, go ahead"
    print_user(user_response)

    # Check approval
    if is_approval(user_response):
        print_agent("Executing plan...")
        print()

        # Execute with progress
        with DocumentEditor(doc_path) as editor:
            def show_progress(progress: StepProgress):
                print(format_step_progress(progress))

            result = execute_with_progress(plan, editor, on_step=show_progress)

        print()
        print_agent(format_execution_result(plan))

    # Cleanup
    doc_path.unlink()
    doc_path.parent.rmdir()


def demo_rejection():
    """Demo: User rejects the plan."""
    print_divider()
    print("DEMO 2: User Rejects Plan")
    print_divider()

    print_user("Delete everything in my document")

    # Agent creates a cautious plan
    plan = (DocumentPlan("Delete all content")
        .add_paragraph(""))  # Placeholder

    print_agent("Here's the plan to delete all content:")
    print()
    print(format_plan_for_chat(plan, style="simple"))
    print()
    print_agent("⚠️ This will remove ALL content. Should I proceed?")

    # User rejects
    user_response = "no, cancel that"
    print_user(user_response)

    if is_rejection(user_response):
        print_agent("Okay, I've cancelled the operation. Your document is unchanged.")


def demo_modification():
    """Demo: User wants to modify the plan."""
    print_divider()
    print("DEMO 3: User Modifies Plan")
    print_divider()

    print_user("Add a table of contents and an appendix")

    # Agent creates initial plan
    plan = (DocumentPlan("Add TOC and Appendix")
        .add_heading("Table of Contents", level=1)
        .add_paragraph("[TOC will be generated here]")
        .add_heading("Appendix", level=1)
        .add_paragraph("Additional materials..."))

    print_agent("Here's my plan:")
    print()
    print(format_plan_for_chat(plan, style="simple"))
    print()
    print_agent("Should I proceed?")

    # User wants modification
    user_response = "change the appendix heading to 'Appendix A: References'"
    print_user(user_response)

    response_type = detect_approval(user_response)
    if response_type == ApprovalResponse.MODIFY:
        print_agent("Got it! Let me update the plan...")

        # Create modified plan
        plan = (DocumentPlan("Add TOC and Appendix (modified)")
            .add_heading("Table of Contents", level=1)
            .add_paragraph("[TOC will be generated here]")
            .add_heading("Appendix A: References", level=1)
            .add_paragraph("Additional materials..."))

        print()
        print(format_plan_for_chat(plan, style="simple"))
        print()
        print_agent("Updated! Should I proceed now?")

        # User approves
        print_user("yes")
        print_agent("Executing... ✓ Done!")


def demo_different_styles():
    """Demo: Different plan display styles."""
    print_divider()
    print("DEMO 4: Different Display Styles")
    print_divider()

    plan = (DocumentPlan("Create quarterly report")
        .add_heading("Q4 2024 Report", level=1)
        .add_paragraph("Executive summary of quarterly performance.")
        .add_table([
            ["Metric", "Q3", "Q4", "Change"],
            ["Revenue", "$1.2M", "$1.5M", "+25%"],
            ["Users", "10K", "15K", "+50%"],
        ])
        .add_heading("Conclusion", level=2)
        .add_paragraph("Strong growth across all metrics."))

    print("\n📦 BOX STYLE:")
    print(format_plan_for_chat(plan, style="box"))

    print("\n📋 SIMPLE STYLE:")
    print(format_plan_for_chat(plan, style="simple"))

    print("\n📄 DETAILED STYLE:")
    print(format_plan_for_chat(plan, style="detailed"))


def demo_approval_detection():
    """Demo: Various approval/rejection phrases."""
    print_divider()
    print("DEMO 5: Approval Detection")
    print_divider()

    test_phrases = [
        "yes",
        "y",
        "ok",
        "go ahead",
        "do it",
        "looks good",
        "lgtm",
        "👍",
        "no",
        "cancel",
        "stop",
        "don't do that",
        "change step 2",
        "actually, can you modify...",
        "what about adding...",
        "hmm let me think",
    ]

    print("Testing approval detection:\n")
    for phrase in test_phrases:
        result = detect_approval(phrase)
        icon = {
            ApprovalResponse.APPROVE: "✓ APPROVE",
            ApprovalResponse.REJECT: "✗ REJECT",
            ApprovalResponse.MODIFY: "~ MODIFY",
            ApprovalResponse.UNCLEAR: "? UNCLEAR",
        }[result]
        print(f"  \"{phrase}\" → {icon}")


def demo_full_conversation():
    """Demo: Full realistic conversation."""
    print_divider()
    print("DEMO 6: Full Realistic Conversation")
    print_divider()

    # Create a temp document path
    doc_path = Path(tempfile.mkdtemp()) / "project_proposal.docx"

    with DocumentEditor(doc_path, create_if_missing=True) as editor:
        editor.add_heading("Project Proposal", level=1)
        editor.add_paragraph("This document outlines our project proposal.")
        editor.add_heading("Background", level=2)
        editor.add_paragraph("Our team has identified a market opportunity.")
        editor.add_heading("Objectives", level=2)
        editor.add_paragraph("1. Increase market share by 20%")
        editor.save()

    print_user("I need to add a budget section to my project proposal with a cost breakdown table")

    # Agent analyzes and creates plan
    print_agent("I'll add a Budget section with a cost breakdown table. Let me create a plan...")

    plan = (DocumentPlan("Add budget section with cost table")
        .add_heading("Budget", level=2)
        .add_paragraph("The following table outlines the projected costs for this project:")
        .add_table([
            ["Category", "Q1", "Q2", "Total"],
            ["Personnel", "$50,000", "$50,000", "$100,000"],
            ["Equipment", "$20,000", "$5,000", "$25,000"],
            ["Marketing", "$10,000", "$15,000", "$25,000"],
            ["Total", "$80,000", "$70,000", "$150,000"],
        ])
        .add_paragraph("Note: All figures are estimates and subject to revision."))

    print()
    print(format_plan_for_chat(plan, style="box"))
    print()
    print_agent("This will add the Budget section after your existing content. Should I proceed?")

    print_user("The numbers look good, but can you change 'Personnel' to 'Staffing'?")

    response_type = detect_approval("The numbers look good, but can you change 'Personnel' to 'Staffing'?")
    print_agent(f"Detected: {response_type.name}")

    if response_type == ApprovalResponse.MODIFY:
        print_agent("Sure! I'll update the table. Here's the revised plan:")

        plan = (DocumentPlan("Add budget section with cost table (revised)")
            .add_heading("Budget", level=2)
            .add_paragraph("The following table outlines the projected costs for this project:")
            .add_table([
                ["Category", "Q1", "Q2", "Total"],
                ["Staffing", "$50,000", "$50,000", "$100,000"],
                ["Equipment", "$20,000", "$5,000", "$25,000"],
                ["Marketing", "$10,000", "$15,000", "$25,000"],
                ["Total", "$80,000", "$70,000", "$150,000"],
            ])
            .add_paragraph("Note: All figures are estimates and subject to revision."))

        print()
        print(format_plan_for_chat(plan, style="box"))
        print()
        print_agent("Ready to proceed?")

    print_user("Perfect, go ahead")

    if is_approval("Perfect, go ahead"):
        print_agent("Executing plan...")
        print()

        with DocumentEditor(doc_path) as editor:
            def show_progress(progress: StepProgress):
                print(format_step_progress(progress))

            execute_with_progress(plan, editor, on_step=show_progress)

        print()
        print_agent(format_execution_result(plan))
        print()
        print_agent(f"Your document has been updated: {doc_path.name}")

    # Cleanup
    doc_path.unlink()
    doc_path.parent.rmdir()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  DOCUMENT MANIPULATION CHAT WORKFLOW DEMO")
    print("=" * 60)

    demo_basic_workflow()
    demo_rejection()
    demo_modification()
    demo_different_styles()
    demo_approval_detection()
    demo_full_conversation()

    print("\n" + "=" * 60)
    print("  DEMO COMPLETE")
    print("=" * 60 + "\n")
