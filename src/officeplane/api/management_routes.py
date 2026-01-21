"""
FastAPI routes for OfficePlane Management System
Instances, Tasks, History, Metrics, and WebSocket
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Body
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import json
from pydantic import BaseModel

from prisma.enums import InstanceState, TaskState, TaskPriority, EventType
from ..management.db import get_db
from ..management.instance_manager import instance_manager
from ..management.task_queue import task_queue
from ..documents.importer import DocumentImporter
from ..documents.store import DocumentStore
from ..components.planning.generator import PlanGenerator, MockPlanLLM
from ..components.planning.models import GeneratePlanInput, PlanSummary, ActionPlan, ActionNode
from ..components.planning.display import PlanDisplayer
from ..components.runner import OpenAIAdapter
from ..config import config

router = APIRouter(prefix="/api")

# WebSocket connections for real-time updates
websocket_connections: set[WebSocket] = set()


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================


class CreateInstanceRequest(BaseModel):
    documentId: Optional[str] = None
    driverType: Optional[str] = None
    filePath: Optional[str] = None


class PlanDocumentRequest(BaseModel):
    prompt: str
    max_chapters: int = 20
    max_sections_per_chapter: int = 10
    max_pages_per_section: int = 5
    include_content_outlines: bool = True


async def broadcast_event(event_type: str, data: dict):
    """Broadcast event to all connected WebSocket clients"""
    message = {"type": event_type, "data": data, "timestamp": datetime.utcnow().isoformat()}

    disconnected = set()
    for ws in websocket_connections:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.add(ws)

    # Clean up disconnected clients
    websocket_connections.difference_update(disconnected)


def _format_outline_for_prompt(outline) -> str:
    lines: List[str] = []
    lines.append(f"Document: {outline.title} ({outline.id})")
    if outline.author:
        lines.append(f"Author: {outline.author}")
    lines.append(
        f"Chapters: {outline.chapter_count}, Sections: {outline.section_count}, Pages: {outline.page_count}"
    )
    for chapter in outline.chapters:
        lines.append(f"- Chapter {chapter.order_index + 1}: {chapter.title} ({chapter.id})")
        for section in chapter.sections:
            lines.append(
                f"  - Section {section.order_index + 1}: {section.title} ({section.id})"
            )
            for page in section.pages:
                lines.append(f"    - Page {page.page_number} ({page.id})")
    return "\n".join(lines)


def _normalize_plan_for_existing_document(
    plan: ActionPlan,
    document_id: str,
    title: str,
    existing_chapter_titles: Optional[set[str]] = None,
) -> ActionPlan:
    roots: List[ActionNode] = []

    def normalize_node(node: ActionNode, parent_id: Optional[str]) -> None:
        node.parent_id = parent_id
        for idx, child in enumerate(node.children):
            if child.order_index == 0:
                child.order_index = idx
            normalize_node(child, node.id)

        if node.action_name == "add_chapter":
            node.inputs["document_id"] = document_id
        elif node.action_name == "write_page":
            if "content" not in node.inputs and "content_outline" in node.inputs:
                node.inputs["content"] = node.inputs.pop("content_outline")
            node.inputs.pop("title", None)
            node.inputs.setdefault("content", "")

    existing_titles = {t.lower() for t in (existing_chapter_titles or set())}

    for root in plan.roots:
        if root.action_name == "create_document":
            for child in root.children:
                if (
                    child.action_name == "add_chapter"
                    and child.inputs.get("title", "").lower() in existing_titles
                ):
                    continue
                child.parent_id = None
                normalize_node(child, None)
                roots.append(child)
        else:
            root.parent_id = None
            if (
                root.action_name == "add_chapter"
                and root.inputs.get("title", "").lower() in existing_titles
            ):
                continue
            normalize_node(root, None)
            roots.append(root)

    return ActionPlan(
        title=f"Plan for {title}",
        original_prompt=plan.original_prompt,
        roots=roots,
    )


def _build_plan_generator() -> PlanGenerator:
    import os

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=openai_key)
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            return PlanGenerator(llm=OpenAIAdapter(client, model=model))
        except Exception:
            return PlanGenerator(llm=MockPlanLLM())
    return PlanGenerator(llm=MockPlanLLM())


# ============================================================
# INSTANCES
# ============================================================


@router.get("/instances")
async def list_instances(state: Optional[str] = None):
    """List all document instances"""
    state_enum = InstanceState(state) if state else None
    instances = await instance_manager.list_instances(state=state_enum)
    return instances


@router.get("/instances/{instance_id}")
async def get_instance(instance_id: str):
    """Get instance by ID"""
    instance = await instance_manager.get_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    return instance


@router.post("/instances")
async def create_instance(request: CreateInstanceRequest = Body(...)):
    """Create a new document instance"""
    # Use configured default driver if not specified
    driver = request.driverType or config.DEFAULT_DRIVER_TYPE

    instance = await instance_manager.create_instance(
        driver_type=driver,
        document_id=request.documentId,
        file_path=request.filePath,
    )

    # Broadcast event
    await broadcast_event("instance_update", instance)

    return instance


@router.post("/instances/{instance_id}/close")
async def close_instance(instance_id: str):
    """Close an instance"""
    instance = await instance_manager.close_instance(instance_id)

    # Broadcast event
    await broadcast_event("instance_update", instance)

    return instance


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str):
    """Delete an instance"""
    await instance_manager.delete_instance(instance_id)
    return {"status": "deleted", "id": instance_id}


# ============================================================
# DOCUMENTS
# ============================================================


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    author: Optional[str] = None,
):
    """
    Upload and import a Word document

    Parses the document structure (chapters, sections, pages) and stores it in the database.
    Returns the document with its full structure.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    if not file.filename.endswith(('.doc', '.docx')):
        raise HTTPException(
            status_code=400,
            detail="Only .doc and .docx files are supported"
        )

    try:
        # Read file contents
        contents = await file.read()

        # Create document store with database URL
        import os
        database_url = os.getenv("DATABASE_URL", "postgresql://officeplane:officeplane@db:5432/officeplane")
        doc_store = DocumentStore(database_url=database_url)

        # Connect to database
        await doc_store.connect()

        # Create importer
        importer = DocumentImporter(doc_store=doc_store)

        # Import document
        document = await importer.import_from_bytes(
            docx_bytes=contents,
            title=title or file.filename.replace('.docx', '').replace('.doc', ''),
            author=author,
            index_for_search=True,  # Enable search indexing
        )

        # Get full document with structure
        full_document = await doc_store.get_document(
            document.id,
            load_children=True  # Load chapters, sections, pages
        )

        # Broadcast event
        await broadcast_event("document_uploaded", {
            "id": str(document.id),
            "title": document.title,
            "author": document.author,
            "filename": file.filename,
        })

        return {
            "id": str(full_document.id),
            "title": full_document.title,
            "author": full_document.author,
            "chapters": [
                {
                    "id": str(ch.id),
                    "title": ch.title,
                    "order_index": ch.order_index,
                    "sections": [
                        {
                            "id": str(sec.id),
                            "title": sec.title,
                            "order_index": sec.order_index,
                            "page_count": len(sec.pages) if sec.pages else 0,
                        }
                        for sec in (ch.sections or [])
                    ],
                }
                for ch in (full_document.chapters or [])
            ],
            "total_chapters": len(full_document.chapters or []),
            "total_pages": sum(
                len(sec.pages or [])
                for ch in (full_document.chapters or [])
                for sec in (ch.sections or [])
            ),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error importing document: {str(e)}"
        )


