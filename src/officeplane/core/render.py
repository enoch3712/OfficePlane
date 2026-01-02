import base64
from dataclasses import dataclass
from typing import List, Literal, Dict, Any

import fitz  # PyMuPDF

from officeplane.core.checksums import sha256_bytes

ImageFormat = Literal["png", "jpeg"]

@dataclass
class PageImage:
    page: int
    dpi: int
    width: int
    height: int
    sha256: str
    data: bytes  # raw image bytes

def pdf_to_images(pdf_bytes: bytes, dpi: int, fmt: ImageFormat = "png") -> List[PageImage]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = len(doc)

    results: List[PageImage] = []
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    for i in range(pages):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes(fmt)
        results.append(
            PageImage(
                page=i + 1,
                dpi=dpi,
                width=pix.width,
                height=pix.height,
                sha256=sha256_bytes(img_bytes),
                data=img_bytes,
            )
        )

    doc.close()
    return results

def page_images_to_payload(images: List[PageImage], inline: bool) -> List[Dict[str, Any]]:
    payload = []
    for img in images:
        item: Dict[str, Any] = {
            "page": img.page,
            "dpi": img.dpi,
            "width": img.width,
            "height": img.height,
            "sha256": img.sha256,
        }
        if inline:
            item["base64"] = base64.b64encode(img.data).decode("utf-8")
        payload.append(item)
    return payload
