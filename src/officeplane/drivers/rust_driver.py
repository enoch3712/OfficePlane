"""
High-performance Rust native driver for OfficePlane.

This driver uses the native officeplane_core module built with Rust + PyO3
for maximum performance. It eliminates Python overhead for:
- LibreOffice connection pooling
- PDF rendering
- Image encoding

Falls back to the Python LibreOffice driver if the native module is not available.
"""

import logging
import os
from typing import Any, Dict, List, Optional, cast

from officeplane.drivers.base import OfficeDriver

log = logging.getLogger("officeplane.rust_driver")

# Try to import the native module
try:
    import officeplane_core

    NATIVE_AVAILABLE = True
    log.info(f"Native Rust driver loaded (version {officeplane_core.version()})")
except ImportError:
    NATIVE_AVAILABLE = False
    log.warning("Native Rust driver not available, will use Python fallback")
    officeplane_core = None


POOL_SIZE = int(os.getenv("POOL_SIZE", "6"))
START_PORT = int(os.getenv("START_PORT", "2002"))
CONVERT_TIMEOUT_SEC = int(os.getenv("CONVERT_TIMEOUT_SEC", "45"))


class RustDriver(OfficeDriver):
    """
    High-performance driver using Rust native extensions.

    This driver provides significant performance improvements over the pure Python
    driver by:
    1. Managing LibreOffice connections in native code (no subprocess per request)
    2. Parallel PDF rendering using native threads (bypasses GIL)
    3. Zero-copy buffer management where possible
    """

    def __init__(self):
        self._initialized = False

        if not NATIVE_AVAILABLE:
            raise RuntimeError(
                "Native Rust module not available. "
                "Build with: cd native/officeplane-core && maturin develop --release"
            )

    def warmup(self) -> None:
        """Initialize the LibreOffice pool."""
        if not self._initialized:
            officeplane_core.init_pool(
                pool_size=POOL_SIZE,
                start_port=START_PORT,
                timeout_secs=CONVERT_TIMEOUT_SEC,
            )
            self._initialized = True
            log.info(f"Rust driver initialized with pool_size={POOL_SIZE}")

    def status(self) -> Dict[str, Any]:
        """Get pool status."""
        if not self._initialized:
            return {"total": 0, "ready": 0, "instances": []}
        return cast(Dict[str, Any], officeplane_core.pool_status())

    def convert_to_pdf(self, filename: str, input_bytes: bytes) -> bytes:
        """Convert Office document to PDF using native pool."""
        if not self._initialized:
            self.warmup()

        timeout_ms = CONVERT_TIMEOUT_SEC * 1000
        return cast(bytes, officeplane_core.convert_to_pdf(input_bytes, timeout_ms=timeout_ms))

    def render_to_images(
        self,
        pdf_bytes: bytes,
        dpi: int = 120,
        image_format: str = "png",
    ) -> List[Dict[str, Any]]:
        """
        Render PDF to images using native parallel rendering.

        Returns list of dicts with keys:
        - page: int
        - dpi: int
        - width: int
        - height: int
        - sha256: str
        - data: bytes
        """
        return cast(
            List[Dict[str, Any]],
            officeplane_core.render_pdf(
                pdf_bytes,
                dpi=dpi,
                format=image_format,
                include_data=True,
            ),
        )

    def render_document(
        self,
        input_bytes: bytes,
        dpi: int = 120,
        image_format: str = "png",
        include_pdf: bool = True,
        include_images: bool = True,
    ) -> Dict[str, Any]:
        """
        Full pipeline: convert + render in one native call.

        This is the most efficient method as it minimizes Python/Rust boundary crossings.

        Returns dict with:
        - pdf: {sha256, size_bytes, data?}
        - pages: [{page, dpi, width, height, sha256, data?}, ...]
        - timings: {convert_ms, render_ms, total_ms}
        """
        if not self._initialized:
            self.warmup()

        timeout_ms = CONVERT_TIMEOUT_SEC * 1000
        return cast(
            Dict[str, Any],
            officeplane_core.render_document(
                input_bytes,
                dpi=dpi,
                format=image_format,
                include_pdf=include_pdf,
                include_images=include_images,
                timeout_ms=timeout_ms,
            ),
        )


def is_available() -> bool:
    """Check if the native Rust driver is available."""
    return NATIVE_AVAILABLE


def get_version() -> Optional[str]:
    """Get the native module version."""
    if NATIVE_AVAILABLE:
        return cast(str, officeplane_core.version())
    return None
