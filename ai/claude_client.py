"""Anthropic Claude provider (chat only — no image generation)."""
from typing import List, Dict

import config

_client = None


def _get():
    global _client
    if _client is None:
        from anthropic import AsyncAnthropic
        _client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


async def chat(model_id: str, history: List[Dict[str, str]]) -> str:
    # Anthropic takes the system prompt as a top-level arg, not a message.
    messages = [
        {"role": m["role"], "content": m["content"]} for m in history
    ]
    resp = await _get().messages.create(
        model=model_id,
        system=config.SYSTEM_PROMPT,
        max_tokens=1024,
        messages=messages,
    )
    return "".join(
        block.text for block in resp.content if block.type == "text"
    ).strip()
