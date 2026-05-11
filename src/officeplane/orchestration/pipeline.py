"""Pipeline orchestrator — run a sequence of skill invocations with output piping.

Pipeline spec shape (JSON-serialisable, validated at submission time):

{
  "name": "Ingested-PDF-to-Excel",
  "steps": [
    {
      "alias": "extract",
      "skill": "extract-tabular-data",
      "inputs": {"document_id": "${parameters.source_document_id}"}
    },
    {
      "alias": "apply",
      "skill": "xlsx-template-apply",
      "inputs": {
        "template_id": "${parameters.template_id}",
        "tables": "${steps.extract.outputs.tables_by_name}"
      }
    }
  ]
}

Each step's `inputs` can reference earlier step outputs and pipeline parameters.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from prisma import Json, Prisma

from officeplane.orchestration.refs import resolve

log = logging.getLogger("officeplane.orchestration.pipeline")


SkillInvoker = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


async def _default_invoker(skill_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Invoke a skill via the existing SkillExecutor + handler.py dispatch."""
    from officeplane.content_agent.skill_executor import SkillExecutor
    executor = SkillExecutor()
    return await executor.invoke(skill_name, inputs)


def validate_spec(spec: dict[str, Any]) -> None:
    steps = spec.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("spec.steps must be a non-empty list")
    aliases_seen: set[str] = set()
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            raise ValueError(f"step {i}: must be an object")
        if not s.get("skill") or not isinstance(s["skill"], str):
            raise ValueError(f"step {i}: 'skill' (str) is required")
        alias = s.get("alias")
        if alias:
            if not isinstance(alias, str):
                raise ValueError(f"step {i}: alias must be a string")
            if alias in aliases_seen:
                raise ValueError(f"step {i}: duplicate alias '{alias}'")
            aliases_seen.add(alias)
        inputs = s.get("inputs") or {}
        if not isinstance(inputs, dict):
            raise ValueError(f"step {i}: inputs must be an object")


async def run_pipeline(
    spec: dict[str, Any],
    *,
    parameters: dict[str, Any] | None = None,
    actor: str | None = None,
    invoker: SkillInvoker | None = None,
    db: Prisma | None = None,
) -> dict[str, Any]:
    """Execute a pipeline spec. Returns {run_id, state, step_count, outputs}.

    Each step's status is persisted to pipeline_steps as it progresses.
    """
    validate_spec(spec)
    parameters = parameters or {}
    invoker = invoker or _default_invoker
    own_db = db is None
    if own_db:
        db = Prisma()
        await db.connect()

    try:
        import json as _json
        run = await db.pipelinerun.create(data={
            "name": spec.get("name"),
            "spec": Json(_json.dumps(spec)),
            "state": "RUNNING",
            "parameters": Json(_json.dumps(parameters)),
            "actor": actor,
        })
        run_id = run.id

        step_outputs_by_alias: dict[str, dict[str, Any]] = {}
        step_outputs_by_index: list[dict[str, Any]] = []
        run_state = "SUCCESS"
        error_message: str | None = None

        for idx, step_spec in enumerate(spec["steps"]):
            alias = step_spec.get("alias") or f"step_{idx}"
            skill_name = step_spec["skill"]
            raw_inputs = step_spec.get("inputs") or {}
            resolved_inputs = resolve(
                raw_inputs,
                parameters=parameters,
                step_outputs=step_outputs_by_alias,
            )
            # Create the step row (QUEUED → RUNNING)
            step_row = await db.pipelinestep.create(data={
                "runId": run_id,
                "stepIndex": idx,
                "alias": alias,
                "skill": skill_name,
                "inputs": Json(_json.dumps(resolved_inputs)),
                "state": "RUNNING",
                "startedAt": _now(),
            })
            t0 = time.time()
            try:
                outputs = await invoker(skill_name, resolved_inputs)
                if not isinstance(outputs, dict):
                    outputs = {"value": outputs}
                duration_ms = int((time.time() - t0) * 1000)
                await db.pipelinestep.update(
                    where={"id": step_row.id},
                    data={
                        "state": "SUCCESS",
                        "outputs": Json(_json.dumps(outputs)),
                        "finishedAt": _now(),
                        "durationMs": duration_ms,
                    },
                )
                step_outputs_by_alias[alias] = outputs
                step_outputs_by_index.append(outputs)
            except Exception as e:
                duration_ms = int((time.time() - t0) * 1000)
                msg = f"{type(e).__name__}: {e}"
                log.warning("pipeline step %s failed: %s", alias, msg)
                await db.pipelinestep.update(
                    where={"id": step_row.id},
                    data={
                        "state": "FAILED",
                        "errorMessage": msg,
                        "finishedAt": _now(),
                        "durationMs": duration_ms,
                    },
                )
                run_state = "FAILED"
                error_message = f"step {idx} ({alias}): {msg}"
                break

        await db.pipelinerun.update(
            where={"id": run_id},
            data={
                "state": run_state,
                "errorMessage": error_message,
                "finishedAt": _now(),
            },
        )

        return {
            "run_id": run_id,
            "state": run_state,
            "step_count": len(spec["steps"]),
            "completed_count": len(step_outputs_by_index),
            "step_outputs": step_outputs_by_alias,
            "error_message": error_message,
        }
    finally:
        if own_db:
            await db.disconnect()