@router.get("/documents")
async def list_documents():
    """List all documents"""
    db = await get_db()
    documents = await db.document.find_many(
        order={"createdAt": "desc"},
        include={"chapters": {"include": {"sections": True}}},
    )

    return [
        {
            "id": str(doc.id),
            "title": doc.title,
            "author": doc.author,
            "createdAt": doc.createdAt.isoformat(),
            "total_chapters": len(doc.chapters or []),
            "total_sections": sum(len(ch.sections or []) for ch in (doc.chapters or [])),
        }
        for doc in documents
    ]


@router.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Get document with full structure"""
    import os
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://officeplane:officeplane@db:5432/officeplane"
    )
    doc_store = DocumentStore(database_url=database_url)
    await doc_store.connect()

    try:
        full_document = await doc_store.get_document(document_id, load_children=True)

        if not full_document:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "id": str(full_document.id),
            "title": full_document.title,
            "author": full_document.author,
            "chapters": [
                {
                    "id": str(ch.id),
                    "title": ch.title,
                    "order_index": ch.order_index,
                    "sections": [
                        {
                            "id": str(sec.id),
                            "title": sec.title,
                            "order_index": sec.order_index,
                            "page_count": len(sec.pages) if sec.pages else 0,
                        }
                        for sec in (ch.sections or [])
                    ],
                }
                for ch in (full_document.chapters or [])
            ],
            "total_chapters": len(full_document.chapters or []),
            "total_pages": sum(
                len(sec.pages or [])
                for ch in (full_document.chapters or [])
                for sec in (ch.sections or [])
            ),
        }
    finally:
        await doc_store.close()


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all its chapters, sections, and pages"""
    import os

    db = await get_db()

    # Check if document exists
    document = await db.document.find_unique(where={"id": document_id})
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Close any instances associated with this document
    instances = await db.documentinstance.find_many(
        where={"documentId": document_id}
    )
    for instance in instances:
        try:
            await instance_manager.close_instance(instance.id)
        except Exception:
            pass  # Instance might already be closed

    # Delete associated instances
    await db.documentinstance.delete_many(where={"documentId": document_id})

    # Delete document (cascades to chapters, sections, pages due to DB relations)
    await db.document.delete(where={"id": document_id})

    # Broadcast event
    await broadcast_event("document_deleted", {
        "id": document_id,
        "title": document.title,
    })

    return {"status": "deleted", "id": document_id}


