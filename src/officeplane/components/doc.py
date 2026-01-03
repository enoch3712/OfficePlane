"""
DocComponent - Document operations component.

Provides actions for:
- convert_to_pdf: Convert Office documents to PDF
- render_pdf_to_images: Render PDF pages as images
- render_document: Full pipeline (convert + render)
- store_bytes: Store artifacts
- remember/recall: Memory utilities
"""

from __future__ import annotations

import base64
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from officeplane.components.action import ComponentAction
from officeplane.components.base import OfficeComponent
from officeplane.components.context import ComponentContext
from officeplane.core.checksums import sha256_bytes
from officeplane.core.render import pdf_to_images


# ============================================================
# Input/Output Models
# ============================================================


class ConvertToPdfInput(BaseModel):
    """Input for convert_to_pdf action."""

    filename: str = Field(..., description="Original filename with extension (e.g., 'doc.pptx')")
    data_base64: str = Field(..., description="Base64-encoded document bytes")


class ConvertToPdfOutput(BaseModel):
    """Output for convert_to_pdf action."""

    pdf_sha256: str = Field(..., description="SHA256 hash of the PDF")
    pdf_base64: str = Field(..., description="Base64-encoded PDF bytes")
    size_bytes: int = Field(..., description="Size of the PDF in bytes")


class RenderPdfInput(BaseModel):
    """Input for render_pdf_to_images action."""

    pdf_base64: str = Field(..., description="Base64-encoded PDF bytes")
    dpi: int = Field(120, ge=72, le=300, description="DPI for rendering (72-300)")
    image_format: Literal["png", "jpeg"] = Field("png", description="Output image format")


class PageImageOutput(BaseModel):
    """Output for a single rendered page."""

    page: int
    dpi: int
    width: int
    height: int
    sha256: str
    base64: str


class RenderPdfOutput(BaseModel):
    """Output for render_pdf_to_images action."""

    pages: List[PageImageOutput]
    pages_count: int


class RenderDocumentInput(BaseModel):
    """Input for render_document action (full pipeline)."""

    filename: str = Field(..., description="Original filename with extension")
    data_base64: str = Field(..., description="Base64-encoded document bytes")
    dpi: int = Field(120, ge=72, le=300, description="DPI for rendering")
    image_format: Literal["png", "jpeg"] = Field("png", description="Output image format")
    output: Literal["pdf", "images", "both"] = Field("both", description="What to include in output")
    store_artifacts: bool = Field(False, description="Whether to store artifacts to disk")


class RenderDocumentOutput(BaseModel):
    """Output for render_document action."""

    request_id: str
    input_filename: str
    input_size_bytes: int
    pdf: Optional[Dict[str, Any]] = None
    pages: List[Dict[str, Any]] = []
    pages_count: int
    timings_ms: Dict[str, int]


class StoreInput(BaseModel):
    """Input for store_bytes action."""

    name: str = Field(..., description="Artifact name")
    data_base64: str = Field(..., description="Base64-encoded data")
    content_type: str = Field("application/octet-stream", description="MIME type")


class StoreOutput(BaseModel):
    """Output for store_bytes action."""

    url: str
    name: str
    size_bytes: int
    sha256: str


class MemoryInput(BaseModel):
    """Input for remember/recall actions."""

    key: str = Field(..., description="Memory key")
    value: Optional[Any] = Field(None, description="Value to store (for remember)")


class MemoryOutput(BaseModel):
    """Output for remember/recall actions."""

    key: str
    value: Optional[Any] = None
    found: bool = True


# ============================================================
# DocComponent
# ============================================================


