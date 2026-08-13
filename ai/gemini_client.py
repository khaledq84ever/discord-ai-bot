"""Google Gemini provider (chat + image generation) on the new google-genai SDK.

Uses the FREE-tier-friendly google-genai package (the old google-generativeai
package is fully deprecated). Chat goes through generate_content; image
generation uses a Gemini image-capable model so it works on a free API key
(the old Imagen `ImageGenerationModel` required a paid/Vertex project).
"""
import asyncio
from typing import List, Dict, Optional

import config

_client = None
_client_per_key: dict[str, any] = {}
_MAX_CACHED_CLIENTS = 200  # cap so distinct user-supplied keys can't grow this forever

# Free-tier image-capable Gemini model. Override via env if your account
# exposes a different one (e.g. an Imagen model on a paid project).
_IMAGE_MODEL = config.GEMINI_IMAGE_MODEL


def _get(api_key: Optional[str] = None):
    key = api_key or config.GOOGLE_API_KEY
    if not api_key:
        global _client
        if _client is None:
            from google import genai
            _client = genai.Client(api_key=key)
        return _client
    if key not in _client_per_key:
        from google import genai
        if len(_client_per_key) >= _MAX_CACHED_CLIENTS:
            _client_per_key.pop(next(iter(_client_per_key)))
        _client_per_key[key] = genai.Client(api_key=key)
    return _client_per_key[key]


async def chat(model_id: str, history: List[Dict[str, str]],
               api_key: Optional[str] = None) -> str:
    from google.genai import types

    client = _get(api_key)
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


async def image(prompt: str, api_key: Optional[str] = None) -> bytes:
    client = _get(api_key)

    def _gen():
        resp = client.models.generate_content(
            model=_IMAGE_MODEL,
            contents=prompt,
        )
        for cand in resp.candidates or []:
            content = getattr(cand, "content", None)
            for part in (getattr(content, "parts", None) or []):
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    return inline.data
        raise RuntimeError("Gemini did not return image data.")

    return await asyncio.to_thread(_gen)
