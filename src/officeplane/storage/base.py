from abc import ABC, abstractmethod

class ArtifactStore(ABC):
    @abstractmethod
    def put_bytes(self, request_id: str, name: str, data: bytes, content_type: str) -> str:
        """Returns a URL path (relative) that can be fetched from /artifacts/..."""
        raise NotImplementedError
