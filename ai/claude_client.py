"""Anthropic Claude provider (chat only — no image generation)."""
from typing import List, Dict, Optional

import config

_client = None
_client_per_key: dict[str, any] = {}
_MAX_CACHED_CLIENTS = 200  # cap so distinct user-supplied keys can't grow this forever


def _get(api_key: Optional[str] = None):
    key = api_key or config.ANTHROPIC_API_KEY
    if not api_key:
        global _client
        if _client is None:
            from anthropic import AsyncAnthropic
            _client = AsyncAnthropic(api_key=key)
        return _client
    if key not in _client_per_key:
        from anthropic import AsyncAnthropic
        if len(_client_per_key) >= _MAX_CACHED_CLIENTS:
            _client_per_key.pop(next(iter(_client_per_key)))
        _client_per_key[key] = AsyncAnthropic(api_key=key)
    return _client_per_key[key]


async def chat(model_id: str, history: List[Dict[str, str]],
               api_key: Optional[str] = None) -> str:
    messages = [
        {"role": m["role"], "content": m["content"]} for m in history
    ]
    resp = await _get(api_key).messages.create(
        model=model_id,
        system=config.SYSTEM_PROMPT,
        max_tokens=1024,
        messages=messages,
    )
    return "".join(
        block.text for block in resp.content if block.type == "text"
    ).strip()
