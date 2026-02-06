---
name: generate-image
description: Generate images using the Gemini vision model (nanobanana pro). Use when the user wants to create, generate, or make an image from a text description.
argument-hint: [prompt]
allowed-tools: Bash, Write, Read
---

Generate an image using the Gemini API based on the user's prompt.

## Instructions

1. Take the user's prompt from `$ARGUMENTS`
2. Run the image generation script at `.claude/skills/generate-image/generate.py`, passing the prompt as a command-line argument:

```bash
python3 .claude/skills/generate-image/generate.py "$ARGUMENTS"
```

3. The script will:
   - Use the `GEMINI_API_KEY` environment variable (already set)
   - Call `gemini-3-pro-image-preview` with image generation config
   - Save the output image to the current working directory
   - Print the filename and any text response from the model

4. After the script runs, read the generated image file to show it to the user.

5. If the script fails, check that:
   - `GEMINI_API_KEY` is set in the environment
   - The `google-genai` package is installed (`pip install google-genai`)

## Notes
- The generated images are saved as PNG/JPEG files in the current directory
- The model may also return text alongside the image
- Aspect ratio, image size, and person generation settings can be customized by editing the script
