"""
Agent Teams API routes.

Start a team, stream progress, get results.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from officeplane.agent_team.team import AgentTeam
from officeplane.content_agent.streaming import sse_manager

log = logging.getLogger("officeplane.api.team_routes")

router = APIRouter(prefix="/api/teams", tags=["teams"])

# Track running teams
_teams: dict[str, dict] = {}


class TeammateConfig(BaseModel):
    role: str
    prompt: Optional[str] = None


class CreateTeamRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    teammates: List[TeammateConfig] = Field(..., min_length=1, max_length=10)
    model: Optional[str] = None
    document_id: Optional[str] = None


class CreateTeamResponse(BaseModel):
    team_id: str
    status: str = "running"
    stream_url: str
    teammates: List[str]


@router.post("", status_code=202, response_model=CreateTeamResponse)
async def create_team(request: CreateTeamRequest):
    """Start an agent team."""
    teammate_configs = [
        {"role": tc.role, "prompt": tc.prompt or f"You are a {tc.role}."}
        for tc in request.teammates
    ]

    team = AgentTeam.create(
        prompt=request.prompt,
        teammates=teammate_configs,
        model=request.model or "gpt-4o",
        document_id=request.document_id,
    )

    # Create SSE stream for this team
    sse_manager.create_stream(team.team_id)

    # Wire SSE events
    async def on_event(agent_id: str, event_type: str, data: dict):
        await sse_manager.push_event(team.team_id, event_type, {
            "agent_id": agent_id, **data
        })

    team.on_event(on_event)

    # Run team in background
    async def run_team():
        try:
            result = await team.run()
            _teams[team.team_id]["result"] = result
            _teams[team.team_id]["status"] = result.get("status", "completed")
        except Exception as e:
            _teams[team.team_id]["status"] = "failed"
            _teams[team.team_id]["error"] = str(e)

    _teams[team.team_id] = {
        "status": "running",
        "team": team,
        "prompt": request.prompt,
        "result": None,
    }

    asyncio.create_task(run_team())

    return CreateTeamResponse(
        team_id=team.team_id,
        status="running",
        stream_url=f"/api/teams/{team.team_id}/stream",
        teammates=[tc.role for tc in request.teammates],
    )


@router.get("/{team_id}/stream")
async def stream_team_events(team_id: str):
    """SSE stream for team events."""
    if team_id not in _teams:
        raise HTTPException(status_code=404, detail="Team not found")

    if team_id not in sse_manager._streams:
        sse_manager.create_stream(team_id)

    return StreamingResponse(
        sse_manager.event_generator(team_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{team_id}")
async def get_team_status(team_id: str):
    """Get team status and results."""
    entry = _teams.get(team_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Team not found")

    response: Dict[str, Any] = {
        "team_id": team_id,
        "status": entry["status"],
        "prompt": entry["prompt"],
    }
    if entry.get("result"):
        response["result"] = entry["result"]
    if entry.get("error"):
        response["error"] = entry["error"]
    return response


@router.delete("/{team_id}")
async def cancel_team(team_id: str):
    """Cancel a running team."""
    entry = _teams.get(team_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Team not found")

    team: AgentTeam = entry["team"]
    await team.cleanup()
    entry["status"] = "cancelled"
    sse_manager.remove_stream(team_id)

    return {"team_id": team_id, "status": "cancelled"}
