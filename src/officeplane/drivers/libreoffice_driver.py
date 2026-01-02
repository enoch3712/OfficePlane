import os
from officeplane.drivers.base import OfficeDriver
from officeplane.drivers.libreoffice_pool import LibreOfficePool

POOL_SIZE = int(os.getenv("POOL_SIZE", "6"))
START_PORT = int(os.getenv("START_PORT", "2002"))
CONVERT_TIMEOUT_SEC = int(os.getenv("CONVERT_TIMEOUT_SEC", "45"))

_pool = LibreOfficePool(size=POOL_SIZE, start_port=START_PORT, convert_timeout_sec=CONVERT_TIMEOUT_SEC)

class LibreOfficeDriver(OfficeDriver):
    def warmup(self) -> None:
        _pool.start_all_async()

    def status(self) -> dict:
        return _pool.status()

    def convert_to_pdf(self, filename: str, input_bytes: bytes) -> bytes:
        return _pool.convert(input_bytes)
