"""Pipeline orchestration endpoints."""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from prisma import Json, Prisma
from pydantic import BaseModel, Field

from officeplane.orchestration.pipeline import run_pipeline, resume_pipeline, validate_spec

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])
log = logging.getLogger("officeplane.api.pipelines")


class StepSpec(BaseModel):
    model_config = {"extra": "allow", "populate_by_name": True}

    alias: str | None = None
    skill: str | None = None  # None for foreach steps; required for regular steps
    inputs: dict[str, Any] = Field(default_factory=dict)


class PipelineSpec(BaseModel):
    model_config = {"extra": "allow"}

    name: str | None = None
    steps: list[StepSpec]


class RunRequest(BaseModel):
    spec: PipelineSpec
    parameters: dict[str, Any] = Field(default_factory=dict)
    actor: str | None = None
    sync: bool = Field(default=False, description="If true, wait for the run to finish before returning")


@router.post("/run")
async def run(req: RunRequest, background: BackgroundTasks):
    spec_dict = json.loads(req.spec.model_dump_json())
    try:
        validate_spec(spec_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if req.sync:
        try:
            result = await run_pipeline(
                spec=spec_dict, parameters=req.parameters, actor=req.actor,
            )
            return result
        except Exception as e:
            log.exception("sync pipeline run failed")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Async: persist the run upfront so the caller has an id, then schedule background task
        db = Prisma()
        await db.connect()
        try:
            run_row = await db.pipelinerun.create(data={
                "name": spec_dict.get("name"),
                "spec": Json(json.dumps(spec_dict)),
                "state": "QUEUED",
                "parameters": Json(json.dumps(req.parameters)),
                "actor": req.actor,
            })
            run_id = run_row.id
        finally:
            await db.disconnect()

        async def _bg():
            try:
                # Delete the QUEUED placeholder row before running so we don't
                # leave a stale row alongside the real run row created by run_pipeline.
                pdb = Prisma()
                await pdb.connect()
                try:
                    await pdb.pipelinerun.delete(where={"id": run_id})
                finally:
                    await pdb.disconnect()
                await run_pipeline(spec=spec_dict, parameters=req.parameters, actor=req.actor)
            except Exception as e:
                log.exception("background pipeline run failed: %s", e)

        background.add_task(_bg)
        return {"run_id": run_id, "state": "QUEUED",
                "step_count": len(spec_dict["steps"]),
                "note": "Pipeline scheduled. Poll /api/pipelines/runs/{run_id} for status."}


@router.post("/runs/{run_id}/resume")
async def resume(run_id: str):
    try:
        return await resume_pipeline(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.exception("resume failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs")
async def list_runs(limit: int = 50, state: str | None = None):
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be 1..500")
    db = Prisma()
    await db.connect()
    try:
        where: dict[str, Any] = {}
        if state:
            where["state"] = state
        rows = await db.pipelinerun.find_many(
            where=where, order={"startedAt": "desc"}, take=limit,
        )
        return {"runs": [_run_summary(r) for r in rows]}
    finally:
        await db.disconnect()


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    db = Prisma()
    await db.connect()
    try:
        run = await db.pipelinerun.find_unique(where={"id": run_id})
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        steps = await db.pipelinestep.find_many(
            where={"runId": run_id}, order={"stepIndex": "asc"},
        )
        return {
            "run": _run_summary(run, full=True),
            "steps": [_step_summary(s) for s in steps],
        }
    finally:
        await db.disconnect()


def _run_summary(r, *, full: bool = False) -> dict[str, Any]:
    out = {
        "id": r.id, "name": r.name, "state": r.state, "actor": r.actor,
        "error_message": r.errorMessage,
        "started_at": r.startedAt.isoformat() if r.startedAt else None,
        "finished_at": r.finishedAt.isoformat() if r.finishedAt else None,
    }
    if full:
        s = r.spec
        if isinstance(s, str):
            try:
                s = json.loads(s)
            except Exception:
                s = {}
        p = r.parameters
        if isinstance(p, str):
            try:
                p = json.loads(p)
            except Exception:
                p = {}
        out["spec"] = s
        out["parameters"] = p
    return out


def _step_summary(s) -> dict[str, Any]:
    outs = s.outputs
    if isinstance(outs, str):
        try:
            outs = json.loads(outs)
        except Exception:
            outs = {}
    ins = s.inputs
    if isinstance(ins, str):
        try:
            ins = json.loads(ins)
        except Exception:
            ins = {}
    return {
        "id": s.id, "step_index": s.stepIndex, "alias": s.alias, "skill": s.skill,
        "state": s.state, "inputs": ins, "outputs": outs,
        "error_message": s.errorMessage,
        "started_at": s.startedAt.isoformat() if s.startedAt else None,
        "finished_at": s.finishedAt.isoformat() if s.finishedAt else None,
        "duration_ms": s.durationMs,
    }
