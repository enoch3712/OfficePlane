"""
Result types for structured error handling.

Instead of returning strings like "Paragraph added successfully",
we return Result[T] that is either Ok(value) or Err(error).

This allows:
- Type-safe success values
- Rich error information with codes, context, and suggestions
- Chaining operations with map/and_then
- Pattern matching on success/failure

Example:
    result = editor.add_paragraph("Hello")

    # Pattern matching
    match result:
        case Ok(paragraph):
            print(f"Added paragraph at position {paragraph.position}")
        case Err(error):
            print(f"Failed: {error.code.name} - {error.message}")
            if error.suggestion:
                print(f"Try: {error.suggestion}")

    # Chaining
    result = (editor
        .add_paragraph("Hello")
        .and_then(lambda p: editor.style_paragraph(p, "Heading1"))
        .and_then(lambda p: editor.add_paragraph_after(p, "World")))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
    overload,
)


# Type variables for Result
T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")


class ErrorCode(Enum):
    """Structured error codes for document operations."""

    # File errors (1xx)
    FILE_NOT_FOUND = 100
    FILE_LOCKED = 101
    FILE_CORRUPTED = 102
    FILE_READ_ONLY = 103
    FILE_PERMISSION_DENIED = 104
    FILE_TOO_LARGE = 105
    FILE_INVALID_FORMAT = 106

    # Document structure errors (2xx)
    INVALID_DOCUMENT = 200
    DOCUMENT_EMPTY = 201
    SECTION_NOT_FOUND = 202
    PARAGRAPH_NOT_FOUND = 203
    TABLE_NOT_FOUND = 204
    HEADING_NOT_FOUND = 205
    ANCHOR_NOT_FOUND = 206
    BOOKMARK_NOT_FOUND = 207

    # Content errors (3xx)
    INVALID_CONTENT = 300
    CONTENT_TOO_LONG = 301
    INVALID_STYLE = 302
    STYLE_NOT_FOUND = 303
    INVALID_FORMAT = 304
    ENCODING_ERROR = 305

    # Operation errors (4xx)
    OPERATION_FAILED = 400
    OPERATION_CANCELLED = 401
    OPERATION_TIMEOUT = 402
    INVALID_POSITION = 403
    INVALID_RANGE = 404
    INDEX_OUT_OF_BOUNDS = 405

    # Transaction errors (5xx)
    TRANSACTION_FAILED = 500
    ROLLBACK_FAILED = 501
    COMMIT_FAILED = 502
    NO_ACTIVE_TRANSACTION = 503
    NESTED_TRANSACTION_ERROR = 504

    # Resource errors (6xx)
    RESOURCE_EXHAUSTED = 600
    MEMORY_ERROR = 601
    DISK_FULL = 602

    # Validation errors (7xx)
    VALIDATION_FAILED = 700
    REQUIRED_FIELD_MISSING = 701
    INVALID_ARGUMENT = 702
    TYPE_MISMATCH = 703

    # Unknown
    UNKNOWN = 999


@dataclass
class DocError:
    """
    Rich error information for document operations.

    Attributes:
        code: Structured error code for programmatic handling
        message: Human-readable error message
        details: Additional context about the error
        source_file: File path where error occurred (if applicable)
        source_location: Location in document (paragraph index, table position, etc.)
        suggestion: Helpful suggestion for resolving the error
        cause: Original exception that caused this error (if any)
    """

    code: ErrorCode
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    source_file: Optional[str] = None
    source_location: Optional[str] = None
    suggestion: Optional[str] = None
    cause: Optional[Exception] = None

    def __str__(self) -> str:
        parts = [f"[{self.code.name}] {self.message}"]
        if self.source_file:
            parts.append(f"  File: {self.source_file}")
        if self.source_location:
            parts.append(f"  Location: {self.source_location}")
        if self.details:
            parts.append(f"  Details: {self.details}")
        if self.suggestion:
            parts.append(f"  Suggestion: {self.suggestion}")
        if self.cause:
            parts.append(f"  Caused by: {type(self.cause).__name__}: {self.cause}")
        return "\n".join(parts)

    def with_context(self, **kwargs: Any) -> DocError:
        """Return a new error with additional context in details."""
        new_details = {**self.details, **kwargs}
        return DocError(
            code=self.code,
            message=self.message,
            details=new_details,
            source_file=self.source_file,
            source_location=self.source_location,
            suggestion=self.suggestion,
            cause=self.cause,
        )

    def with_suggestion(self, suggestion: str) -> DocError:
        """Return a new error with a suggestion."""
        return DocError(
            code=self.code,
            message=self.message,
            details=self.details,
            source_file=self.source_file,
            source_location=self.source_location,
            suggestion=suggestion,
            cause=self.cause,
        )

    @classmethod
    def file_not_found(cls, path: str) -> DocError:
        """Create a file not found error."""
        return cls(
            code=ErrorCode.FILE_NOT_FOUND,
            message=f"File not found: {path}",
            source_file=path,
            suggestion="Check that the file path is correct and the file exists.",
        )

    @classmethod
    def file_locked(cls, path: str, holder: Optional[str] = None) -> DocError:
        """Create a file locked error."""
        msg = f"File is locked: {path}"
        if holder:
            msg += f" (held by {holder})"
        return cls(
            code=ErrorCode.FILE_LOCKED,
            message=msg,
            source_file=path,
            details={"holder": holder} if holder else {},
            suggestion="Close the file in other applications or wait for the lock to be released.",
        )

    @classmethod
    def invalid_position(cls, position: Any, valid_range: str) -> DocError:
        """Create an invalid position error."""
        return cls(
            code=ErrorCode.INVALID_POSITION,
            message=f"Invalid position: {position}",
            details={"position": position, "valid_range": valid_range},
            suggestion=f"Use a position within the valid range: {valid_range}",
        )

    @classmethod
    def element_not_found(
        cls,
        element_type: str,
        identifier: Any,
        search_scope: Optional[str] = None,
    ) -> DocError:
        """Create an element not found error."""
        code_map = {
            "section": ErrorCode.SECTION_NOT_FOUND,
            "paragraph": ErrorCode.PARAGRAPH_NOT_FOUND,
            "table": ErrorCode.TABLE_NOT_FOUND,
            "heading": ErrorCode.HEADING_NOT_FOUND,
            "anchor": ErrorCode.ANCHOR_NOT_FOUND,
            "bookmark": ErrorCode.BOOKMARK_NOT_FOUND,
        }
        code = code_map.get(element_type.lower(), ErrorCode.OPERATION_FAILED)
        msg = f"{element_type.capitalize()} not found: {identifier}"
        if search_scope:
            msg += f" (searched in {search_scope})"
        return cls(
            code=code,
            message=msg,
            details={"element_type": element_type, "identifier": identifier},
        )

    @classmethod
    def from_exception(cls, exc: Exception, context: Optional[str] = None) -> DocError:
        """Create a DocError from an exception."""
        msg = str(exc)
        if context:
            msg = f"{context}: {msg}"
        return cls(
            code=ErrorCode.OPERATION_FAILED,
            message=msg,
            cause=exc,
        )


@dataclass
class Ok(Generic[T]):
    """Success case of Result, containing the value."""

    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        """Get the value, assuming success."""
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Get the value or return default."""
        return self.value

    def unwrap_err(self) -> DocError:
        """Get the error - raises since this is Ok."""
        raise ValueError("Called unwrap_err on Ok value")

    def map(self, fn: Callable[[T], U]) -> Result[U]:
        """Transform the success value."""
        return Ok(fn(self.value))

    def map_err(self, fn: Callable[[DocError], DocError]) -> Result[T]:
        """Transform the error (no-op for Ok)."""
        return self

    def and_then(self, fn: Callable[[T], Result[U]]) -> Result[U]:
        """Chain another operation that may fail."""
        return fn(self.value)

    def or_else(self, fn: Callable[[DocError], Result[T]]) -> Result[T]:
        """Return this Ok, ignoring the fallback."""
        return self


