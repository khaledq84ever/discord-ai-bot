# 📌 PROJECT INFO — Discord AI Bot (single source of truth)

Everything you need to pick this project back up anytime: accounts, IDs, URLs,
and the exact commands. **No secrets are stored here** — secret tokens/keys
live only in `.env` (gitignored). This file is safe to commit.

> Last updated: 2026-05-27

---

## 1. What this is
A multi-model AI Discord bot (GPT + Gemini + Claude) with image generation,
Arabic-first. Users chat with it inside Discord "AI rooms"; admins add it to
their server with one click from a public landing page.

- **Local folder:** `/home/khaled/discord-ai-bot/`
- **Language/stack:** Python + `discord.py` v2
- **Bot host:** Railway (worker process)
- **Landing page host:** Vercel (static)

---

## 2. Accounts & IDs (NOT secret — safe to keep)

| Service | Detail |
|---|---|
| **GitHub repo** | https://github.com/khaledq84ever/discord-ai-bot (private, branch `master`) |
| **GitHub user** | `khaledq84ever` |
| **Discord app name** | `AI Bot` |
| **Discord Application ID** | `1509039897577656400` |
| **Discord Public Key** | `b2fd83e4a52a9b44f6565efef0166c04c97a893ee6a77fcfe50353fcb0fbe7bf` |
| **Vercel account** | `khaledq84ever-1215` (team `khaledq8s-projects`) |
| **Vercel project** | `discordbot` (id `prj_W33zhBaQt3o7iyX2tK6HCFnB7ZxU`) |
| **Railway account** | `khaledq84ever@gmail.com` |

### Logins (how to sign in — no passwords stored)
- **Discord Developer Portal:** https://discord.com/developers/applications (log in with your Discord account)
- **GitHub:** `gh auth status` — already logged in as `khaledq84ever`
- **Vercel:** `vercel whoami` — already logged in as `khaledq84ever-1215`
- **Railway:** `railway whoami`. If it says *Unauthorized*, re-login (interactive):
  `railway login --browserless` (opens a code/URL to approve on your phone)

---

## 3. Live URLs
- **Add-to-Discord landing page:** https://discordbot-khaledq8s-projects.vercel.app
- **One-click invite link (what the button uses):**
  `https://discord.com/oauth2/authorize?client_id=1509039897577656400&permissions=117760&scope=bot%20applications.commands`
- **Bot live URL:** none — a Discord bot has no web page; it connects out to Discord.

---

## 4. Secrets — where they go (fill these in `.env`, never here)
Copy `.env.example` to `.env` and fill in:

| Variable | What it is | Where to get it |
|---|---|---|
| `DISCORD_TOKEN` | Bot token (SECRET) | Dev Portal → your app → **Bot** → Reset Token |
| `GOOGLE_API_KEY` | Free Gemini key | https://aistudio.google.com/apikey |
| `OPENAI_API_KEY` | GPT + DALL·E (paid, optional) | https://platform.openai.com/api-keys |
| `ANTHROPIC_API_KEY` | Claude (paid, optional) | https://console.anthropic.com |

⚠️ On Discord Dev Portal → **Bot** page, also enable **MESSAGE CONTENT INTENT** and Save.

For Railway, set the same variables in the dashboard (Variables tab) or via CLI.

---

## 5. Common commands

### Save your work (git → GitHub)
```bash
cd /home/khaled/discord-ai-bot
git add -A && git commit -m "your message" && git push
```

### Run the bot locally
```bash
cd /home/khaled/discord-ai-bot
pip install -r requirements.txt
cp .env.example .env        # then fill in DISCORD_TOKEN + GOOGLE_API_KEY
python3 bot.py
```

### Test the AI only (free Gemini, no Discord needed)
```bash
GOOGLE_API_KEY=your-key python3 test_gemini.py
```

### Update + redeploy the landing page (Vercel)
```bash
cd /home/khaled/discord-ai-bot/web
vercel --prod --yes
```

### Deploy the bot (Railway) — first time
```bash
cd /home/khaled/discord-ai-bot
railway login --browserless        # only if 'railway whoami' says Unauthorized
railway init --name discordbot     # create the project
# set variables:
railway variables --set DISCORD_TOKEN=xxx --set GOOGLE_API_KEY=xxx
# add a Volume mounted at /data in the dashboard (for chat history)
railway up --detach                # deploy via Dockerfile
```

---

## 6. In-Discord usage (after the bot is online)
- `/setchannel` — make the current channel an AI room (then just type to chat)
- `/model` — switch GPT / Gemini / Claude
- `/ask <question>` — one-off question anywhere
- `/imagine <prompt>` — generate an image
- `/reset` — clear the channel's memory
- `/help` — command list

---

## 7. Status / TODO
- [x] Bot code built + verified (compiles, DB read/write works)
- [x] Pushed to GitHub
- [x] Landing page live on Vercel (public, admins-only add — enforced by Discord)
- [x] One-click button wired with real Application ID
- [ ] Enable MESSAGE CONTENT INTENT + copy bot token
- [ ] Add `GOOGLE_API_KEY` (free Gemini) — run `test_gemini.py` to confirm
- [ ] Deploy bot to Railway (re-login first, add volume at `/data`)
