"""OpenAI (GPT + DALL·E / gpt-image-1) provider."""
import base64
from typing import List, Dict, Optional

import config

_client = None
_client_per_key: dict[str, any] = {}


def _get(api_key: Optional[str] = None):
    key = api_key or config.OPENAI_API_KEY
    if not api_key:
        global _client
        if _client is None:
            from openai import AsyncOpenAI
            _client = AsyncOpenAI(api_key=key)
        return _client
    if key not in _client_per_key:
        from openai import AsyncOpenAI
        _client_per_key[key] = AsyncOpenAI(api_key=key)
    return _client_per_key[key]


async def chat(model_id: str, history: List[Dict[str, str]],
               api_key: Optional[str] = None) -> str:
    messages = [{"role": "system", "content": config.SYSTEM_PROMPT}] + history
    resp = await _get(api_key).chat.completions.create(
        model=model_id,
        messages=messages,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


async def image(prompt: str, api_key: Optional[str] = None) -> bytes:
    resp = await _get(api_key).images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        n=1,
    )
    return base64.b64decode(resp.data[0].b64_json)
