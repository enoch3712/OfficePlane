import asyncio
import uuid

import pytest
from unittest.mock import AsyncMock

from officeplane.orchestration.pipeline import run_pipeline, validate_spec


def test_validate_foreach_requires_alias():
    spec = {"steps": [{"type": "foreach", "over": [1], "as": "x",
                       "do": [{"skill": "a"}]}]}
    with pytest.raises(ValueError, match="alias"):
        validate_spec(spec)


def test_validate_foreach_requires_as():
    spec = {"steps": [{"type": "foreach", "alias": "fe", "over": [1],
                       "do": [{"skill": "a"}]}]}
    with pytest.raises(ValueError, match="'as'"):
        validate_spec(spec)


def test_validate_foreach_requires_nonempty_do():
    spec = {"steps": [{"type": "foreach", "alias": "fe", "over": [1], "as": "x", "do": []}]}
    with pytest.raises(ValueError, match="'do'"):
        validate_spec(spec)


def test_validate_foreach_concurrency_bounds():
    base = {"type": "foreach", "alias": "fe", "over": [1], "as": "x",
            "do": [{"skill": "a"}]}
    with pytest.raises(ValueError, match="concurrency"):
        validate_spec({"steps": [{**base, "concurrency": 0}]})
    with pytest.raises(ValueError, match="concurrency"):
        validate_spec({"steps": [{**base, "concurrency": 20}]})


def test_validate_foreach_recurses_into_substeps():
    spec = {"steps": [{
        "type": "foreach", "alias": "fe", "over": [1], "as": "x",
        "do": [{"alias": "ok", "skill": "a"}, {"alias": "missing_skill"}],
    }]}
    with pytest.raises(ValueError, match="skill"):
        validate_spec(spec)


@pytest.mark.asyncio
async def test_foreach_iterates_sequentially():
    """Run foreach over [a, b, c] with a single skill — confirm 3 iteration outputs."""
    from prisma import Prisma
    invocations = []
    async def fake_invoker(skill, inputs):
        invocations.append((skill, inputs))
        return {"echo": inputs.get("x"), "skill": skill}

    spec = {
        "name": "fe-seq",
        "steps": [
            {"type": "foreach", "alias": "fe", "over": ["a", "b", "c"], "as": "item",
             "do": [{"alias": "echo", "skill": "echo-skill",
                     "inputs": {"x": "${item}"}}]},
        ]
    }

    db = Prisma()
    await db.connect()
    try:
        result = await run_pipeline(spec=spec, invoker=fake_invoker, db=db)
        assert result["state"] == "SUCCESS"
        # The foreach output should be in step_outputs.fe
        fe = result["step_outputs"]["fe"]
        assert fe["count"] == 3
        assert fe["successes"] == 3
        assert fe["failures"] == 0
        # Each iteration's echo output should reflect the bound item
        echoes = [it["echo"]["echo"] for it in fe["iterations"]]
        assert echoes == ["a", "b", "c"]
        # Cleanup
        await db.pipelinestep.delete_many(where={"runId": result["run_id"]})
        await db.pipelinerun.delete(where={"id": result["run_id"]})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_foreach_piped_from_prior_step():
    """The list comes from an earlier step's output."""
    from prisma import Prisma
    async def fake_invoker(skill, inputs):
        if skill == "list-skill":
            return {"items": [{"id": "x"}, {"id": "y"}]}
        return {"got": inputs.get("doc_id")}

    spec = {
        "steps": [
            {"alias": "lst", "skill": "list-skill", "inputs": {}},
            {"type": "foreach", "alias": "fe", "over": "${steps.lst.outputs.items}",
             "as": "doc",
             "do": [{"alias": "ext", "skill": "ext-skill",
                     "inputs": {"doc_id": "${doc.id}"}}]},
        ]
    }
    db = Prisma()
    await db.connect()
    try:
        result = await run_pipeline(spec=spec, invoker=fake_invoker, db=db)
        assert result["state"] == "SUCCESS"
        fe = result["step_outputs"]["fe"]
        assert fe["count"] == 2
        got_ids = [it["ext"]["got"] for it in fe["iterations"]]
        assert got_ids == ["x", "y"]
        await db.pipelinestep.delete_many(where={"runId": result["run_id"]})
        await db.pipelinerun.delete(where={"id": result["run_id"]})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_foreach_continues_after_individual_failure_marked():
    """One iteration fails. Pipeline overall is FAILED but the foreach reports per-iteration status."""
    from prisma import Prisma
    async def fake_invoker(skill, inputs):
        if inputs.get("x") == "bad":
            raise RuntimeError("boom on bad")
        return {"ok": True}

    spec = {
        "steps": [
            {"type": "foreach", "alias": "fe", "over": ["good1", "bad", "good2"], "as": "v",
             "do": [{"alias": "do", "skill": "s", "inputs": {"x": "${v}"}}]},
        ]
    }
    db = Prisma()
    await db.connect()
    try:
        result = await run_pipeline(spec=spec, invoker=fake_invoker, db=db)
        assert result["state"] == "FAILED"
        fe = result["step_outputs"]["fe"]
        # Sequential mode stops the failing iteration but still records the others' attempts
        assert fe["count"] == 3
        assert fe["failures"] >= 1
        await db.pipelinestep.delete_many(where={"runId": result["run_id"]})
        await db.pipelinerun.delete(where={"id": result["run_id"]})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_foreach_parallel_concurrency_3():
    """3 concurrent iterations — confirm timing is roughly 1x per item, not Nx."""
    import time
    from prisma import Prisma

    async def fake_invoker(skill, inputs):
        await asyncio.sleep(0.2)
        return {"item": inputs.get("v")}

    spec = {
        "steps": [
            {"type": "foreach", "alias": "fe", "over": [1, 2, 3, 4, 5, 6],
             "as": "v", "concurrency": 3,
             "do": [{"alias": "s", "skill": "slow",
                     "inputs": {"v": "${v}"}}]},
        ]
    }
    db = Prisma()
    await db.connect()
    try:
        t0 = time.time()
        result = await run_pipeline(spec=spec, invoker=fake_invoker, db=db)
        elapsed = time.time() - t0
        # 6 items × 0.2s sequential = 1.2s. With concurrency=3 it should be ~0.4-0.7s.
        assert elapsed < 1.0, f"concurrency=3 took {elapsed:.2f}s — expected <1.0s"
        assert result["state"] == "SUCCESS"
        assert result["step_outputs"]["fe"]["count"] == 6
        await db.pipelinestep.delete_many(where={"runId": result["run_id"]})
        await db.pipelinerun.delete(where={"id": result["run_id"]})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_foreach_raises_when_over_not_a_list():
    from prisma import Prisma
    async def fake_invoker(skill, inputs):
        return {}
    spec = {
        "steps": [
            {"type": "foreach", "alias": "fe", "over": "not-a-list", "as": "x",
             "do": [{"alias": "s", "skill": "s", "inputs": {}}]},
        ]
    }
    db = Prisma()
    await db.connect()
    try:
        result = await run_pipeline(spec=spec, invoker=fake_invoker, db=db)
        assert result["state"] == "FAILED"
        assert "did not resolve to a list" in (result["error_message"] or "")
    finally:
        await db.disconnect()
