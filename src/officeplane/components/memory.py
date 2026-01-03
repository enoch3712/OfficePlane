"""
ComponentMemory - Memory interface for components.

Provides short-term and long-term memory capabilities:
- InMemoryComponentMemory: Simple dict-based memory (per-session)
- ArtifactBackedMemory: Persistent memory using ArtifactStore
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from officeplane.storage.base import ArtifactStore


class ComponentMemory(ABC):
    """
    Abstract interface for component memory.

    Memory allows components to store and retrieve state
    across action invocations within a session.
    """

    @abstractmethod
    def remember(self, key: str, value: Any) -> None:
        """Store a value in memory."""
        raise NotImplementedError

    @abstractmethod
    def recall(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from memory."""
        raise NotImplementedError

    @abstractmethod
    def forget(self, key: str) -> None:
        """Remove a value from memory."""
        raise NotImplementedError

    @abstractmethod
    def list_keys(self) -> List[str]:
        """List all keys in memory."""
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """Clear all memory."""
        raise NotImplementedError

    def has(self, key: str) -> bool:
        """Check if a key exists in memory."""
        return key in self.list_keys()

    def remember_many(self, items: Dict[str, Any]) -> None:
        """Store multiple values in memory."""
        for key, value in items.items():
            self.remember(key, value)

    def recall_many(self, keys: List[str]) -> Dict[str, Any]:
        """Retrieve multiple values from memory."""
        return {key: self.recall(key) for key in keys if self.has(key)}


class InMemoryComponentMemory(ComponentMemory):
    """
    Simple in-memory storage using a dictionary.

    Suitable for single-session use. Data is lost when the
    memory object is garbage collected.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def remember(self, key: str, value: Any) -> None:
        self._store[key] = value

    def recall(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def forget(self, key: str) -> None:
        self._store.pop(key, None)

    def list_keys(self) -> List[str]:
        return list(self._store.keys())

    def clear(self) -> None:
        self._store.clear()

    def __repr__(self) -> str:
        return f"InMemoryComponentMemory(keys={self.list_keys()})"


class ArtifactBackedMemory(ComponentMemory):
    """
    Persistent memory backed by an ArtifactStore.

    Stores memory as JSON in the artifact store, allowing
    persistence across sessions/restarts.
    """

    def __init__(
        self,
        store: ArtifactStore,
        request_id: str,
        memory_file: str = "_memory.json",
    ) -> None:
        self._store = store
        self._request_id = request_id
        self._memory_file = memory_file
        self._cache: Dict[str, Any] = {}
        self._dirty = False

    def _load(self) -> None:
        """Load memory from artifact store (lazy)."""
        # Note: This requires ArtifactStore to support reading
        # For now, we operate on the cache only
        pass

    def _save(self) -> None:
        """Persist memory to artifact store."""
        if self._dirty:
            data = json.dumps(self._cache, indent=2).encode("utf-8")
            self._store.put_bytes(
                self._request_id,
                self._memory_file,
                data,
                "application/json",
            )
            self._dirty = False

    def remember(self, key: str, value: Any) -> None:
        self._cache[key] = value
        self._dirty = True
        self._save()

    def recall(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def forget(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]
            self._dirty = True
            self._save()

    def list_keys(self) -> List[str]:
        return list(self._cache.keys())

    def clear(self) -> None:
        self._cache.clear()
        self._dirty = True
        self._save()

    def __repr__(self) -> str:
        return f"ArtifactBackedMemory(request_id={self._request_id}, keys={self.list_keys()})"