@dataclass
class Err(Generic[T]):
    """Failure case of Result, containing the error."""

    error: DocError

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> T:
        """Get the value - raises since this is Err."""
        raise ValueError(f"Called unwrap on Err: {self.error}")

    def unwrap_or(self, default: T) -> T:
        """Get the value or return default."""
        return default

    def unwrap_err(self) -> DocError:
        """Get the error."""
        return self.error

    def map(self, fn: Callable[[T], U]) -> Result[U]:
        """Transform the success value (no-op for Err)."""
        return Err(self.error)

    def map_err(self, fn: Callable[[DocError], DocError]) -> Result[T]:
        """Transform the error."""
        return Err(fn(self.error))

    def and_then(self, fn: Callable[[T], Result[U]]) -> Result[U]:
        """Chain another operation (no-op for Err)."""
        return Err(self.error)

    def or_else(self, fn: Callable[[DocError], Result[T]]) -> Result[T]:
        """Try the fallback operation."""
        return fn(self.error)


# Type alias for Result
Result = Union[Ok[T], Err[T]]


def collect_results(results: List[Result[T]]) -> Result[List[T]]:
    """
    Collect a list of Results into a Result of list.

    If all results are Ok, returns Ok with all values.
    If any result is Err, returns the first error.

    Example:
        results = [Ok(1), Ok(2), Ok(3)]
        collected = collect_results(results)  # Ok([1, 2, 3])

        results = [Ok(1), Err(error), Ok(3)]
        collected = collect_results(results)  # Err(error)
    """
    values: List[T] = []
    for result in results:
        if result.is_err():
            return Err(result.unwrap_err())
        values.append(result.unwrap())
    return Ok(values)


def try_operation(fn: Callable[[], T], context: Optional[str] = None) -> Result[T]:
    """
    Execute a function and wrap exceptions in Result.

    Example:
        result = try_operation(lambda: Document(path), "Opening document")
        match result:
            case Ok(doc):
                # use doc
            case Err(error):
                print(error)
    """
    try:
        return Ok(fn())
    except FileNotFoundError as e:
        return Err(DocError.file_not_found(str(e.filename or "")))
    except PermissionError as e:
        return Err(
            DocError(
                code=ErrorCode.FILE_PERMISSION_DENIED,
                message=f"Permission denied: {e}",
                cause=e,
            )
        )
    except Exception as e:
        return Err(DocError.from_exception(e, context))
