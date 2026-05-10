"""Mock Vision adapter for testing document ingestion."""

from typing import Any, Callable, Dict, List, Optional

from officeplane.ingestion.vision_protocol import VisionResponse


class MockVisionAdapter:
    """Mock vision adapter for testing without API calls.

    Provides configurable responses for testing the ingestion pipeline.
    """

    def __init__(
        self,
        response_generator: Optional[Callable[[List[bytes], str], Dict[str, Any]]] = None,
        default_chapters: int = 1,
        canned_summary: Optional[str] = None,
        canned_topics: Optional[List[str]] = None,
        canned_key_entities: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the mock adapter.

        Args:
            response_generator: Optional function to generate custom responses.
                Takes (images, prompt) and returns a dict for json_data.
            default_chapters: Number of chapters to generate in default response.
            canned_summary: Optional document summary to include in responses.
            canned_topics: Optional list of topic tags to include in responses.
            canned_key_entities: Optional key entities dict to include in responses.
        """
        self._response_generator = response_generator
        self._default_chapters = default_chapters
        self._canned_summary = canned_summary
        self._canned_topics = canned_topics
        self._canned_key_entities = canned_key_entities
        self._call_count = 0
        self._call_history: List[Dict[str, Any]] = []

    async def analyze_images(
        self,
        images: List[bytes],
        prompt: str,
        system_prompt: Optional[str] = None,
        start_page: int = 1,
    ) -> VisionResponse:
        """Return mock analysis for testing.

        Args:
            images: List of image bytes.
            prompt: The prompt (used for logging).
            system_prompt: Optional system instruction (used for logging).
            start_page: Starting page number for image labels (1-indexed).

        Returns:
            VisionResponse with mock data.
        """
        self._call_count += 1
        self._call_history.append({
            "images_count": len(images),
            "prompt": prompt,
            "system_prompt": system_prompt,
            "start_page": start_page,
            "call_number": self._call_count,
        })

        if self._response_generator:
            try:
                json_data = self._response_generator(images, prompt)
                return VisionResponse(
                    raw_text="",
                    json_data=json_data,
                    model="mock",
                    usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                )
            except Exception as e:
                return VisionResponse(error=f"Mock generator error: {str(e)}")

        # Generate default response based on number of pages
        json_data = self._generate_default_response(len(images))

        return VisionResponse(
            raw_text="",
            json_data=json_data,
            model="mock",
            usage={
                "prompt_tokens": len(images) * 1000,
                "completion_tokens": 500,
                "total_tokens": len(images) * 1000 + 500,
            },
        )

    def _generate_default_response(self, page_count: int) -> Dict[str, Any]:
        """Generate a default document structure response.

        Args:
            page_count: Number of pages being analyzed.

        Returns:
            Document structure dict.
        """
        chapters = []
        pages_per_chapter = max(1, page_count // self._default_chapters)

        for i in range(self._default_chapters):
            start_page = i * pages_per_chapter + 1
            end_page = min((i + 1) * pages_per_chapter, page_count)

            if start_page > page_count:
                break

            chapter = {
                "title": f"Chapter {i + 1}",
                "summary": f"This is chapter {i + 1} of the document.",
                "sections": [
                    {
                        "title": f"Section {i + 1}.1",
                        "summary": f"section summary {i * 1 + 1}",
                        "pages": list(range(start_page, end_page + 1)),
                    }
                ],
            }
            chapters.append(chapter)

        response: Dict[str, Any] = {
            "title": "Mock Document",
            "author": "Mock Author",
            "chapters": chapters,
        }
        if self._canned_summary is not None:
            response["document_summary"] = self._canned_summary
        if self._canned_topics is not None:
            response["topics"] = self._canned_topics
        if self._canned_key_entities is not None:
            response["key_entities"] = self._canned_key_entities
        return response

    @property
    def supports_batch(self) -> bool:
        """Whether this adapter supports multiple images in a single call."""
        return True

    @property
    def max_images_per_call(self) -> int:
        """Maximum number of images that can be sent in a single call."""
        return 32

    @property
    def model_name(self) -> str:
        """The name of the model being used."""
        return "mock"

    @property
    def call_count(self) -> int:
        """Number of times analyze_images has been called."""
        return self._call_count

    @property
    def call_history(self) -> List[Dict[str, Any]]:
        """History of all analyze_images calls."""
        return self._call_history.copy()

    def reset(self) -> None:
        """Reset call count and history."""
        self._call_count = 0
        self._call_history = []


def create_mock_response(
    title: str = "Test Document",
    chapters: Optional[List[Dict[str, Any]]] = None,
    canned_summary: Optional[str] = None,
    canned_topics: Optional[List[str]] = None,
    canned_key_entities: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a mock document structure response.

    Args:
        title: Document title.
        chapters: List of chapter dicts.
        canned_summary: Optional document-level summary string.
        canned_topics: Optional list of topic tags.
        canned_key_entities: Optional key entities dict.

    Returns:
        Document structure dict.
    """
    if chapters is None:
        chapters = [
            {
                "title": "Introduction",
                "summary": "An introduction to the document.",
                "sections": [
                    {
                        "title": "Overview",
                        "summary": "section summary 1",
                        "pages": [1, 2],
                    }
                ],
            },
            {
                "title": "Main Content",
                "summary": "The main content of the document.",
                "sections": [
                    {
                        "title": "Details",
                        "summary": "section summary 2",
                        "pages": [3, 4, 5],
                    }
                ],
            },
        ]

    response: Dict[str, Any] = {
        "title": title,
        "author": "Test Author",
        "chapters": chapters,
    }
    if canned_summary is not None:
        response["document_summary"] = canned_summary
    if canned_topics is not None:
        response["topics"] = canned_topics
    if canned_key_entities is not None:
        response["key_entities"] = canned_key_entities
    return response
