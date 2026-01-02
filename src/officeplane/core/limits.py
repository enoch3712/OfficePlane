import os

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
MAX_DPI = int(os.getenv("MAX_DPI", "300"))
DEFAULT_DPI = int(os.getenv("DEFAULT_DPI", "120"))

ALLOWED_EXTS = {".pptx", ".ppt", ".docx", ".xlsx"}

def validate_upload(filename: str, size_bytes: int) -> None:
    if not filename:
        raise ValueError("Missing filename")
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported extension {ext}. Allowed: {sorted(ALLOWED_EXTS)}")

    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValueError(f"File too large: {size_bytes} bytes > {max_bytes} bytes")

def validate_dpi(dpi: int) -> int:
    if dpi <= 0:
        raise ValueError("dpi must be > 0")
    if dpi > MAX_DPI:
        raise ValueError(f"dpi too high: {dpi} > {MAX_DPI}")
    return dpi
