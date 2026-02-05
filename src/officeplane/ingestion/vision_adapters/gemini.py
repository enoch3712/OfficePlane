"""Gemini Vision adapter for document structure extraction."""

import asyncio
import base64
import json
from typing import Any, Dict, List, Optional

from officeplane.ingestion.vision_protocol import VisionResponse

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None  # type: ignore
    GenerationConfig = None  # type: ignore


class GeminiVisionAdapter:
    """Vision adapter using Google's Gemini models.

    Uses the google-generativeai SDK with JSON mode for structured
    document extraction.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        max_images: int = 16,
    ):
        """Initialize the Gemini adapter.

        Args:
            api_key: Google API key for Gemini.
            model: Gemini model name.
            max_images: Maximum images per API call.

        Raises:
            ImportError: If google-generativeai is not installed.
            ValueError: If API key is empty.
        """
        if not GENAI_AVAILABLE:
            raise ImportError(
                "google-generativeai is required for GeminiVisionAdapter. "
                "Install it with: pip install google-generativeai"
            )

        if not api_key:
            raise ValueError("API key is required for GeminiVisionAdapter")

        self._api_key = api_key
        self._model_name = model
        self._max_images = max_images
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        """Get or create the Gemini client."""
        if self._client is None:
            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(
                model_name=self._model_name,
                generation_config=GenerationConfig(
                    response_mime_type="application/json",
                ),
            )
        return self._client

    async def analyze_images(
        self,
        images: List[bytes],
        prompt: str,
        system_prompt: Optional[str] = None,
        start_page: int = 1,
    ) -> VisionResponse:
        """Analyze images using Gemini vision model.

        Args:
            images: List of image bytes (JPEG or PNG).
            prompt: The prompt describing what to extract.
            system_prompt: Optional system instruction.
            start_page: Starting page number for image labels (1-indexed).

        Returns:
            VisionResponse with extracted structure.
        """
        if not images:
            return VisionResponse(error="No images provided")

        if len(images) > self._max_images:
            return VisionResponse(
                error=f"Too many images ({len(images)}). Maximum is {self._max_images}."
            )

        try:
            # Build content parts
            parts = self._build_parts(images, prompt, system_prompt, start_page)

            # Run synchronous API call in thread pool
            client = self._get_client()
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.generate_content(parts),
            )

            # Extract response text
            raw_text = response.text if hasattr(response, "text") else ""

            # Try to parse as JSON
            json_data = self._try_parse_json(raw_text)

            # Build usage info
            usage = {}
            if hasattr(response, "usage_metadata"):
                metadata = response.usage_metadata
                usage = {
                    "prompt_tokens": getattr(metadata, "prompt_token_count", 0),
                    "completion_tokens": getattr(metadata, "candidates_token_count", 0),
                    "total_tokens": getattr(metadata, "total_token_count", 0),
                }

            return VisionResponse(
                raw_text=raw_text,
                json_data=json_data,
                model=self._model_name,
                usage=usage,
            )

        except Exception as e:
            return VisionResponse(error=f"Gemini API error: {str(e)}")

    def _build_parts(
        self,
        images: List[bytes],
        prompt: str,
        system_prompt: Optional[str],
        start_page: int = 1,
    ) -> List[Any]:
        """Build content parts for Gemini API.

        Args:
            images: Image bytes list.
            prompt: User prompt.
            system_prompt: Optional system instruction.
            start_page: Starting page number for labels (1-indexed).

        Returns:
            List of content parts for the API.
        """
        parts = []

        # Add system prompt if provided
        if system_prompt:
            parts.append(system_prompt + "\n\n")

        # Add images with labels using absolute page numbers
        for i, image_bytes in enumerate(images):
            # Detect image type from magic bytes
            mime_type = self._detect_mime_type(image_bytes)

            # Create inline data dict
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(image_bytes).decode("utf-8"),
                }
            })

            # Add page label with absolute page number
            page_num = start_page + i
            parts.append(f"\n[Page {page_num}]\n")

        # Add main prompt
        parts.append(prompt)

        return parts

    def _detect_mime_type(self, image_bytes: bytes) -> str:
        """Detect MIME type from image bytes.

        Args:
            image_bytes: Image content.

        Returns:
            MIME type string.
        """
        if image_bytes[:4] == b"\x89PNG":
            return "image/png"
        if image_bytes[:2] == b"\xff\xd8":
            return "image/jpeg"
        if image_bytes[:4] == b"GIF8":
            return "image/gif"
        if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            return "image/webp"
        # Default to JPEG
        return "image/jpeg"

    def _try_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to parse text as JSON.

        Args:
            text: Text that might be JSON.

        Returns:
            Parsed JSON or None if parsing fails.
        """
        if not text:
            return None

        # Try direct parsing
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        if "```" in text:
            lines = text.split("\n")
            in_block = False
            json_lines = []

            for line in lines:
                if line.strip().startswith("```"):
                    if in_block:
                        break
                    in_block = True
                    continue
                if in_block:
                    json_lines.append(line)

            if json_lines:
                try:
                    return json.loads("\n".join(json_lines))
                except json.JSONDecodeError:
                    pass

        return None

    @property
    def supports_batch(self) -> bool:
        """Whether this adapter supports multiple images in a single call."""
        return True

    @property
    def max_images_per_call(self) -> int:
        """Maximum number of images that can be sent in a single call."""
        return self._max_images

    @property
    def model_name(self) -> str:
        """The name of the model being used."""
        return self._model_name
