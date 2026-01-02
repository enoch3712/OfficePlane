from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class PdfOut(BaseModel):
    sha256: str
    base64: Optional[str] = None
    url: Optional[str] = None

class PageOut(BaseModel):
    page: int
    dpi: int
    width: int
    height: int
    sha256: str
    base64: Optional[str] = None
    url: Optional[str] = None

class ManifestOut(BaseModel):
    pages_count: int
    timings_ms: Dict[str, int]
    versions: Dict[str, str]
    extra: Dict[str, Any] = {}

class RenderResponse(BaseModel):
    request_id: str
    input: Dict[str, Any]
    pdf: Optional[PdfOut] = None
    pages: List[PageOut]
    manifest: ManifestOut
