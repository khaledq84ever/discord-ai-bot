"""Central configuration — everything comes from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Default model used by a server until /model changes it.
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.0-flash")

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
    "gemini-1.5-pro":    os.getenv("ID_GEMINI_PRO", "gemini-1.5-pro"),
    "claude-sonnet":     os.getenv("ID_CLAUDE_SONNET", "claude-sonnet-4-6"),
    "claude-opus":       os.getenv("ID_CLAUDE_OPUS", "claude-opus-4-7"),
}

# Arabic-first system prompt shared by every provider.
SYSTEM_PROMPT = (
    "You are a helpful, friendly AI assistant for an Arabic-speaking Discord "
    "community (Kuwait/Gulf region first). Detect the language of each user "
    "message and ALWAYS reply in that same language. When the user writes in "
    "Arabic, reply in clear Modern Standard Arabic with a warm, natural Gulf "
    "tone. When they write in English, reply in English. Keep answers concise, "
    "well-formatted for Discord (use markdown, short paragraphs), and avoid "
    "walls of text. You are running inside a Discord chat room."
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
