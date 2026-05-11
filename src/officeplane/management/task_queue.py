"""
Task Queue System with Retry Logic

Workers block-wait on Redis (BRPOP) instead of polling Postgres.
Document-level locks via Redis SETNX prevent concurrent mutations on the same file.
Task state is persisted in Postgres (source of truth); Redis is the dispatch layer.
"""
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Optional, Any
from uuid import uuid4

from prisma.enums import TaskState, TaskPriority
from .db import get_db


class TaskQueue:
    """Manages task queue with Redis dispatch and document-level locking."""

    def __init__(self):
        self.workers: dict[str, asyncio.Task] = {}
        self.worker_count = 3

    # ── Worker lifecycle ─────────────────────────────────────────────────

    async def start_workers(self):
        """Start background workers."""
        for i in range(self.worker_count):
            worker_id = f"worker-{i}"
            task = asyncio.create_task(self._worker_loop(worker_id))
            self.workers[worker_id] = task

    async def stop_workers(self):
        """Stop all workers."""
        for worker_id, task in self.workers.items():
            task.cancel()
        self.workers.clear()

    async def _worker_loop(self, worker_id: str):
        """Worker loop — blocks on Redis, falls back to Postgres polling."""
        print(f"[TaskQueue] Worker {worker_id} started")

        while True:
            try:
                task = await self._dequeue_task(worker_id)
                if task:
                    await self._execute_task(task, worker_id)
                else:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                print(f"[TaskQueue] Worker {worker_id} stopped")
                break
            except Exception as e:
                print(f"[TaskQueue] Worker {worker_id} error: {e}")
                await asyncio.sleep(5)

    # ── Dequeue ──────────────────────────────────────────────────────────

    async def _dequeue_task(self, worker_id: str) -> Optional[dict]:
        """
        Get next task to run.

        Try Redis BRPOP first (instant wakeup on new task).
        Fall back to Postgres scan for retries / pre-existing tasks.
        """
        # Fast path: Redis pop
        task_id = await self._pop_from_redis()
        if task_id:
            return await self._claim_task(task_id, worker_id)

        # Slow path: scan Postgres for scheduled retries
        return await self._scan_postgres(worker_id)

    async def _pop_from_redis(self) -> Optional[str]:
        """Non-blocking pop from Redis task list."""
        try:
            from officeplane.management.redis_client import pop_task
            return await pop_task(timeout=2.0)
        except Exception:
            # Redis unavailable — fall through to Postgres
            return None

    async def _claim_task(self, task_id: str, worker_id: str) -> Optional[dict]:
        """Mark a task as RUNNING in Postgres. Acquire document lock if needed."""
        db = await get_db()

        task = await db.task.find_unique(where={"id": task_id})
        if not task or task.state not in (TaskState.QUEUED, TaskState.RETRYING):
            return None

        # Acquire document lock if task targets a specific document
        if task.documentId:
            locked = await self._acquire_lock(task.documentId, task_id)
            if not locked:
                # Couldn't get lock — re-queue for later
                try:
                    from officeplane.management.redis_client import push_task
                    await push_task(task_id, task.priority.value)
                except Exception:
                    pass
                return None

        updated = await db.task.update(
            where={"id": task_id},
            data={
                "state": TaskState.RUNNING,
                "startedAt": datetime.utcnow(),
                "workerId": worker_id,
                "workerHost": "localhost",
            },
        )
        return updated.model_dump()

    async def _scan_postgres(self, worker_id: str) -> Optional[dict]:
        """Fallback: scan Postgres for ready tasks (retries, pre-Redis tasks)."""
        db = await get_db()

        task = await db.task.find_first(
            where={
                "state": {"in": [TaskState.QUEUED, TaskState.RETRYING]},
                "scheduledFor": {"lte": datetime.utcnow()},
            },
            order=[{"priority": "desc"}, {"createdAt": "asc"}],
        )
        if not task:
            return None

        # Acquire document lock if needed
        if task.documentId:
            locked = await self._acquire_lock(task.documentId, task.id)
            if not locked:
                return None  # Someone else has this document, skip

        updated = await db.task.update(
            where={"id": task.id},
            data={
                "state": TaskState.RUNNING,
                "startedAt": datetime.utcnow(),
                "workerId": worker_id,
                "workerHost": "localhost",
            },
        )
        return updated.model_dump()

    # ── Document locking ─────────────────────────────────────────────────

    async def _acquire_lock(self, document_id: str, holder: str) -> bool:
        """Try to acquire a document-level lock via Redis."""
        try:
            from officeplane.management.redis_client import acquire_document_lock
            return await acquire_document_lock(document_id, holder, timeout=5.0)
        except Exception as e:
            # Redis down — allow execution (degrade gracefully)
            print(f"[TaskQueue] Lock fallback (Redis unavailable): {e}")
            return True

    async def _release_lock(self, document_id: str, holder: str) -> None:
        """Release document lock."""
        try:
            from officeplane.management.redis_client import release_document_lock
            await release_document_lock(document_id, holder)
        except Exception:
            pass

    # ── Execution ────────────────────────────────────────────────────────

    async def _execute_task(self, task: dict, worker_id: str):
        """Execute a task, then release lock."""
        db = await get_db()
        task_id = task["id"]
        document_id = task.get("documentId")
        start_time = datetime.utcnow()

        try:
            print(f"[TaskQueue] {worker_id} executing task {task_id}: {task['taskType']}")

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

            result = await self._run_task_logic(task)

            end_time = datetime.utcnow()
            await db.task.update(
                where={"id": task_id},
                data={
                    "state": TaskState.COMPLETED,
                    "completedAt": end_time,
                    "result": result,
                },
            )
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
            error_message = str(e)
            error_stack = traceback.format_exc()
            end_time = datetime.utcnow()

            print(f"[TaskQueue] Task {task_id} failed: {error_message}")

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

            retry_count = task["retryCount"] + 1
            max_retries = task["maxRetries"]

            if retry_count < max_retries:
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
                    f"[TaskQueue] Task {task_id} will retry in {delay}s "
                    f"(attempt {retry_count}/{max_retries})"
                )
            else:
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

        finally:
            # Always release document lock and mark task done in Redis
            if document_id:
                await self._release_lock(document_id, task_id)
            try:
                from officeplane.management.redis_client import task_done
                await task_done(task_id)
            except Exception:
                pass

    # ── Task logic dispatch ──────────────────────────────────────────────

    async def _run_task_logic(self, task: dict) -> dict:
        """Execute task-specific logic."""
        task_type = task["taskType"]
        payload = task["payload"]

        if task_type == "skill_run":
            return await self._run_skill_job(task["id"], payload)

        if task_type == "content_generate":
            return await self._run_content_generate(task["id"], payload)

        elif task_type == "convert_to_pdf":
            await asyncio.sleep(2)
            return {"status": "converted", "pages": 5}

        elif task_type == "render_images":
            await asyncio.sleep(3)
            return {"status": "rendered", "images": 10}

        elif task_type == "export_document":
            await asyncio.sleep(1.5)
            return {"status": "exported", "file_path": "/tmp/output.docx"}

        else:
            await asyncio.sleep(1)
            return {"status": "completed"}

    def _skill_executor(self):
        if not hasattr(self, "_executor_singleton"):
            from officeplane.content_agent.skill_executor import SkillExecutor

            self._executor_singleton = SkillExecutor()
        return self._executor_singleton

    async def _run_skill_job(self, job_id: str, payload: dict) -> dict:
        """Execute a skill-based job."""
        from officeplane.content_agent.skill_executor import (
            SkillExecutor,
            SkillNotFoundError,
            SkillInputError,
        )

        skill_name = payload["skill"]
        inputs = payload.get("params", {})

        # New SKILL.md path first
        try:
            executor = self._skill_executor()
            executor.get_skill(skill_name)
        except SkillNotFoundError:
            executor = None

        if executor is not None:
            from officeplane.content_agent.streaming import sse_manager

            if job_id not in sse_manager._streams:
                sse_manager.create_stream(job_id)
            await sse_manager.push_event(
                job_id, "start", {"job_id": job_id, "skill": skill_name}
            )
            try:
                output = await executor.invoke(skill_name, inputs)
            except SkillInputError as exc:
                await sse_manager.push_event(
                    job_id, "stop", {"status": "failed", "error": str(exc)}
                )
                return {"status": "failed", "error": str(exc)}
            await sse_manager.push_event(
                job_id, "stop", {"status": "completed", "output": output}
            )
            return {"status": "completed", "output": output}

        # Legacy path (preserved as-is below)
        from officeplane.skills import registry
        from officeplane.skills.base import SkillContext
        from officeplane.content_agent.config import ContentAgentConfig
        from officeplane.content_agent.workspace import WorkspaceManager
        from officeplane.content_agent.streaming import sse_manager

        if job_id not in sse_manager._streams:
            sse_manager.create_stream(job_id)

        config = ContentAgentConfig.from_env()
        workspace = WorkspaceManager(config.workspace_root).create(job_id)
        model = payload.get("model") or config.model

        await sse_manager.push_event(job_id, "start", {"job_id": job_id, "skill": skill_name})

        try:
            skill = registry.get(skill_name)
            ctx = SkillContext(
                job_id=job_id,
                workspace=workspace,
                model=model,
                driver=payload.get("driver", skill.default_driver),
                params=inputs,
            )

            result = await skill.run(ctx)

            errors = await skill.validate(ctx, result)
            if errors:
                result.errors.extend(errors)

            if result.succeeded:
                result = await skill.quality_check(ctx, result)

            await sse_manager.push_event(job_id, "stop", {
                "status": result.status,
                "output": result.output,
                "errors": result.errors,
            })

            return {"status": result.status, **result.output, "errors": result.errors}

        except Exception as exc:
            await sse_manager.push_event(job_id, "stop", {
                "status": "failed", "error": str(exc),
            })
            raise

    async def _run_content_generate(self, job_id: str, payload: dict) -> dict:
        """Run content generation agent."""
        from officeplane.content_agent.config import ContentAgentConfig
        from officeplane.content_agent.models import OutputFormat
        from officeplane.content_agent.runner import ContentAgentRunner
        from officeplane.content_agent.streaming import sse_manager

        if job_id not in sse_manager._streams:
            sse_manager.create_stream(job_id)

        config = ContentAgentConfig.from_env()
        runner = ContentAgentRunner(config)
        output_format = OutputFormat(payload.get("output_format", "pptx"))

        result = await runner.run(
            job_id=job_id,
            prompt=payload["prompt"],
            output_format=output_format,
            model_override=payload.get("model"),
            options=payload.get("options", {}),
            driver=payload.get("driver", "deepagents_sdk"),
        )
        return result

    # ── Public API ───────────────────────────────────────────────────────

    async def enqueue_task(
        self,
        task_type: str,
        payload: dict[str, Any],
        task_name: Optional[str] = None,
        document_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
    ) -> dict:
        """Add a new task to the queue."""
        db = await get_db()
        trace_id = f"task-{uuid4()}"

        task = await db.task.create(
            data={
                "taskType": task_type,
                "taskName": task_name,
                "documentId": document_id,
                "payload": payload,
                "priority": priority,
                "maxRetries": max_retries,
                "metadata": {"traceId": trace_id},
            }
        )

        # Push to Redis for instant worker wakeup
        try:
            from officeplane.management.redis_client import push_task
            await push_task(task.id, priority.value if hasattr(priority, 'value') else priority)
        except Exception as e:
            print(f"[TaskQueue] Redis push failed (will poll): {e}")

        print(f"[TaskQueue] Enqueued task {task.id}: {task_type}")
        return task.model_dump()

    async def cancel_task(self, task_id: str) -> dict:
        """Cancel a task."""
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
        """Manually retry a failed task."""
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
        # Push to Redis
        try:
            from officeplane.management.redis_client import push_task
            await push_task(task.id, task.priority.value)
        except Exception:
            pass
        return task.model_dump()

    async def get_task(self, task_id: str) -> Optional[dict]:
        """Get task by ID."""
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
        """List tasks."""
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
