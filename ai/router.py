"""Routes a chat/image request to the right provider based on the model key."""
from typing import List, Dict

import config
from ai import openai_client, gemini_client, claude_client


class ProviderError(Exception):
    pass


def _resolve(model_key: str):
    provider = config.provider_for(model_key)
    model_id = config.MODEL_MENU.get(model_key, model_key)
    return provider, model_id


async def chat(model_key: str, history: List[Dict[str, str]]) -> str:
    provider, model_id = _resolve(model_key)
    try:
        if provider == "openai":
            if not config.OPENAI_API_KEY:
                raise ProviderError("OPENAI_API_KEY is not set.")
            return await openai_client.chat(model_id, history)
        if provider == "google":
            if not config.GOOGLE_API_KEY:
                raise ProviderError("GOOGLE_API_KEY is not set.")
            return await gemini_client.chat(model_id, history)
        if provider == "anthropic":
            if not config.ANTHROPIC_API_KEY:
                raise ProviderError("ANTHROPIC_API_KEY is not set.")
            return await claude_client.chat(model_id, history)
        raise ProviderError(f"Unknown provider for model '{model_key}'.")
    except ProviderError:
        raise
    except Exception as e:  # surface provider SDK errors cleanly
        raise ProviderError(str(e)) from e


async def image(provider: str, prompt: str) -> bytes:
    try:
        if provider == "openai":
            if not config.OPENAI_API_KEY:
                raise ProviderError("OPENAI_API_KEY is not set.")
            return await openai_client.image(prompt)
        if provider == "google":
            if not config.GOOGLE_API_KEY:
                raise ProviderError("GOOGLE_API_KEY is not set.")
            return await gemini_client.image(prompt)
        raise ProviderError(f"'{provider}' cannot generate images.")
    except ProviderError:
        raise
    except Exception as e:
        raise ProviderError(str(e)) from e