class DocComponent(OfficeComponent):
    """
    Document operations component.

    Provides high-level actions for document conversion and rendering,
    backed by the OfficeDriver and ArtifactStore.
    """

    def __init__(self) -> None:
        super().__init__(
            name="doc",
            purpose="Convert and render Office documents (PPTX, DOCX, XLSX) to PDF and images",
            description=(
                "A component for processing Office documents. "
                "Can convert documents to PDF, render PDF pages as images, "
                "and store artifacts for later retrieval."
            ),
        )

    def _build_actions(self) -> None:
        """Build and register all actions."""
        self._register_action(self._make_convert_to_pdf_action())
        self._register_action(self._make_render_pdf_action())
        self._register_action(self._make_render_document_action())
        self._register_action(self._make_store_bytes_action())
        self._register_action(self._make_remember_action())
        self._register_action(self._make_recall_action())

    def _make_convert_to_pdf_action(self) -> ComponentAction:
        """Create the convert_to_pdf action."""

        def handler(ctx: ComponentContext, input: ConvertToPdfInput) -> ConvertToPdfOutput:
            input_bytes = base64.b64decode(input.data_base64)
            pdf_bytes = ctx.driver.convert_to_pdf(input.filename, input_bytes)

            return ConvertToPdfOutput(
                pdf_sha256=sha256_bytes(pdf_bytes),
                pdf_base64=base64.b64encode(pdf_bytes).decode("utf-8"),
                size_bytes=len(pdf_bytes),
            )

        return ComponentAction(
            name="convert_to_pdf",
            description="Convert an Office document (PPTX, DOCX, XLSX) to PDF format",
            input_model=ConvertToPdfInput,
            output_model=ConvertToPdfOutput,
            handler=handler,
        )

    def _make_render_pdf_action(self) -> ComponentAction:
        """Create the render_pdf_to_images action."""

        def handler(ctx: ComponentContext, input: RenderPdfInput) -> RenderPdfOutput:
            pdf_bytes = base64.b64decode(input.pdf_base64)
            images = pdf_to_images(pdf_bytes, dpi=input.dpi, fmt=input.image_format)

            pages = [
                PageImageOutput(
                    page=img.page,
                    dpi=img.dpi,
                    width=img.width,
                    height=img.height,
                    sha256=img.sha256,
                    base64=base64.b64encode(img.data).decode("utf-8"),
                )
                for img in images
            ]

            return RenderPdfOutput(
                pages=pages,
                pages_count=len(pages),
            )

        return ComponentAction(
            name="render_pdf_to_images",
            description="Render PDF pages as images (PNG or JPEG)",
            input_model=RenderPdfInput,
            output_model=RenderPdfOutput,
            handler=handler,
        )

    def _make_render_document_action(self) -> ComponentAction:
        """Create the render_document action (full pipeline)."""

        def handler(ctx: ComponentContext, input: RenderDocumentInput) -> RenderDocumentOutput:
            import time

            t_total = time.time()
            input_bytes = base64.b64decode(input.data_base64)

            # Convert to PDF
            t0 = time.time()
            pdf_bytes = ctx.driver.convert_to_pdf(input.filename, input_bytes)
            convert_ms = int((time.time() - t0) * 1000)

            pdf_sha = sha256_bytes(pdf_bytes)

            # Render to images
            t1 = time.time()
            images = pdf_to_images(pdf_bytes, dpi=input.dpi, fmt=input.image_format)
            render_ms = int((time.time() - t1) * 1000)

            # Build output
            pdf_out = None
            if input.output in ("pdf", "both"):
                if input.store_artifacts:
                    url = ctx.store.put_bytes(
                        ctx.request_id, "out.pdf", pdf_bytes, "application/pdf"
                    )
                    pdf_out = {"sha256": pdf_sha, "url": url, "size_bytes": len(pdf_bytes)}
                else:
                    pdf_out = {
                        "sha256": pdf_sha,
                        "base64": base64.b64encode(pdf_bytes).decode("utf-8"),
                        "size_bytes": len(pdf_bytes),
                    }

            pages_out = []
            if input.output in ("images", "both"):
                for img in images:
                    page_data: Dict[str, Any] = {
                        "page": img.page,
                        "dpi": img.dpi,
                        "width": img.width,
                        "height": img.height,
                        "sha256": img.sha256,
                    }
                    if input.store_artifacts:
                        name = f"page_{img.page}.{input.image_format}"
                        url = ctx.store.put_bytes(
                            ctx.request_id, name, img.data, f"image/{input.image_format}"
                        )
                        page_data["url"] = url
                    else:
                        page_data["base64"] = base64.b64encode(img.data).decode("utf-8")
                    pages_out.append(page_data)

            total_ms = int((time.time() - t_total) * 1000)

            return RenderDocumentOutput(
                request_id=ctx.request_id,
                input_filename=input.filename,
                input_size_bytes=len(input_bytes),
                pdf=pdf_out,
                pages=pages_out,
                pages_count=len(images),
                timings_ms={"convert": convert_ms, "render": render_ms, "total": total_ms},
            )

        return ComponentAction(
            name="render_document",
            description=(
                "Full document rendering pipeline: convert Office document to PDF "
                "and render pages as images in one operation"
            ),
            input_model=RenderDocumentInput,
            output_model=RenderDocumentOutput,
            handler=handler,
        )

    def _make_store_bytes_action(self) -> ComponentAction:
        """Create the store_bytes action."""

        def handler(ctx: ComponentContext, input: StoreInput) -> StoreOutput:
            data = base64.b64decode(input.data_base64)
            url = ctx.store.put_bytes(ctx.request_id, input.name, data, input.content_type)

            return StoreOutput(
                url=url,
                name=input.name,
                size_bytes=len(data),
                sha256=sha256_bytes(data),
            )

        return ComponentAction(
            name="store_bytes",
            description="Store arbitrary bytes as an artifact for later retrieval",
            input_model=StoreInput,
            output_model=StoreOutput,
            handler=handler,
        )

    def _make_remember_action(self) -> ComponentAction:
        """Create the remember action."""

        def handler(ctx: ComponentContext, input: MemoryInput) -> MemoryOutput:
            ctx.memory.remember(input.key, input.value)
            return MemoryOutput(key=input.key, value=input.value, found=True)

        return ComponentAction(
            name="remember",
            description="Store a value in component memory for later recall",
            input_model=MemoryInput,
            output_model=MemoryOutput,
            handler=handler,
        )

    def _make_recall_action(self) -> ComponentAction:
        """Create the recall action."""

        def handler(ctx: ComponentContext, input: MemoryInput) -> MemoryOutput:
            value = ctx.memory.recall(input.key)
            found = ctx.memory.has(input.key)
            return MemoryOutput(key=input.key, value=value, found=found)

        return ComponentAction(
            name="recall",
            description="Retrieve a value from component memory",
            input_model=MemoryInput,
            output_model=MemoryOutput,
            handler=handler,
        )
