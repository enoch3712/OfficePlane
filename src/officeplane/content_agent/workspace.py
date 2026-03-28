"""Workspace manager for content generation jobs."""

import logging
import os
import shutil
from pathlib import Path

log = logging.getLogger("officeplane.content_agent.workspace")


class WorkspaceManager:
    """Creates and manages per-job workspace directories."""

    def __init__(self, root: str = "/data/workspaces"):
        self.root = Path(root)

    def create(self, job_id: str) -> Path:
        """Create workspace directory for a job."""
        workspace = self.root / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        log.info("Created workspace: %s", workspace)
        return workspace

    def get(self, job_id: str) -> Path:
        """Get workspace path for a job."""
        return self.root / job_id

    def cleanup(self, job_id: str) -> None:
        """Remove workspace directory."""
        workspace = self.root / job_id
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
            log.info("Cleaned up workspace: %s", workspace)

    def list_outputs(self, job_id: str) -> list[Path]:
        """List output files in a workspace."""
        workspace = self.root / job_id
        if not workspace.exists():
            return []
        # Look for generated presentation files
        extensions = {".pptx", ".html", ".pdf", ".png", ".jpg", ".svg"}
        return [f for f in workspace.rglob("*") if f.suffix.lower() in extensions]

    def get_primary_output(self, job_id: str, output_format: str = "pptx") -> Path | None:
        """Get the primary output file for a job."""
        workspace = self.root / job_id
        if not workspace.exists():
            return None
        # Look for the main output file
        for f in workspace.rglob(f"*.{output_format}"):
            return f
        return None
