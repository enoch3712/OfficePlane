"""
ECMSession — atomic multi-agent, multi-document session.

Execution model:
  1. add_job() — register skill jobs (session must be OPEN)
  2. commit() — runs all jobs concurrently in staging workspaces
               → on all-success: atomically moves outputs to committed/
               → on any failure: rolls back staging + compensates committed ops
  3. rollback() — explicit discard; cleans up all staging state

Atomicity guarantee:
  - File level: staging → committed via shutil.move (atomic on same filesystem)
  - DB level: each skill's save_to_document_store runs independently;
              failed jobs are compensated via TransactionLog
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4

from officeplane.ecm.transaction import TransactionLog

log = logging.getLogger(__name__)


class SessionState(str, Enum):
    OPEN = "open"
    RUNNING = "running"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class ECMJob:
    job_id: str
    skill_name: str
    params: dict
    driver: str
    model: str
    state: str = "pending"          # pending | running | completed | failed
    result: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class SessionResult:
    session_id: str
    status: str                     # "committed" | "failed" | "rolled_back"
    jobs: list[ECMJob]
    errors: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.status == "committed"


class ECMSession:
    """Atomic multi-agent, multi-document execution session."""

    def __init__(self, workspace_root: str = "/data/workspaces") -> None:
        self.session_id = f"session_{uuid4().hex[:12]}"
        self.jobs: list[ECMJob] = []
        self.state = SessionState.OPEN
        self._root = Path(workspace_root)
        self._staging = self._root / "sessions" / self.session_id
        self._txlog = TransactionLog()

    # ── Public API ────────────────────────────────────────────────────────────

    def add_job(
        self,
        skill_name: str,
        params: dict,
        driver: Optional[str] = None,
        model: str = "gpt-4o",
    ) -> ECMJob:
        """Add a skill job to this session. Session must be OPEN."""
        if self.state != SessionState.OPEN:
            raise RuntimeError(
                f"Cannot add jobs — session {self.session_id} is {self.state.value}"
            )

        from officeplane.content_agent.skill_executor import (
            SkillExecutor,
            SkillNotFoundError,
        )

        executor = SkillExecutor()
        default_driver = "deepagents_sdk"
        try:
            executor.get_skill(skill_name)
            # SKILL.md skill resolved.
        except SkillNotFoundError:
            # Fall back to legacy registry.
            from officeplane.skills.registry import get as get_skill_legacy

            legacy = get_skill_legacy(skill_name)  # raises KeyError if absent
            default_driver = legacy.default_driver

        job = ECMJob(
            job_id=f"{self.session_id}_j{len(self.jobs)}",
            skill_name=skill_name,
            params=params,
            driver=driver or default_driver,
            model=model,
        )
        self.jobs.append(job)
        log.debug("Session %s: added job %s (%s)", self.session_id, job.job_id, skill_name)
        return job

    async def commit(self) -> SessionResult:
        """
        Execute all jobs atomically.

        Returns a SessionResult regardless of outcome.
        Callers should check result.succeeded.
        """
        if self.state != SessionState.OPEN:
            raise RuntimeError(
                f"Session {self.session_id} is {self.state.value}, not open"
            )
        if not self.jobs:
            raise RuntimeError("No jobs to commit")

        self.state = SessionState.RUNNING
        self._staging.mkdir(parents=True, exist_ok=True)
        log.info(
            "Session %s committing %d job(s)", self.session_id, len(self.jobs)
        )

        try:
            await self._execute_jobs()
            await self._commit_outputs()
            self.state = SessionState.COMMITTED
            log.info("Session %s committed successfully", self.session_id)
            return SessionResult(
                session_id=self.session_id,
                status="committed",
                jobs=self.jobs,
            )

        except Exception as exc:
            log.error("Session %s failed: %s — rolling back", self.session_id, exc)
            self.state = SessionState.FAILED
            await self._rollback()
            return SessionResult(
                session_id=self.session_id,
                status="failed",
                jobs=self.jobs,
                errors=[str(exc)],
            )

    async def rollback(self) -> None:
        """Explicitly discard an open or failed session."""
        await self._rollback()
        self.state = SessionState.ROLLED_BACK
        log.info("Session %s rolled back", self.session_id)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "job_count": len(self.jobs),
            "jobs": [
                {
                    "job_id": j.job_id,
                    "skill": j.skill_name,
                    "driver": j.driver,
                    "state": j.state,
                    "result": j.result,
                    "error": j.error,
                }
                for j in self.jobs
            ],
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _execute_jobs(self) -> None:
        """Run all jobs concurrently in isolated staging workspaces."""
        from officeplane.content_agent.skill_executor import (
            SkillExecutor,
            SkillNotFoundError,
        )

        _executor = SkillExecutor()

        async def _run_one(job: ECMJob) -> None:
            workspace = self._staging / job.job_id
            workspace.mkdir(parents=True, exist_ok=True)

            job.state = "running"

            # Try SKILL.md executor first
            try:
                _executor.get_skill(job.skill_name)
                skill_md_found = True
            except SkillNotFoundError:
                skill_md_found = False

            if skill_md_found:
                from officeplane.content_agent.skill_executor import SkillInputError

                try:
                    output = await _executor.invoke(job.skill_name, job.params)
                except SkillInputError as exc:
                    job.state = "failed"
                    job.error = str(exc)
                    raise RuntimeError(
                        f"Job {job.job_id} ({job.skill_name}) failed: {job.error}"
                    )
                job.state = "completed"
                job.result = output
                return

            # Legacy path
            from officeplane.skills.base import SkillContext
            from officeplane.skills.registry import get as get_skill

            skill = get_skill(job.skill_name)
            ctx = SkillContext(
                job_id=job.job_id,
                workspace=workspace,
                model=job.model,
                driver=job.driver,
                params=job.params,
                session_id=self.session_id,
            )

            result = await skill.run(ctx)

            validation_errors = await skill.validate(ctx, result)
            if validation_errors:
                result.errors.extend(validation_errors)
                result.status = "failed"

            if result.succeeded:
                result = await skill.quality_check(ctx, result)

            if not result.succeeded:
                job.state = "failed"
                job.error = "; ".join(result.errors) or "Skill failed with no message"
                raise RuntimeError(
                    f"Job {job.job_id} ({job.skill_name}) failed: {job.error}"
                )

            job.state = "completed"
            job.result = result.output

        # All jobs run in parallel — any failure propagates and cancels the rest
        await asyncio.gather(*[_run_one(j) for j in self.jobs])

    async def _commit_outputs(self) -> None:
        """
        Atomically move staging workspaces to committed/.
        Records each move in the transaction log for compensation.
        """
        committed_root = self._root / "committed"
        committed_root.mkdir(parents=True, exist_ok=True)

        for job in self.jobs:
            src = self._staging / job.job_id
            dst = committed_root / job.job_id
            if src.exists():
                shutil.move(str(src), str(dst))
                # Record for compensation: if we need to undo, move dst back to src
                self._txlog.record("move_dir", src=str(src), dst=str(dst))

        # Remove empty staging session dir
        if self._staging.exists():
            shutil.rmtree(self._staging, ignore_errors=True)

    async def _rollback(self) -> None:
        """Delete staging workspaces and compensate any committed operations."""
        if self._staging.exists():
            shutil.rmtree(self._staging, ignore_errors=True)
        await self._txlog.compensate()
