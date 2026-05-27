"""Central configuration — everything comes from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
# Public (non-secret) Discord Application/Client ID — used to build the invite.
APPLICATION_ID = os.getenv("APPLICATION_ID", "1509039897577656400")
# Bot permissions bitfield: view channels + send messages + read history +
# embed links + attach files + add reactions.
INVITE_PERMISSIONS = os.getenv("INVITE_PERMISSIONS", "117824")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Default model used by a server until /model changes it.
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.0-flash")

# Gemini image-generation model (free-tier capable). The old Imagen
# `ImageGenerationModel` needed a paid Vertex project; this one works on a
# free API key. Override if your account exposes a dedicated Imagen model.
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

# Where the SQLite "live" database lives. On Railway, point this at a mounted
# volume (e.g. /data/bot.db) so conversation history survives restarts.
DB_PATH = os.getenv("DB_PATH", "bot.db")

# How many past messages of a channel to feed the model for context.
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "15"))

# Per-user cooldown (seconds) to protect your API bill.
USER_COOLDOWN = float(os.getenv("USER_COOLDOWN", "3"))

# Friendly model menu -> actual provider model id. Override ids via env if your
# account exposes different names.
MODEL_MENU = {
    "gpt-4o":            os.getenv("ID_GPT4O", "gpt-4o"),
    "gpt-4o-mini":       os.getenv("ID_GPT4O_MINI", "gpt-4o-mini"),
    "gemini-2.0-flash":  os.getenv("ID_GEMINI_FLASH", "gemini-2.0-flash"),
    "gemini-2.5-flash":  os.getenv("ID_GEMINI_25_FLASH", "gemini-2.5-flash"),
    "gemini-2.5-pro":    os.getenv("ID_GEMINI_PRO", "gemini-2.5-pro"),
    "claude-sonnet":     os.getenv("ID_CLAUDE_SONNET", "claude-sonnet-4-6"),
    "claude-opus":       os.getenv("ID_CLAUDE_OPUS", "claude-opus-4-7"),
}

# Which provider /imagine uses when the user doesn't pick one. Google works on
# a free Gemini key; OpenAI (DALL·E) needs a paid key.
DEFAULT_IMAGE_PROVIDER = os.getenv("DEFAULT_IMAGE_PROVIDER", "google")

# Arabic-first system prompt shared by every provider.
SYSTEM_PROMPT = (
    "You are «AI Bot», a sharp, friendly AI assistant living inside a Discord "
    "server for an Arabic-speaking community (Kuwait & the Gulf first).\n\n"
    "LANGUAGE: Detect the language of each message and ALWAYS reply in that "
    "same language. For Arabic, reply in clear, natural Arabic with a warm "
    "Gulf/Kuwaiti tone (لهجة خليجية ودّية) — never stiff or robotic. For "
    "English, reply in English. If the user mixes, mirror their mix.\n\n"
    "STYLE: Be concise and genuinely useful. Format for Discord: short "
    "paragraphs, **bold** for key points, bullet lists when helpful, and put "
    "code in fenced ``` blocks with the language tag. Avoid walls of text and "
    "don't overuse emojis (one or two when they add warmth).\n\n"
    "HONESTY: If you're unsure or lack the info, say so plainly instead of "
    "inventing facts. For current events you can't verify, be clear about the "
    "limit. Keep the conversation context in mind — you can see recent "
    "messages in this channel.\n\n"
    "SAFETY: Be respectful and family-friendly. Politely decline harmful, "
    "hateful, or explicit requests. You cannot send DMs, manage the server, or "
    "act outside this chat."
)


def invite_url() -> str:
    """One-click 'Add to Discord' OAuth2 authorize URL for this bot."""
    return (
        "https://discord.com/oauth2/authorize"
        f"?client_id={APPLICATION_ID}"
        f"&permissions={INVITE_PERMISSIONS}"
        "&scope=bot%20applications.commands"
    )


def provider_for(model_key: str) -> str:
    """Return which provider a friendly model key belongs to."""
    if model_key.startswith("gpt"):
        return "openai"
    if model_key.startswith("gemini"):
        return "google"
    if model_key.startswith("claude"):
        return "anthropic"
    return "google"
