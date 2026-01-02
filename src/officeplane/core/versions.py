import os
import subprocess
from functools import lru_cache

@lru_cache(maxsize=1)
def libreoffice_version() -> str:
    try:
        out = subprocess.check_output(["soffice", "--version"], stderr=subprocess.STDOUT, timeout=3)
        return out.decode("utf-8", errors="ignore").strip()
    except Exception:
        return "unknown"

def officeplane_version() -> str:
    return os.getenv("OFFICEPLANE_VERSION", "0.1.0")
