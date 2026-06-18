"""Routes a chat/image request to the right provider based on the model key."""
from typing import List, Dict, Optional

import config
import memory
from ai import openai_client, gemini_client, claude_client


class ProviderError(Exception):
    pass


def _resolve(model_key: str):
    provider = config.provider_for(model_key)
    model_id = config.MODEL_MENU.get(model_key, model_key)
    return provider, model_id


def _api_key(provider: str, user_id: Optional[int] = None) -> str:
    if user_id is not None:
        user_key = memory.get_user_api_key(user_id, provider)
        if user_key:
            return user_key
    return {
        "openai": config.OPENAI_API_KEY,
        "google": config.GOOGLE_API_KEY,
        "anthropic": config.ANTHROPIC_API_KEY,
    }.get(provider, "")


async def chat(model_key: str, history: List[Dict[str, str]],
               user_id: Optional[int] = None) -> str:
    provider, model_id = _resolve(model_key)
    key = _api_key(provider, user_id)
    if not key:
        raise ProviderError(
            f"مفتاح {provider} غير مضبوط / {provider} API key is not set.\n"
            "استخدم `/model setkey` لتعيين مفتاحك الخاص / set your key with `/model setkey`."
        )
    try:
        if provider == "openai":
            return await openai_client.chat(model_id, history, api_key=key)
        if provider == "google":
            return await gemini_client.chat(model_id, history, api_key=key)
        if provider == "anthropic":
            return await claude_client.chat(model_id, history, api_key=key)
        raise ProviderError(f"Unknown provider for model '{model_key}'.")
    except ProviderError:
        raise
    except Exception as e:
        raise ProviderError(str(e)) from e


async def image(provider: str, prompt: str,
                user_id: Optional[int] = None) -> bytes:
    key = _api_key(provider, user_id)
    if not key:
        raise ProviderError(
            f"مفتاح {provider} غير مضبوط / {provider} API key is not set.\n"
            "استخدم `/model setkey` لتعيين مفتاحك الخاص / set your key with `/model setkey`."
        )
    try:
        if provider == "openai":
            return await openai_client.image(prompt, api_key=key)
        if provider == "google":
            return await gemini_client.image(prompt, api_key=key)
        raise ProviderError(f"'{provider}' cannot generate images.")
    except ProviderError:
        raise
    except Exception as e:
        raise ProviderError(str(e)) from e
