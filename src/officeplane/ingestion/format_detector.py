"""Document format detection via magic bytes.

Detects document formats by examining file headers rather than relying
on file extensions.
"""

from enum import Enum
from typing import Optional


class DocumentFormat(Enum):
    """Supported document formats."""

    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    XLSX = "xlsx"
    XLS = "xls"
    PPTX = "pptx"
    PPT = "ppt"
    UNKNOWN = "unknown"


# Magic byte signatures for document formats
# PDF: %PDF
_PDF_MAGIC = b"%PDF"

# ZIP-based formats (DOCX, XLSX, PPTX) start with PK
_ZIP_MAGIC = b"PK\x03\x04"

# Old Office formats (DOC, XLS, PPT) use OLE/Compound File Binary Format
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def detect_format(data: bytes, filename: Optional[str] = None) -> DocumentFormat:
    """Detect document format from file content.

    Uses magic bytes for primary detection, with filename as fallback
    for ambiguous ZIP-based formats.

    Args:
        data: File content bytes.
        filename: Optional filename for additional context.

    Returns:
        Detected DocumentFormat.
    """
    if len(data) < 8:
        return DocumentFormat.UNKNOWN

    # Check PDF
    if data[:4] == _PDF_MAGIC:
        return DocumentFormat.PDF

    # Check ZIP-based formats (Office Open XML)
    if data[:4] == _ZIP_MAGIC:
        return _detect_ooxml_format(data, filename)

    # Check OLE-based formats (old Office)
    if data[:8] == _OLE_MAGIC:
        return _detect_ole_format(data, filename)

    return DocumentFormat.UNKNOWN


def _detect_ooxml_format(data: bytes, filename: Optional[str] = None) -> DocumentFormat:
    """Detect specific OOXML format (docx, xlsx, pptx).

    Examines ZIP contents to identify the specific format.

    Args:
        data: File content bytes.
        filename: Optional filename for fallback.

    Returns:
        Detected DocumentFormat.
    """
    import zipfile
    from io import BytesIO

    try:
        with zipfile.ZipFile(BytesIO(data), "r") as zf:
            names = set(zf.namelist())

            # Check directory structure first — more reliable than content-type strings
            # because some files embed spreadsheets (xlsx Default extensions) inside
            # a presentation, which would cause a false XLSX match on content types.
            names_joined = " ".join(names)
            if "word/" in names_joined:
                return DocumentFormat.DOCX
            if "ppt/" in names_joined:
                return DocumentFormat.PPTX
            if "xl/" in names_joined:
                return DocumentFormat.XLSX

            # Check for content type markers as fallback
            if "[Content_Types].xml" in names:
                content_types = zf.read("[Content_Types].xml").decode("utf-8", errors="ignore")

                if "wordprocessingml" in content_types:
                    return DocumentFormat.DOCX
                if "presentationml" in content_types:
                    return DocumentFormat.PPTX
                if "spreadsheetml" in content_types:
                    return DocumentFormat.XLSX

    except zipfile.BadZipFile:
        pass

    # Fallback to filename extension
    if filename:
        return _format_from_extension(filename)

    return DocumentFormat.UNKNOWN


def _detect_ole_format(data: bytes, filename: Optional[str] = None) -> DocumentFormat:
    """Detect specific OLE format (doc, xls, ppt).

    For OLE files, we primarily rely on filename extension as the
    internal structure is complex.

    Args:
        data: File content bytes.
        filename: Optional filename for detection.

    Returns:
        Detected DocumentFormat.
    """
    if filename:
        return _format_from_extension(filename)

    # Without filename, we can't easily distinguish DOC/XLS/PPT
    # Default to DOC as most common
    return DocumentFormat.DOC


def _format_from_extension(filename: str) -> DocumentFormat:
    """Detect format from filename extension.

    Args:
        filename: Filename with extension.

    Returns:
        Detected DocumentFormat.
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    extension_map = {
        "pdf": DocumentFormat.PDF,
        "docx": DocumentFormat.DOCX,
        "doc": DocumentFormat.DOC,
        "xlsx": DocumentFormat.XLSX,
        "xls": DocumentFormat.XLS,
        "pptx": DocumentFormat.PPTX,
        "ppt": DocumentFormat.PPT,
    }

    return extension_map.get(ext, DocumentFormat.UNKNOWN)


def is_pdf(data: bytes) -> bool:
    """Check if data is a PDF file.

    Args:
        data: File content bytes.

    Returns:
        True if the data is a PDF.
    """
    return detect_format(data) == DocumentFormat.PDF


def is_office_document(data: bytes, filename: Optional[str] = None) -> bool:
    """Check if data is an Office document (Word, Excel, PowerPoint).

    Args:
        data: File content bytes.
        filename: Optional filename for additional context.

    Returns:
        True if the data is an Office document.
    """
    fmt = detect_format(data, filename)
    return fmt in (
        DocumentFormat.DOCX,
        DocumentFormat.DOC,
        DocumentFormat.XLSX,
        DocumentFormat.XLS,
        DocumentFormat.PPTX,
        DocumentFormat.PPT,
    )


def needs_conversion(data: bytes, filename: Optional[str] = None) -> bool:
    """Check if document needs conversion to PDF for processing.

    Args:
        data: File content bytes.
        filename: Optional filename for additional context.

    Returns:
        True if the document needs conversion to PDF.
    """
    fmt = detect_format(data, filename)
    return fmt != DocumentFormat.PDF and fmt != DocumentFormat.UNKNOWN
