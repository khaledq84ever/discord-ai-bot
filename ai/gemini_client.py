"""Google Gemini provider (chat + Imagen image generation). FREE tier friendly."""
import asyncio
from typing import List, Dict

import config

_configured = False


def _ensure():
    global _configured
    if not _configured:
        import google.generativeai as genai
        genai.configure(api_key=config.GOOGLE_API_KEY)
        _configured = True


async def chat(model_id: str, history: List[Dict[str, str]]) -> str:
    _ensure()
    import google.generativeai as genai

    # Gemini uses 'user'/'model' roles and a separate system_instruction.
    contents = []
    for m in history:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [m["content"]]})

    model = genai.GenerativeModel(
        model_id, system_instruction=config.SYSTEM_PROMPT
    )
    # google-generativeai is sync; run it off the event loop.
    resp = await asyncio.to_thread(model.generate_content, contents)
    return resp.text.strip()


async def image(prompt: str) -> bytes:
    """Generate an image with Imagen and return PNG bytes."""
    _ensure()
    import google.generativeai as genai

    def _gen():
        model = genai.ImageGenerationModel("imagen-3.0-generate-002")
        result = model.generate_images(prompt=prompt, number_of_images=1)
        return result.images[0]._image_bytes

    return await asyncio.to_thread(_gen)
