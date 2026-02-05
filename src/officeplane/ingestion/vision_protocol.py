"""Protocol definition for vision model adapters."""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Protocol, runtime_checkable


@dataclass
class VisionResponse:
    """Response from a vision model analysis.

    Attributes:
        raw_text: The raw text response from the model.
        json_data: Parsed JSON data if the response was valid JSON.
        model: The model that generated the response.
        usage: Token usage information if available.
        error: Error message if the request failed.
    """

    raw_text: str = ""
    json_data: Optional[Any] = None
    model: str = ""
    usage: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Whether the response was successful."""
        return self.error is None and (bool(self.raw_text) or self.json_data is not None)


@runtime_checkable
class VisionModelProtocol(Protocol):
    """Protocol for vision model adapters.

    This follows the same pattern as LLMProtocol in components/runner.py,
    allowing different vision model providers to be plugged in.
    """

    async def analyze_images(
        self,
        images: List[bytes],
        prompt: str,
        system_prompt: Optional[str] = None,
        start_page: int = 1,
    ) -> VisionResponse:
        """Analyze images and extract information.

        Args:
            images: List of image bytes (JPEG or PNG).
            prompt: The prompt describing what to extract from the images.
            system_prompt: Optional system prompt for additional context.
            start_page: Starting page number for image labels (1-indexed).

        Returns:
            VisionResponse containing the model's analysis.
        """
        ...

    @property
    def supports_batch(self) -> bool:
        """Whether this adapter supports multiple images in a single call."""
        ...

    @property
    def max_images_per_call(self) -> int:
        """Maximum number of images that can be sent in a single call."""
        ...

    @property
    def model_name(self) -> str:
        """The name of the model being used."""
        ...