@router.post("/documents/{document_id}/plan")
async def plan_document(document_id: str, request: PlanDocumentRequest = Body(...)):
    """Generate an action plan for editing an existing document."""
    import os
    from uuid import UUID

    database_url = os.getenv(
        "DATABASE_URL", "postgresql://officeplane:officeplane@db:5432/officeplane"
    )
    doc_store = DocumentStore(database_url=database_url)
    await doc_store.connect()

    try:
        outline = await doc_store.get_outline(UUID(document_id))
        if not outline:
            raise HTTPException(status_code=404, detail="Document not found")

        outline_text = _format_outline_for_prompt(outline)
        prompt = (
            "You are planning edits for an existing document.\n"
            "Use the outline below as immutable existing structure.\n"
            "Only propose new chapters/sections/pages to add unless the user explicitly requests edits or deletions.\n"
            "If edits/deletions are requested, reference existing IDs from the outline.\n"
            "Return a plan that can be executed with actions: add_chapter, add_section, write_page, edit_page, delete_page.\n\n"
            f"Document outline:\n{outline_text}\n\n"
            f"User request:\n{request.prompt}"
        )

        generator = _build_plan_generator()
        plan_input = GeneratePlanInput(
            prompt=prompt,
            max_chapters=request.max_chapters,
            max_sections_per_chapter=request.max_sections_per_chapter,
            max_pages_per_section=request.max_pages_per_section,
            include_content_outlines=request.include_content_outlines,
        )
        result = await generator.generate_plan(plan_input)
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error or "Plan generation failed")

        existing_titles = {ch.title for ch in outline.chapters}
        normalized_plan = _normalize_plan_for_existing_document(
            result.plan,
            document_id=document_id,
            title=outline.title,
            existing_chapter_titles=existing_titles,
        )

        summary = PlanSummary.from_plan(normalized_plan)
        return {
            "document": {
                "id": str(outline.id),
                "title": outline.title,
                "author": outline.author,
                "chapter_count": outline.chapter_count,
                "section_count": outline.section_count,
                "page_count": outline.page_count,
            },
            "plan": summary.model_dump(),
            "tree": PlanDisplayer.to_json(normalized_plan, include_inputs=True),
        }
    finally:
        await doc_store.close()


# ============================================================
# TASKS
# ============================================================


