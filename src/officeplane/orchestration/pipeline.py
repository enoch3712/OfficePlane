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
import officeplane.orchestration.refs as _refs_mod

log = logging.getLogger("officeplane.orchestration.pipeline")


def _resolve_iter(
    inputs: Any,
    *,
    parameters: dict[str, Any],
    step_outputs: dict[str, Any],
    extra_root: dict[str, Any] | None = None,
) -> Any:
    """Like resolve() but also exposes `extra_root` keys at the top level of the ctx.

    Used by foreach to make the bound iteration variable (e.g. ``item``, ``doc``) directly
    addressable as ``${item}`` / ``${doc.id}`` rather than ``${parameters.item}``.
    """
    if extra_root is None:
        return resolve(inputs, parameters=parameters, step_outputs=step_outputs)
    ctx: dict[str, Any] = {
        "parameters": parameters,
        "steps": {a: {"outputs": o} for a, o in step_outputs.items()},
        **extra_root,
    }
    return _refs_mod._walk(inputs, ctx)  # noqa: SLF001


SkillInvoker = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


async def _default_invoker(skill_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Invoke a skill via the existing SkillExecutor + handler.py dispatch."""
    from officeplane.content_agent.skill_executor import SkillExecutor
    executor = SkillExecutor()
    return await executor.invoke(skill_name, inputs)


def _validate_step(step: Any, idx_label: str) -> None:
    """Validate either a regular skill step or a foreach step."""
    if not isinstance(step, dict):
        raise ValueError(f"step {idx_label}: must be an object")
    step_type = step.get("type")
    if step_type == "foreach":
        if not step.get("alias") or not isinstance(step["alias"], str):
            raise ValueError(f"step {idx_label}: foreach requires an alias")
        if "over" not in step:
            raise ValueError(f"step {idx_label}: foreach requires 'over' (ref or list)")
        if not step.get("as") or not isinstance(step["as"], str):
            raise ValueError(f"step {idx_label}: foreach requires 'as' (item binding name)")
        do = step.get("do")
        if not isinstance(do, list) or not do:
            raise ValueError(f"step {idx_label}: foreach 'do' must be a non-empty list")
        concurrency = step.get("concurrency", 1)
        if not isinstance(concurrency, int) or not (1 <= concurrency <= 10):
            raise ValueError(f"step {idx_label}: concurrency must be int in 1..10")
        # Validate sub-steps
        for j, sub in enumerate(do):
            _validate_step(sub, f"{idx_label}.do[{j}]")
        return
    # Regular skill step
    if not step.get("skill") or not isinstance(step["skill"], str):
        raise ValueError(f"step {idx_label}: 'skill' (str) is required")
    inputs = step.get("inputs") or {}
    if not isinstance(inputs, dict):
        raise ValueError(f"step {idx_label}: inputs must be an object")


def validate_spec(spec: dict[str, Any]) -> None:
    steps = spec.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("spec.steps must be a non-empty list")
    aliases_seen: set[str] = set()
    for i, s in enumerate(steps):
        _validate_step(s, str(i))
        alias = s.get("alias")
        if alias:
            if alias in aliases_seen:
                raise ValueError(f"step {i}: duplicate alias '{alias}'")
            aliases_seen.add(alias)


async def _execute_foreach(
    db: Prisma,
    run_id: str,
    parent_idx: int,
    step_spec: dict[str, Any],
    parameters: dict[str, Any],
    step_outputs_by_alias: dict[str, Any],
    invoker: SkillInvoker,
) -> tuple[dict[str, Any], bool]:
    """Run a foreach step. Returns (outputs_dict, success_bool)."""
    import asyncio
    import json as _json

    alias = step_spec["alias"]
    as_name = step_spec["as"]
    concurrency = int(step_spec.get("concurrency", 1))
    do_steps = step_spec["do"]

    # Resolve the over expression
    over_raw = step_spec["over"]
    over = resolve(over_raw, parameters=parameters, step_outputs=step_outputs_by_alias)
    if not isinstance(over, list):
        raise ValueError(
            f"foreach '{alias}': 'over' did not resolve to a list (got {type(over).__name__})"
        )

    # Insert parent foreach row
    parent_row = await db.pipelinestep.create(data={
        "runId": run_id,
        "stepIndex": parent_idx,
        "alias": alias,
        "skill": "_foreach_",
        "inputs": Json(_json.dumps({
            "foreach": True,
            "over_count": len(over),
            "concurrency": concurrency,
            "as": as_name,
        })),
        "state": "RUNNING",
        "startedAt": _now(),
    })

    async def _run_iteration(idx: int, item: Any) -> tuple[dict[str, Any], bool]:
        """Run the entire `do` sub-spec for one item. Returns (iter_outputs, ok)."""
        iter_params = {**parameters, as_name: item, "_index": idx}
        # Extra root so ${item} / ${doc.id} resolve without needing ${parameters.item}
        extra_root = {as_name: item, "_index": idx}
        iter_outputs: dict[str, Any] = {}
        ok = True
        for sub_idx, sub_step in enumerate(do_steps):
            # Use offset formula to avoid collision with parent row at step_index=parent_idx.
            # parent_idx * 10000 gives a block per top-level step;
            # +1000 ensures always > parent_idx (even when parent_idx==0);
            # idx * 100 + sub_idx spreads iterations within the block.
            sub_step_index = parent_idx * 10000 + 1000 + idx * 100 + sub_idx
            sub_alias = sub_step.get("alias") or f"step_{sub_idx}"
            namespaced_alias = f"{alias}.{idx}.{sub_alias}"

            sub_inputs = _resolve_iter(
                sub_step.get("inputs") or {},
                parameters=iter_params,
                step_outputs=iter_outputs,
                extra_root=extra_root,
            )
            sub_row = await db.pipelinestep.create(data={
                "runId": run_id,
                "stepIndex": sub_step_index,
                "alias": namespaced_alias,
                "skill": sub_step["skill"],
                "inputs": Json(_json.dumps(sub_inputs)),
                "state": "RUNNING",
                "startedAt": _now(),
            })
            t0 = time.time()
            try:
                out = await invoker(sub_step["skill"], sub_inputs)
                if not isinstance(out, dict):
                    out = {"value": out}
                await db.pipelinestep.update(
                    where={"id": sub_row.id},
                    data={
                        "state": "SUCCESS",
                        "outputs": Json(_json.dumps(out)),
                        "finishedAt": _now(),
                        "durationMs": int((time.time() - t0) * 1000),
                    },
                )
                iter_outputs[sub_alias] = out
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                await db.pipelinestep.update(
                    where={"id": sub_row.id},
                    data={
                        "state": "FAILED",
                        "errorMessage": msg,
                        "finishedAt": _now(),
                        "durationMs": int((time.time() - t0) * 1000),
                    },
                )
                ok = False
                break
        return iter_outputs, ok

    # Execute iterations with bounded concurrency
    iteration_results: list[tuple[dict[str, Any], bool] | None] = [None] * len(over)
    sem = asyncio.Semaphore(concurrency)

    async def _wrapped(i: int, item: Any) -> None:
        async with sem:
            res = await _run_iteration(i, item)
            iteration_results[i] = res  # type: ignore[assignment]

    if concurrency == 1:
        for i, item in enumerate(over):
            res = await _run_iteration(i, item)
            iteration_results[i] = res  # type: ignore[assignment]
    else:
        await asyncio.gather(*(_wrapped(i, item) for i, item in enumerate(over)))

    iterations_out = [r[0] for r in iteration_results if r is not None]
    successes = sum(1 for r in iteration_results if r is not None and r[1])
    failures = len(iteration_results) - successes
    parent_state = "SUCCESS" if failures == 0 else "FAILED"

    await db.pipelinestep.update(
        where={"id": parent_row.id},
        data={
            "state": parent_state,
            "outputs": Json(_json.dumps({
                "iterations": iterations_out,
                "count": len(iteration_results),
                "successes": successes,
                "failures": failures,
            })),
            "finishedAt": _now(),
            "errorMessage": (
                None if parent_state == "SUCCESS"
                else f"{failures}/{len(iteration_results)} iterations failed"
            ),
        },
    )

    return {
        "iterations": iterations_out,
        "count": len(iteration_results),
        "successes": successes,
        "failures": failures,
    }, parent_state == "SUCCESS"


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
            if step_spec.get("type") == "foreach":
                try:
                    foreach_out, ok = await _execute_foreach(
                        db, run_id, idx, step_spec,
                        parameters, step_outputs_by_alias, invoker,
                    )
                    step_outputs_by_alias[step_spec["alias"]] = foreach_out
                    step_outputs_by_index.append(foreach_out)
                    if not ok:
                        run_state = "FAILED"
                        error_message = (
                            f"foreach step {idx} ({step_spec['alias']}) had failures"
                        )
                        break
                except Exception as e:
                    msg = f"{type(e).__name__}: {e}"
                    log.warning("foreach %s failed: %s", step_spec.get("alias"), msg)
                    run_state = "FAILED"
                    error_message = f"step {idx} ({step_spec.get('alias', '')}): {msg}"
                    break
            else:
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
