"""Pydantic models for content generation API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    PPTX = "pptx"
    HTML = "html"
    BOTH = "both"


class DriverType(str, Enum):
    DEEPAGENTS_SDK = "deepagents_sdk"
    DEEPAGENTS_CLI = "deepagents_cli"


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerateRequest(BaseModel):
    """Request to start content generation."""

    prompt: str = Field(..., min_length=1, max_length=10000)
    output_format: OutputFormat = OutputFormat.PPTX
    model: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)
    driver: DriverType = DriverType.DEEPAGENTS_SDK


class GenerateResponse(BaseModel):
    """Response when a generation job is created."""

    job_id: str
    status: JobState = JobState.QUEUED
    stream_url: str


class JobStatus(BaseModel):
    """Current status of a generation job."""

    job_id: str
    status: JobState
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    document_id: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None


class SSEEvent(BaseModel):
    """A server-sent event."""

    event: str
    data: Dict[str, Any]
