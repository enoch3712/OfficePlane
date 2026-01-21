"""
Task Queue System with Retry Logic
Temporal-style task orchestration for document operations
"""
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Optional, Any
from uuid import uuid4

from prisma import Prisma
from prisma.enums import TaskState, TaskPriority
from .db import get_db


class TaskQueue:
    """Manages task queue with retry logic"""

    def __init__(self):
        self.workers: dict[str, asyncio.Task] = {}
        self.worker_count = 3  # Number of concurrent workers

    async def start_workers(self):
        """Start background workers to process queue"""
        for i in range(self.worker_count):
            worker_id = f"worker-{i}"
            task = asyncio.create_task(self._worker_loop(worker_id))
            self.workers[worker_id] = task

    async def stop_workers(self):
        """Stop all workers"""
        for worker_id, task in self.workers.items():
            task.cancel()
        self.workers.clear()

    async def _worker_loop(self, worker_id: str):
        """Worker loop to process tasks"""
        print(f"[TaskQueue] Worker {worker_id} started")

        while True:
            try:
                # Get next task from queue
                task = await self._dequeue_task(worker_id)

                if task:
                    await self._execute_task(task, worker_id)
                else:
                    # No tasks available, wait before polling again
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                print(f"[TaskQueue] Worker {worker_id} stopped")
                break
            except Exception as e:
                print(f"[TaskQueue] Worker {worker_id} error: {e}")
                await asyncio.sleep(5)

    async def _dequeue_task(self, worker_id: str) -> Optional[dict]:
        """Get next task from queue (QUEUED or RETRYING)"""
        db = await get_db()

        # Find highest priority task that's ready to run
        task = await db.task.find_first(
            where={
                "state": {"in": [TaskState.QUEUED, TaskState.RETRYING]},
                "scheduledFor": {"lte": datetime.utcnow()},
            },
            order=[{"priority": "desc"}, {"createdAt": "asc"}],
        )

        if not task:
            return None

        # Mark as RUNNING and assign to worker
        updated_task = await db.task.update(
            where={"id": task.id},
            data={
                "state": TaskState.RUNNING,
                "startedAt": datetime.utcnow(),
                "workerId": worker_id,
                "workerHost": "localhost",  # In production: get actual hostname
            },
        )

        return updated_task.model_dump()

    async def _execute_task(self, task: dict, worker_id: str):
        """Execute a task"""
        db = await get_db()
        task_id = task["id"]
        start_time = datetime.utcnow()

        try:
            print(f"[TaskQueue] {worker_id} executing task {task_id}: {task['taskType']}")

            # Record retry attempt
            await db.taskretry.create(
                data={
                    "taskId": task_id,
                    "attemptNumber": task["retryCount"] + 1,
                    "startedAt": start_time,
                    "state": TaskState.RUNNING,
                    "workerId": worker_id,
                    "workerHost": "localhost",
                }
            )

            # Execute task based on type
            result = await self._run_task_logic(task)

            # Task succeeded
            end_time = datetime.utcnow()
            await db.task.update(
                where={"id": task_id},
                data={
                    "state": TaskState.COMPLETED,
                    "completedAt": end_time,
                    "result": result,
                },
            )

            # Update retry record
            await db.taskretry.update_many(
                where={
                    "taskId": task_id,
                    "attemptNumber": task["retryCount"] + 1,
                },
                data={
                    "state": TaskState.COMPLETED,
                    "completedAt": end_time,
                },
            )

            print(f"[TaskQueue] Task {task_id} completed successfully")

        except Exception as e:
            # Task failed
            error_message = str(e)
            error_stack = traceback.format_exc()
            end_time = datetime.utcnow()

            print(f"[TaskQueue] Task {task_id} failed: {error_message}")

            # Update retry record
            await db.taskretry.update_many(
                where={
                    "taskId": task_id,
                    "attemptNumber": task["retryCount"] + 1,
                },
                data={
                    "state": TaskState.FAILED,
                    "completedAt": end_time,
                    "errorMessage": error_message,
                    "errorStack": error_stack,
                },
            )

            # Check if we should retry
            retry_count = task["retryCount"] + 1
            max_retries = task["maxRetries"]

            if retry_count < max_retries:
                # Schedule retry with exponential backoff
                delay = task["retryDelaySeconds"] * (
                    task["backoffMultiplier"] ** retry_count
                )
                scheduled_for = datetime.utcnow() + timedelta(seconds=delay)

                await db.task.update(
                    where={"id": task_id},
                    data={
                        "state": TaskState.RETRYING,
                        "retryCount": retry_count,
                        "scheduledFor": scheduled_for,
                        "errorMessage": error_message,
                        "errorStack": error_stack,
                    },
                )

                print(
                    f"[TaskQueue] Task {task_id} will retry in {delay}s (attempt {retry_count}/{max_retries})"
                )
            else:
                # Max retries exceeded, mark as FAILED
                await db.task.update(
                    where={"id": task_id},
                    data={
                        "state": TaskState.FAILED,
                        "completedAt": end_time,
                        "errorMessage": error_message,
                        "errorStack": error_stack,
                    },
                )

                print(f"[TaskQueue] Task {task_id} failed after {max_retries} attempts")

    async def _run_task_logic(self, task: dict) -> dict:
        """Execute task-specific logic"""
        task_type = task["taskType"]
        payload = task["payload"]

        # Simulate task execution
        if task_type == "convert_to_pdf":
            await asyncio.sleep(2)  # Simulate work
            return {"status": "converted", "pages": 5}

        elif task_type == "render_images":
            await asyncio.sleep(3)  # Simulate work
            return {"status": "rendered", "images": 10}

        elif task_type == "export_document":
            await asyncio.sleep(1.5)  # Simulate work
            return {"status": "exported", "file_path": "/tmp/output.docx"}

        else:
            # Generic task
            await asyncio.sleep(1)
            return {"status": "completed"}

    async def enqueue_task(
        self,
        task_type: str,
        payload: dict[str, Any],
        task_name: Optional[str] = None,
        document_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
    ) -> dict:
        """Add a new task to the queue"""
        db = await get_db()

        trace_id = f"task-{uuid4()}"

        task = await db.task.create(
            data={
                "taskType": task_type,
                "taskName": task_name,
                "documentId": document_id,
                "instanceId": instance_id,
                "payload": payload,
                "priority": priority,
                "maxRetries": max_retries,
                "metadata": {"traceId": trace_id},
            }
        )

        print(f"[TaskQueue] Enqueued task {task.id}: {task_type}")

        return task.model_dump()

    async def cancel_task(self, task_id: str) -> dict:
        """Cancel a task"""
        db = await get_db()

        task = await db.task.update(
            where={"id": task_id},
            data={
                "state": TaskState.CANCELLED,
                "completedAt": datetime.utcnow(),
            },
        )

        return task.model_dump()

    async def retry_task(self, task_id: str) -> dict:
        """Manually retry a failed task"""
        db = await get_db()

        task = await db.task.update(
            where={"id": task_id},
            data={
                "state": TaskState.QUEUED,
                "retryCount": 0,
                "scheduledFor": datetime.utcnow(),
                "errorMessage": None,
                "errorStack": None,
            },
        )

        return task.model_dump()

    async def get_task(self, task_id: str) -> Optional[dict]:
        """Get task by ID"""
        db = await get_db()
        task = await db.task.find_unique(
            where={"id": task_id}, include={"document": True}
        )
        return task.model_dump() if task else None

    async def list_tasks(
        self,
        state: Optional[TaskState] = None,
        priority: Optional[TaskPriority] = None,
        limit: int = 100,
    ) -> list[dict]:
        """List tasks"""
        db = await get_db()

        where_clause = {}
        if state:
            where_clause["state"] = state
        if priority:
            where_clause["priority"] = priority

        tasks = await db.task.find_many(
            where=where_clause,
            include={"document": True},
            order={"createdAt": "desc"},
            take=limit,
        )

        return [task.model_dump() for task in tasks]


# Global task queue
task_queue = TaskQueue()
