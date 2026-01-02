from typing import cast

import fitz  # PyMuPDF

from officeplane.drivers.base import OfficeDriver


class MockDriver(OfficeDriver):
    """Converts any input into a deterministic 2-page PDF for self-contained tests."""

    def convert_to_pdf(self, filename: str, input_bytes: bytes) -> bytes:
        doc = fitz.open()
        for i in range(2):
            page = doc.new_page()
            page.insert_text((72, 72), f"OfficePlane Mock PDF page {i+1}\nfile={filename}")
        pdf_bytes = cast(bytes, doc.tobytes())
        doc.close()
        return pdf_bytes
