# Zoya Image Generation Tool v1

Adds a controlled text-to-image tool named `imagegen`.

## Provider

Primary provider: Google Gemini native image generation through the REST Interactions API.

Default model: `gemini-3.1-flash-image`.

Configuration:

- `GEMINI_API_KEY` (preferred) or `GOOGLE_API_KEY`
- `GEMINI_IMAGE_MODEL` (optional override)

No Python image SDK is required; the adapter uses Python's standard library HTTP client.

## Supported request fields

- `prompt`
- `output_file` (optional; defaults to `generated_images/zoya_image_<timestamp>.png` inside the workspace)
- `aspect_ratio` (optional)
- `image_size` (optional: 512, 1K, 2K, 4K)

## Routing examples

- `Ek boy ki image generate karo jiske haath mein mobile hai.`
- `IMAGE GENERATION PROMPT: cinematic anime boy...`
- Requests that merely resize/edit an existing image are not intercepted by this tool.

## Safety / architecture

- Output paths are constrained to Zoya's workspace.
- Network permission is explicit and tool-scoped: only `imagegen` is allowed by the default execution policy.
- The Brain routes image generation; it never executes the provider call itself.
- Existing GenOffice spreadsheet/slides support is preserved.
