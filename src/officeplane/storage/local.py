from pathlib import Path
from officeplane.storage.base import ArtifactStore

class LocalArtifactStore(ArtifactStore):
    def __init__(self, root_dir: str = "/data"):
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, request_id: str, name: str, data: bytes, content_type: str) -> str:
        out_dir = self.root / request_id
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / name
        path.write_bytes(data)
        return f"/artifacts/{request_id}/{name}"
