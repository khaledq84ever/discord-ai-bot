"""Google Gemini provider (chat + image generation) on the new google-genai SDK.

Uses the FREE-tier-friendly google-genai package (the old google-generativeai
package is fully deprecated). Chat goes through generate_content; image
generation uses a Gemini image-capable model so it works on a free API key
(the old Imagen `ImageGenerationModel` required a paid/Vertex project).
"""
import asyncio
from typing import List, Dict

import config

_client = None

# Free-tier image-capable Gemini model. Override via env if your account
# exposes a different one (e.g. an Imagen model on a paid project).
_IMAGE_MODEL = config.GEMINI_IMAGE_MODEL


def _get():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=config.GOOGLE_API_KEY)
    return _client


async def chat(model_id: str, history: List[Dict[str, str]]) -> str:
    from google.genai import types

    client = _get()
    # Gemini uses 'user'/'model' roles; the system prompt is a separate config.
    contents = []
    for m in history:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=m["content"])])
        )

    def _call():
        resp = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=config.SYSTEM_PROMPT,
            ),
        )
        return (resp.text or "").strip()

    text = await asyncio.to_thread(_call)
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text


async def image(prompt: str) -> bytes:
    """Generate an image and return raw PNG/JPEG bytes (free-tier friendly)."""
    from google.genai import types

    client = _get()

    def _gen():
        resp = client.models.generate_content(
            model=_IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )
        for cand in resp.candidates or []:
            content = getattr(cand, "content", None)
            for part in (getattr(content, "parts", None) or []):
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    return inline.data
        raise RuntimeError("Gemini did not return image data.")

    return await asyncio.to_thread(_gen)
