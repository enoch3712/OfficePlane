"""Prompts for vision model document structure extraction."""

SYSTEM_PROMPT = """You are a document structure analyzer. Your task is to examine document page images and extract the hierarchical structure including chapters, sections, and page content.

You must respond with valid JSON only, no additional text or markdown formatting."""

STRUCTURE_EXTRACTION_PROMPT = """Analyze these document pages and extract the document structure.

For each page, identify:
1. Chapter titles/headings (typically larger text, numbered like "Chapter 1" or "1.", or styled as headings)
2. Section titles/subheadings (smaller than chapter headings but distinct from body text)
3. The text content of each page

Return a JSON object with this exact structure:

{
    "title": "Document title (from cover page or first major heading)",
    "author": "Author name if visible, otherwise null",
    "chapters": [
        {
            "title": "Chapter title",
            "summary": "Brief 1-2 sentence summary of the chapter content",
            "start_page": 1,
            "sections": [
                {
                    "title": "Section title",
                    "pages": [
                        {
                            "page_number": 1,
                            "content": "Full text content of this page"
                        }
                    ]
                }
            ]
        }
    ]
}

Rules:
- Page numbers should match the [Page N] labels in the input
- If no clear chapters exist, create a single chapter with the document title
- If no clear sections exist within a chapter, create a single section per chapter
- Extract ALL visible text content for each page
- Preserve paragraph breaks with double newlines
- Do not invent or hallucinate content - only extract what is visible
- For pages with only images/figures, note "[Figure/Image]" in content"""

BATCH_STRUCTURE_PROMPT = """Analyze these document pages (pages {start_page} to {end_page}) and extract the document structure.

This is batch {batch_number} of {total_batches} for this document.

For each page, identify:
1. Chapter titles/headings (typically larger text, numbered like "Chapter 1" or styled as headings)
2. Section titles/subheadings (smaller than chapter headings but distinct from body text)
3. The text content of each page

Return a JSON object with this exact structure:

{{
    "pages": [
        {{
            "page_number": <actual page number>,
            "chapter_title": "Chapter title if this page starts a new chapter, otherwise null",
            "section_title": "Section title if this page starts a new section, otherwise null",
            "content": "Full text content of this page"
        }}
    ]
}}

Rules:
- Page numbers should be the actual page numbers ({start_page} to {end_page})
- Only set chapter_title if the page contains a chapter heading
- Only set section_title if the page contains a section heading
- Extract ALL visible text content for each page
- Preserve paragraph breaks with double newlines
- For pages with only images/figures, note "[Figure/Image]" in content"""


def get_structure_prompt(
    start_page: int = 1,
    end_page: int = 1,
    batch_number: int = 1,
    total_batches: int = 1,
) -> str:
    """Get the appropriate structure extraction prompt.

    Args:
        start_page: First page number in the batch.
        end_page: Last page number in the batch.
        batch_number: Current batch number (1-indexed).
        total_batches: Total number of batches.

    Returns:
        Formatted prompt string.
    """
    if total_batches == 1:
        return STRUCTURE_EXTRACTION_PROMPT

    return BATCH_STRUCTURE_PROMPT.format(
        start_page=start_page,
        end_page=end_page,
        batch_number=batch_number,
        total_batches=total_batches,
    )


MERGE_PROMPT = """You have extracted page-by-page structure from a document across multiple batches.
Now merge these results into a coherent document structure.

Batch results:
{batch_results}

Merge these into a single document structure with this format:

{
    "title": "Document title",
    "author": "Author name or null",
    "chapters": [
        {
            "title": "Chapter title",
            "summary": "1-2 sentence summary",
            "sections": [
                {
                    "title": "Section title",
                    "pages": [1, 2, 3]
                }
            ]
        }
    ]
}

Rules:
- Combine consecutive pages into their proper chapters and sections
- If a chapter/section spans batches, merge them together
- Pages without explicit chapter/section headings belong to the previous chapter/section
- Generate summaries for each chapter based on the page content
- Pages list should contain just page numbers, not full page objects"""


def get_merge_prompt(batch_results: str) -> str:
    """Get the prompt for merging batch results.

    Args:
        batch_results: JSON string of all batch results.

    Returns:
        Formatted merge prompt.
    """
    return MERGE_PROMPT.format(batch_results=batch_results)
