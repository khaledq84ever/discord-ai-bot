"""OpenAI (GPT + DALL·E / gpt-image-1) provider."""
import base64
from typing import List, Dict

import config

_client = None


def _get():
    global _client
    if _client is None:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


async def chat(model_id: str, history: List[Dict[str, str]]) -> str:
    messages = [{"role": "system", "content": config.SYSTEM_PROMPT}] + history
    resp = await _get().chat.completions.create(
        model=model_id,
        messages=messages,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


async def image(prompt: str) -> bytes:
    """Return raw PNG bytes for the prompt."""
    resp = await _get().images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        n=1,
    )
    return base64.b64decode(resp.data[0].b64_json)