@router.get("/tasks")
async def list_tasks(
    state: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 100,
):
    """List tasks"""
    state_enum = TaskState(state) if state else None
    priority_enum = TaskPriority(priority) if priority else None

    tasks = await task_queue.list_tasks(
        state=state_enum,
        priority=priority_enum,
        limit=limit,
    )
    return tasks


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task by ID"""
    task = await task_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks")
async def create_task(
    taskType: str,
    payload: dict = {},
    taskName: Optional[str] = None,
    documentId: Optional[str] = None,
    instanceId: Optional[str] = None,
    priority: str = "NORMAL",
    maxRetries: int = 3,
):
    """Enqueue a new task"""
    priority_enum = TaskPriority(priority)

    task = await task_queue.enqueue_task(
        task_type=taskType,
        payload=payload,
        task_name=taskName,
        document_id=documentId,
        instance_id=instanceId,
        priority=priority_enum,
        max_retries=maxRetries,
    )

    # Broadcast event
    await broadcast_event("task_update", task)

    return task


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a task"""
    task = await task_queue.cancel_task(task_id)

    # Broadcast event
    await broadcast_event("task_update", task)

    return task


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    """Retry a failed task"""
    task = await task_queue.retry_task(task_id)

    # Broadcast event
    await broadcast_event("task_update", task)

    return task


# ============================================================
# HISTORY
# ============================================================


@router.get("/history")
async def get_history(
    eventType: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Get execution history"""
    db = await get_db()

    where_clause = {}
    if eventType:
        where_clause["eventType"] = EventType(eventType)

    history = await db.executionhistory.find_many(
        where=where_clause,
        include={"document": True, "task": True},
        order={"timestamp": "desc"},
        skip=offset,
        take=limit,
    )

    return [event.model_dump() for event in history]


# ============================================================
# METRICS
# ============================================================


@router.get("/metrics")
async def get_metrics():
    """Get system metrics"""
    db = await get_db()

    # Instance metrics
    instances = await db.documentinstance.find_many()
    instances_by_state = {}
    total_memory = 0
    total_cpu = 0
    active_count = 0

    for inst in instances:
        state = inst.state.value
        instances_by_state[state] = instances_by_state.get(state, 0) + 1

        if inst.state in [InstanceState.OPEN, InstanceState.IDLE, InstanceState.IN_USE]:
            active_count += 1
            if inst.memoryMb:
                total_memory += inst.memoryMb
            if inst.cpuPercent:
                total_cpu += inst.cpuPercent

    # Task metrics
    tasks = await db.task.find_many()
    tasks_by_state = {}
    total_duration = 0
    completed_count = 0
    failed_count = 0

    for task in tasks:
        state = task.state.value
        tasks_by_state[state] = tasks_by_state.get(state, 0) + 1

        if task.state == TaskState.COMPLETED and task.startedAt and task.completedAt:
            duration = (task.completedAt - task.startedAt).total_seconds() * 1000
            total_duration += duration
            completed_count += 1

        if task.state == TaskState.FAILED:
            failed_count += 1

    avg_duration_ms = total_duration / completed_count if completed_count > 0 else 0
    failure_rate = failed_count / len(tasks) if tasks else 0

    return {
        "instances": {
            "total": len(instances),
            "byState": instances_by_state,
        },
        "tasks": {
            "total": len(tasks),
            "byState": tasks_by_state,
            "avgDurationMs": avg_duration_ms,
            "failureRate": failure_rate,
        },
        "system": {
            "uptime": 0,  # TODO: track uptime
            "memoryUsageMb": total_memory / active_count if active_count > 0 else 0,
            "cpuPercent": total_cpu / active_count if active_count > 0 else 0,
        },
    }


# ============================================================
# WEBSOCKET
# ============================================================


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    websocket_connections.add(websocket)

    print(f"[WebSocket] Client connected. Total connections: {len(websocket_connections)}")

    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "data": {"message": "Connected to OfficePlane Management System"},
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Keep connection alive and listen for messages
        while True:
            data = await websocket.receive_text()
            # Echo or process messages if needed
            # await websocket.send_json({"type": "echo", "data": data})

    except WebSocketDisconnect:
        websocket_connections.discard(websocket)
        print(
            f"[WebSocket] Client disconnected. Total connections: {len(websocket_connections)}"
        )
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        websocket_connections.discard(websocket)
