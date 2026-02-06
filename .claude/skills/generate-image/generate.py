import mimetypes
import os
import sys
from google import genai
from google.genai import types


def save_binary_file(file_name, data):
    with open(file_name, "wb") as f:
        f.write(data)
    print(f"Image saved to: {file_name}")


def generate(prompt):
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-3-pro-image-preview"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        image_config=types.ImageConfig(
            image_size="1K",
        ),
        response_modalities=[
            "IMAGE",
            "TEXT",
        ],
    )

    file_index = 0
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        if chunk.parts is None:
            continue
        for part in chunk.parts:
            if part.inline_data and part.inline_data.data:
                file_extension = mimetypes.guess_extension(part.inline_data.mime_type) or ".png"
                file_name = f"generated_image_{file_index}{file_extension}"
                file_index += 1
                save_binary_file(file_name, part.inline_data.data)
            elif part.text:
                print(part.text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate.py <prompt>")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    generate(prompt)
