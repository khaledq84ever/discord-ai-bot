# Work Notes — Discord AI Bot

## 2026-06-03 — Dependency upgrade

Bumped `requirements.txt` to current tested baseline:
`discord.py>=2.7.1, openai>=2.40.0, google-genai>=2.7.0, anthropic>=0.105.2,
python-dotenv>=1.2.2, aiohttp>=3.14.0`.

Checked the provider clients (`ai/openai_client.py`, `claude_client.py`, `gemini_client.py`)
against the new SDK majors — all use API surfaces still valid in openai 2.x / anthropic
0.105 / google-genai 2.x, so no code changes needed.

**Verified:** Railway deploy logs → *"Logged in as AI Bot#5087 — slash commands synced
(global), in 3 servers"*. (Voice warning is expected — this bot doesn't use voice.)
**Shipped:** Railway `ai-bot` SUCCESS · GitHub `master` commit `645b4f8`.
