"""
Persistent orchestration settings for document planning.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Literal, Optional

from pydantic import BaseModel, Field


ProviderPreference = Literal["auto", "gemini", "openai", "mock"]
PlanningStrategy = Literal["workchestrator", "classic"]


class ModelRoleSettings(BaseModel):
    provider: ProviderPreference = "auto"
    model: Optional[str] = None


class TakeoverPolicySettings(BaseModel):
    worker_confidence_threshold: float = Field(0.68, ge=0.0, le=1.0)
    max_worker_retries: int = Field(1, ge=0, le=3)
    complexity_takeover_threshold: float = Field(0.72, ge=0.0, le=1.0)
    max_validation_issues: int = Field(1, ge=0, le=10)


class OrchestrationSettings(BaseModel):
    enabled: bool = True
    strategy: PlanningStrategy = "workchestrator"
    allow_orchestrator_takeover: bool = True
    worker: ModelRoleSettings = Field(default_factory=ModelRoleSettings)
    orchestrator: ModelRoleSettings = Field(default_factory=ModelRoleSettings)
    takeover: TakeoverPolicySettings = Field(default_factory=TakeoverPolicySettings)


class OrchestrationSettingsStore:
    """File-backed settings store used by the UI and planning endpoints."""

    def __init__(self, path: Optional[str] = None) -> None:
        configured_path = path or os.getenv("OFFICEPLANE_SETTINGS_PATH")
        self.path = Path(configured_path or ".officeplane/orchestration_settings.json")
        self._lock = Lock()

    def load(self) -> OrchestrationSettings:
        with self._lock:
            if not self.path.exists():
                settings = OrchestrationSettings()
                self._write_locked(settings)
                return settings

            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                return OrchestrationSettings.model_validate(payload)
            except Exception:
                settings = OrchestrationSettings()
                self._write_locked(settings)
                return settings

    def save(self, settings: OrchestrationSettings) -> OrchestrationSettings:
        with self._lock:
            self._write_locked(settings)
            return settings

    def _write_locked(self, settings: OrchestrationSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(settings.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )


settings_store = OrchestrationSettingsStore()
