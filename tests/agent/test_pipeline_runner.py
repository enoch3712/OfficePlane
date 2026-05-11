import pytest

from officeplane.orchestration.pipeline import run_pipeline, validate_spec


def test_validate_spec_rejects_empty_steps():
    with pytest.raises(ValueError, match="non-empty list"):
        validate_spec({"steps": []})


def test_validate_spec_rejects_missing_skill():
    with pytest.raises(ValueError, match="skill"):
        validate_spec({"steps": [{"alias": "x"}]})


def test_validate_spec_rejects_duplicate_alias():
    with pytest.raises(ValueError, match="duplicate alias"):
        validate_spec({"steps": [
            {"alias": "x", "skill": "a"},
            {"alias": "x", "skill": "b"},
        ]})


@pytest.mark.asyncio
async def test_runs_two_step_pipeline_with_output_piping():
    """Mock the invoker to verify outputs propagate to next step's resolved inputs."""
    captured: list[tuple[str, dict]] = []

    async def fake_invoker(skill: str, inputs: dict):
        captured.append((skill, inputs))
        if skill == "extract-tabular-data":
            return {"table_count": 1, "tables": [{"name": "Revenue", "rows": [["NA", 1200]]}]}
        if skill == "xlsx-template-apply":
            return {"file_path": "/data/.../output.xlsx", "table_count": inputs.get("expected", 1)}
        return {}

    spec = {
        "name": "PDF→Excel",
        "steps": [
            {"alias": "extract", "skill": "extract-tabular-data",
             "inputs": {"document_id": "${parameters.source_id}"}},
            {"alias": "apply", "skill": "xlsx-template-apply",
             "inputs": {
                 "template_id": "${parameters.template_id}",
                 "tables_count_passthrough": "${steps.extract.outputs.table_count}",
                 "first_row": "${steps.extract.outputs.tables.0.rows.0}",
             }},
        ],
    }

    from prisma import Prisma
    db = Prisma()
    await db.connect()
    try:
        result = await run_pipeline(
            spec=spec,
            parameters={"source_id": "pdf-1", "template_id": "tpl-1"},
            invoker=fake_invoker,
            db=db,
        )

        assert result["state"] == "SUCCESS"
        assert result["completed_count"] == 2
        # First step got the parameter
        assert captured[0][0] == "extract-tabular-data"
        assert captured[0][1]["document_id"] == "pdf-1"
        # Second step got the resolved outputs
        assert captured[1][0] == "xlsx-template-apply"
        assert captured[1][1]["tables_count_passthrough"] == 1
        assert captured[1][1]["first_row"] == ["NA", 1200]

        # Cleanup the run + steps
        await db.pipelinestep.delete_many(where={"runId": result["run_id"]})
        await db.pipelinerun.delete(where={"id": result["run_id"]})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_failed_step_halts_pipeline():
    """If step 2 raises, run is marked FAILED, later steps are not executed."""
    async def fake_invoker(skill: str, inputs: dict):
        if skill == "ok-skill":
            return {"x": 1}
        if skill == "broken-skill":
            raise RuntimeError("boom")
        return {}

    spec = {"steps": [
        {"alias": "a", "skill": "ok-skill", "inputs": {}},
        {"alias": "b", "skill": "broken-skill", "inputs": {}},
        {"alias": "c", "skill": "ok-skill", "inputs": {"x": "${steps.b.outputs.x}"}},
    ]}

    from prisma import Prisma
    db = Prisma()
    await db.connect()
    try:
        result = await run_pipeline(spec=spec, invoker=fake_invoker, db=db)
        assert result["state"] == "FAILED"
        assert result["completed_count"] == 1
        assert "boom" in result["error_message"]

        # Confirm step rows: 1=SUCCESS, 2=FAILED, 3=missing
        steps = await db.pipelinestep.find_many(where={"runId": result["run_id"]}, order={"stepIndex": "asc"})
        assert [s.state for s in steps] == ["SUCCESS", "FAILED"]

        await db.pipelinestep.delete_many(where={"runId": result["run_id"]})
        await db.pipelinerun.delete(where={"id": result["run_id"]})
    finally:
        await db.disconnect()
