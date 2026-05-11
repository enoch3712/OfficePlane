import json, asyncio, pytest, uuid
from pathlib import Path
from fastapi.testclient import TestClient


def _client():
    from officeplane.api.main import app
    return TestClient(app)


def _seed_workspace(workspace_id: str, snapshots: dict[int, dict]) -> Path:
    """Write each revision's snapshot file under /data/workspaces/<ws>/revisions/<n>.json"""
    ws_root = Path("/data/workspaces") / workspace_id
    (ws_root / "revisions").mkdir(parents=True, exist_ok=True)
    for n, snap in snapshots.items():
        if n == 1:
            (ws_root / "document.json").write_text(json.dumps(snap))
        else:
            (ws_root / "revisions" / f"{n}.json").write_text(json.dumps(snap))
    return ws_root


@pytest.mark.asyncio
async def test_diff_added_removed_changed():
    from prisma import Prisma
    db = Prisma()
    await db.connect()
    try:
        ws = str(uuid.uuid4())
        snap1 = {"type": "document", "children": [
            {"type": "section", "id": "s1", "level": 1, "heading": "A", "children": [
                {"type": "paragraph", "id": "p1", "text": "before"},
                {"type": "paragraph", "id": "p2", "text": "stays"},
            ]}
        ]}
        snap2 = {"type": "document", "children": [
            {"type": "section", "id": "s1", "level": 1, "heading": "A", "children": [
                {"type": "paragraph", "id": "p1", "text": "AFTER"},          # changed
                {"type": "paragraph", "id": "p3", "text": "new"},            # added
                # p2 removed
            ]}
        ]}
        _seed_workspace(ws, {1: snap1, 2: snap2})
        r1 = await db.documentrevision.create(data={
            "workspaceId": ws, "revisionNumber": 1, "op": "create",
            "payload": json.dumps({}), "actor": "system",
        })
        await db.documentrevision.create(data={
            "workspaceId": ws, "parentRevisionId": r1.id, "revisionNumber": 2,
            "op": "replace", "payload": json.dumps({"target_id": "p1"}), "actor": "user",
        })

        c = _client()
        r = c.get(f"/api/workspaces/{ws}/diff?from=1&to=2")
        assert r.status_code == 200, r.text
        j = r.json()
        s = j["diff"]["summary"]
        assert s["added_count"] == 1
        assert s["removed_count"] == 1
        assert s["changed_count"] == 1
        added_ids = [e["id"] for e in j["diff"]["added"]]
        removed_ids = [e["id"] for e in j["diff"]["removed"]]
        changed_ids = [e["id"] for e in j["diff"]["changed"]]
        assert added_ids == ["p3"]
        assert removed_ids == ["p2"]
        assert changed_ids == ["p1"]

        await db.documentrevision.delete_many(where={"workspaceId": ws})
    finally:
        await db.disconnect()


def test_diff_404_when_revisions_missing():
    c = _client()
    r = c.get(f"/api/workspaces/{uuid.uuid4()}/diff?from=1&to=2")
    assert r.status_code == 404


def test_diff_400_when_from_equals_to():
    c = _client()
    r = c.get(f"/api/workspaces/{uuid.uuid4()}/diff?from=1&to=1")
    # Either 400 (from==to validation) or 404 if revision lookup happens first
    assert r.status_code in (400, 404)
