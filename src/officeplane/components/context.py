"""
ComponentContext - Execution context for component actions.

Provides access to:
- request_id: Scope for storage and memory
- driver: OfficeDriver for document conversion
- store: ArtifactStore for persistence
- memory: ComponentMemory for state across actions
- logger: Scoped logger for the request
- extras: Arbitrary per-run state (versions, timing, etc.)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from officeplane.drivers.base import OfficeDriver
    from officeplane.storage.base import ArtifactStore
    from officeplane.components.memory import ComponentMemory


@dataclass
class ComponentContext:
    """
    Execution context for component actions.

    This is the primary interface through which actions access
    system capabilities (driver, store, memory).
    """

    request_id: str
    driver: OfficeDriver
    store: ArtifactStore
    memory: ComponentMemory
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("officeplane.component"))
    extras: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        driver: OfficeDriver,
        store: ArtifactStore,
        memory: Optional[ComponentMemory] = None,
        request_id: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
    ) -> ComponentContext:
        """
        Factory method to create a new context.

        Args:
            driver: OfficeDriver for document conversion
            store: ArtifactStore for persistence
            memory: Optional ComponentMemory (defaults to InMemoryComponentMemory)
            request_id: Optional request ID (auto-generated if not provided)
            extras: Optional extra state
        """
        from officeplane.components.memory import InMemoryComponentMemory

        if request_id is None:
            request_id = str(uuid.uuid4())

        if memory is None:
            memory = InMemoryComponentMemory()

        logger = logging.getLogger(f"officeplane.component.{request_id[:8]}")

        return cls(
            request_id=request_id,
            driver=driver,
            store=store,
            memory=memory,
            logger=logger,
            extras=extras or {},
        )

    def child(self, suffix: str) -> ComponentContext:
        """
        Create a child context with a suffixed request_id.

        Useful for sub-operations that need their own scope
        but share the same driver/store/memory.
        """
        return ComponentContext(
            request_id=f"{self.request_id}/{suffix}",
            driver=self.driver,
            store=self.store,
            memory=self.memory,
            logger=self.logger.getChild(suffix),
            extras=self.extras.copy(),
        )

    def set_extra(self, key: str, value: Any) -> None:
        """Set an extra value in the context."""
        self.extras[key] = value

    def get_extra(self, key: str, default: Any = None) -> Any:
        """Get an extra value from the context."""
        return self.extras.get(key, default)