async def resume_pipeline(run_id: str, *, db: Prisma | None = None) -> dict[str, Any]:
    """Re-run only the FAILED + later steps of an existing run.
    Uses the spec stored on the run; substitutes outputs from prior SUCCESS steps."""
    own_db = db is None
    if own_db:
        db = Prisma()
        await db.connect()
    try:
        run = await db.pipelinerun.find_unique(where={"id": run_id})
        if not run:
            raise ValueError(f"run not found: {run_id}")
        import json as _json
        raw_spec = run.spec
        if isinstance(raw_spec, str):
            spec = _json.loads(raw_spec)
        else:
            spec = raw_spec
        parameters = run.parameters or {}
        if isinstance(parameters, str):
            parameters = _json.loads(parameters)

        # Load existing step rows; replay SUCCESS, restart from FAILED onward
        steps_in_db = await db.pipelinestep.find_many(
            where={"runId": run_id}, order={"stepIndex": "asc"},
        )
        outputs_by_alias: dict[str, dict[str, Any]] = {}
        first_failed_idx: int | None = None
        for s in steps_in_db:
            if s.state == "SUCCESS":
                outs = s.outputs
                if isinstance(outs, str):
                    outs = _json.loads(outs)
                outputs_by_alias[s.alias or f"step_{s.stepIndex}"] = outs or {}
            elif first_failed_idx is None:
                first_failed_idx = s.stepIndex
        if first_failed_idx is None:
            return {"run_id": run_id, "state": run.state, "step_count": len(steps_in_db),
                    "completed_count": len(steps_in_db), "note": "nothing to resume"}

        # Run the suffix
        await db.pipelinerun.update(
            where={"id": run_id},
            data={"state": "RUNNING", "errorMessage": None, "finishedAt": None},
        )
        run_state = "SUCCESS"
        error_message: str | None = None

        for idx in range(first_failed_idx, len(spec["steps"])):
            step_spec = spec["steps"][idx]
            alias = step_spec.get("alias") or f"step_{idx}"
            skill_name = step_spec["skill"]
            resolved_inputs = resolve(
                step_spec.get("inputs") or {},
                parameters=parameters,
                step_outputs=outputs_by_alias,
            )
            # Reset row (in case it exists as FAILED)
            existing = next((s for s in steps_in_db if s.stepIndex == idx), None)
            if existing:
                await db.pipelinestep.update(
                    where={"id": existing.id},
                    data={
                        "state": "RUNNING", "errorMessage": None,
                        "inputs": Json(_json.dumps(resolved_inputs)),
                        "startedAt": _now(), "finishedAt": None, "durationMs": None,
                        "outputs": Json("{}"),
                    },
                )
                step_id = existing.id
            else:
                step_row = await db.pipelinestep.create(data={
                    "runId": run_id, "stepIndex": idx, "alias": alias,
                    "skill": skill_name,
                    "inputs": Json(_json.dumps(resolved_inputs)),
                    "state": "RUNNING", "startedAt": _now(),
                })
                step_id = step_row.id

            t0 = time.time()
            try:
                outputs = await _default_invoker(skill_name, resolved_inputs)
                if not isinstance(outputs, dict):
                    outputs = {"value": outputs}
                await db.pipelinestep.update(
                    where={"id": step_id},
                    data={
                        "state": "SUCCESS",
                        "outputs": Json(_json.dumps(outputs)),
                        "finishedAt": _now(),
                        "durationMs": int((time.time() - t0) * 1000),
                    },
                )
                outputs_by_alias[alias] = outputs
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                await db.pipelinestep.update(
                    where={"id": step_id},
                    data={
                        "state": "FAILED",
                        "errorMessage": msg,
                        "finishedAt": _now(),
                        "durationMs": int((time.time() - t0) * 1000),
                    },
                )
                run_state = "FAILED"
                error_message = f"step {idx} ({alias}): {msg}"
                break

        await db.pipelinerun.update(
            where={"id": run_id},
            data={"state": run_state, "errorMessage": error_message, "finishedAt": _now()},
        )
        return {"run_id": run_id, "state": run_state, "step_count": len(spec["steps"]),
                "completed_count": len(outputs_by_alias), "error_message": error_message}
    finally:
        if own_db:
            await db.disconnect()
