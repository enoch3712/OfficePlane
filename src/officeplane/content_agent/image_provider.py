"""Pluggable image provider.

Env var ``OFFICEPLANE_IMAGE_PROVIDER`` selects the backend:
- ``placeholder`` (default): Pillow draws a labeled grey box. Zero network.
- ``gemini``: Google Imagen via google-generativeai. Requires GOOGLE_API_KEY.
- ``openai``: DALL-E via openai SDK. Requires OPENAI_API_KEY.

Each provider exposes::

    async def generate_image(prompt: str, *, width: int = 1024, height: int = 768) -> bytes

Returns PNG bytes. Raises RuntimeError on failure with a clear message.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod


class ImageProvider(ABC):
    @abstractmethod
    async def generate_image(self, prompt: str, *, width: int = 1024, height: int = 768) -> bytes: ...


class PlaceholderProvider(ImageProvider):
    async def generate_image(self, prompt: str, *, width: int = 1024, height: int = 768) -> bytes:
        from PIL import Image, ImageDraw, ImageFont
        import io
        img = Image.new("RGB", (width, height), (40, 44, 52))
        draw = ImageDraw.Draw(img)
        # Title bar
        draw.rectangle([(0, 0), (width, 60)], fill=(94, 252, 171))
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
            small = ImageFont.truetype("DejaVuSans.ttf", 16)
        except OSError:
            font = ImageFont.load_default()
            small = font
        draw.text((20, 18), "Generated figure", fill=(15, 17, 22), font=font)
        # Wrap prompt to box
        words = prompt.split()
        lines, line = [], ""
        for w in words:
            test = (line + " " + w).strip()
            if len(test) <= 60:
                line = test
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        y = 100
        for ln in lines[:20]:
            draw.text((20, y), ln, fill=(220, 226, 236), font=small)
            y += 24
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


class GeminiImageProvider(ImageProvider):
    def __init__(self, model: str = "gemini-2.5-flash-image"):
        self._model = model
        self._key = os.getenv("GOOGLE_API_KEY")
        if not self._key:
            raise RuntimeError("GOOGLE_API_KEY required for GeminiImageProvider")

    async def generate_image(self, prompt: str, *, width: int = 1024, height: int = 768) -> bytes:
        # Use google-generativeai SDK in an executor to avoid blocking the loop.
        import asyncio
        import google.generativeai as genai
        genai.configure(api_key=self._key)
        model = genai.GenerativeModel(self._model)

        def _call():
            resp = model.generate_content([prompt])
            # New SDK returns multipart; pluck the first image part
            for part in resp.candidates[0].content.parts:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data and "image" in getattr(inline, "mime_type", ""):
                    return bytes(inline.data)
            raise RuntimeError("Gemini did not return image bytes")

        return await asyncio.get_event_loop().run_in_executor(None, _call)


class OpenAIImageProvider(ImageProvider):
    def __init__(self, model: str = "dall-e-3"):
        self._model = model
        self._key = os.getenv("OPENAI_API_KEY")
        if not self._key:
            raise RuntimeError("OPENAI_API_KEY required for OpenAIImageProvider")

    async def generate_image(self, prompt: str, *, width: int = 1024, height: int = 768) -> bytes:
        import asyncio
        import base64
        from openai import OpenAI
        client = OpenAI(api_key=self._key)
        # Round size to DALL-E supported (1024x1024 / 1024x1792 / 1792x1024)
        size = "1024x1024"
        if width > height * 1.3:
            size = "1792x1024"
        elif height > width * 1.3:
            size = "1024x1792"

        def _call():
            r = client.images.generate(
                model=self._model,
                prompt=prompt,
                size=size,
                response_format="b64_json",
                n=1,
            )
            return base64.b64decode(r.data[0].b64_json)

        return await asyncio.get_event_loop().run_in_executor(None, _call)


def get_provider() -> ImageProvider:
    name = (os.getenv("OFFICEPLANE_IMAGE_PROVIDER") or "placeholder").lower()
    if name == "gemini":
        return GeminiImageProvider()
    if name == "openai":
        return OpenAIImageProvider()
    return PlaceholderProvider()
