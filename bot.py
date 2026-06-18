"""Multi-model AI Discord bot — chat rooms + image generation, Arabic-first.

Reads every message in designated AI rooms in real time, stores it in the
live SQLite DB, and replies using the server's selected model
(GPT / Gemini / Claude). Slash commands let users switch models and generate
images.
"""
import io
import os
import time
import asyncio
import hashlib
import logging
from datetime import datetime

import discord
from discord import app_commands

import config
import memory
import steamrip
from ai import router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aibot")

intents = discord.Intents.default()
# Channel free-chat needs Message Content Intent (ON in Developer Portal).
# Set env MESSAGE_CONTENT=0 to run slash-commands-only until that toggle is enabled.
intents.message_content = os.getenv("MESSAGE_CONTENT", "1") == "1"

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# user_id -> last request timestamp (simple per-user cooldown)
_cooldowns: dict[int, float] = {}


def _rate_limited(user_id: int) -> bool:
    now = time.time()
    last = _cooldowns.get(user_id, 0)
    if now - last < config.USER_COOLDOWN:
        return True
    _cooldowns[user_id] = now
    return False


async def _send_long(target, text: str):
    """Split replies over Discord's 2000-char limit into multiple messages."""
    for i in range(0, len(text), 1990):
        await target.send(text[i:i + 1990])


AVATAR_PATH = os.path.join(os.path.dirname(__file__), "assets", "avatar.png")


async def _auto_setup():
    """One-time bot appearance setup: upload the avatar if it changed.

    Idempotent — we store the avatar file's hash in the DB and only call
    Discord again when the image actually changes, to avoid hitting the
    strict avatar-edit rate limit on every restart.
    """
    if os.getenv("SET_AVATAR", "1") != "1" or not os.path.exists(AVATAR_PATH):
        return
    with open(AVATAR_PATH, "rb") as f:
        data = f.read()
    digest = hashlib.sha256(data).hexdigest()
    if memory.get_meta("avatar_hash") == digest:
        return
    try:
        await bot.user.edit(avatar=data)
        memory.set_meta("avatar_hash", digest)
        log.info("Bot avatar set from %s", AVATAR_PATH)
    except discord.HTTPException as e:
        log.warning("Could not set avatar (rate limit or perms): %s", e)


WELCOME = (
    "👋 **مرحباً! أنا بوت الذكاء الاصطناعي.**\n"
    "للبدء، يكتب أحد المشرفين الأمر `/setchannel` في القناة اللي يبيها، "
    "وبعدها أي رسالة فيها أرد عليها تلقائياً. أو استخدموا `/ask` و `/imagine` "
    "من أي مكان. اكتبوا `/help` للأوامر كلها.\n\n"
    "👋 **Hi! I'm your AI bot.** An admin runs `/setchannel` to turn a channel "
    "into an AI room, then just type to chat. Or use `/ask` and `/imagine` "
    "anywhere. Type `/help` for everything."
)


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Post a friendly how-to the moment the bot is added to a server."""
    channel = guild.system_channel
    if channel is None or not channel.permissions_for(guild.me).send_messages:
        channel = next(
            (c for c in guild.text_channels
             if c.permissions_for(guild.me).send_messages), None)
    if channel is not None:
        try:
            await channel.send(WELCOME)
        except discord.HTTPException:
            pass
    log.info("Joined guild '%s' (%d) — now in %d server(s).",
             guild.name, guild.id, len(bot.guilds))


@bot.event
async def on_ready():
    memory.init()
    memory.init_steamrip()
    await _auto_setup()
    await _resume_steamrip_auto()
    asyncio.create_task(_steamrip_watchdog())
    # Global commands work in every server worldwide but can take up to an hour
    # to propagate. Set DEV_GUILD_ID to also sync instantly to your test server.
    dev_guild = os.getenv("DEV_GUILD_ID")
    if dev_guild:
        g = discord.Object(id=int(dev_guild))
        tree.copy_global_to(guild=g)
        await tree.sync(guild=g)
        log.info("Synced commands instantly to dev guild %s", dev_guild)
    await tree.sync()
    log.info("Logged in as %s — slash commands synced (global).", bot.user)
    log.info("In %d server(s). Invite: %s", len(bot.guilds), config.invite_url())


@bot.event
async def on_message(message: discord.Message):
    # Ignore the bot's own messages and other bots.
    if message.author.bot:
        return
    # Only auto-respond inside designated AI rooms.
    if not message.guild or not memory.is_ai_channel(message.channel.id):
        return
    content = message.content.strip()
    if not content:
        return
    if _rate_limited(message.author.id):
        return

    # Store the user's message in the live DB (real-time history).
    memory.add_message(message.channel.id, "user", content,
                       author=message.author.display_name)

    model_key = memory.get_model(message.guild.id)
    history = memory.get_history(message.channel.id)

    async with message.channel.typing():
        try:
            reply = await router.chat(model_key, history, user_id=message.author.id)
        except router.ProviderError as e:
            await message.reply(
                f"⚠️ تعذّر الاتصال بالذكاء الاصطناعي / AI request failed:\n`{e}`"
            )
            return

    memory.add_message(message.channel.id, "assistant", reply)
    await _send_long(message.channel, reply)


# --------------------------------------------------------------------------- #
#  Slash commands
# --------------------------------------------------------------------------- #

@tree.command(name="ask", description="اسأل الذكاء الاصطناعي / Ask the AI a question")
@app_commands.describe(prompt="سؤالك / your question")
async def ask(interaction: discord.Interaction, prompt: str):
    if _rate_limited(interaction.user.id):
        await interaction.response.send_message(
            "⏳ مهلاً قليلاً / slow down a sec.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    model_key = memory.get_model(interaction.guild_id)
    history = [{"role": "user", "content": prompt}]
    try:
        reply = await router.chat(model_key, history, user_id=interaction.user.id)
    except router.ProviderError as e:
        await interaction.followup.send(f"⚠️ {e}")
        return
    # followup has the same 2000 cap; chunk it.
    chunks = [reply[i:i + 1990] for i in range(0, len(reply), 1990)]
    await interaction.followup.send(chunks[0])
    for c in chunks[1:]:
        await interaction.channel.send(c)


def _detect_provider(api_key: str) -> str | None:
    """Guess the provider from the key's prefix so users can just paste a key.
    Order matters: Anthropic keys also start with 'sk-', so check it first."""
    k = (api_key or "").strip()
    if k.startswith("sk-ant-"):
        return "anthropic"
    if k.startswith("AIza"):
        return "google"
    if k.startswith("sk-") or k.startswith("sess-"):
        return "openai"
    return None


@tree.command(name="model", description="غيّر النموذج أو المفتاح / Switch model or set your API key")
@app_commands.describe(
    action="ماذا تريد أن تفعل؟ / what to do",
    provider="اختياري — يُكتشف تلقائياً / optional — auto-detected from the key",
    api_key="مفتاح API الخاص بك / your API key (for setkey)",
)
@app_commands.choices(action=[
    app_commands.Choice(name="اختر النموذج / pick model", value="pick"),
    app_commands.Choice(name="🔑 setkey — تعيين مفتاح API", value="setkey"),
    app_commands.Choice(name="🗑️ rmkey — حذف مفتاح API", value="rmkey"),
    app_commands.Choice(name="👀 mykeys — عرض مفاتيحي", value="mykeys"),
])
@app_commands.choices(provider=[
    app_commands.Choice(name="OpenAI", value="openai"),
    app_commands.Choice(name="Google (Gemini)", value="google"),
    app_commands.Choice(name="Anthropic (Claude)", value="anthropic"),
])
async def model(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    provider: app_commands.Choice[str] = None,
    api_key: str = None,
):
    if action.value == "pick":
        current = memory.get_model(interaction.guild_id)
        options = [discord.SelectOption(label=k) for k in config.MODEL_MENU]
        select = discord.ui.Select(
            placeholder="اختر النموذج / pick a model", options=options)
        async def select_cb(interaction: discord.Interaction):
            choice = select.values[0]
            memory.set_model(interaction.guild_id, choice)
            await interaction.response.edit_message(
                content=f"✅ النموذج الحالي / active model: **{choice}**", view=None)
        select.callback = select_cb
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message(
            f"النموذج الحالي / current: **{current}**", view=view, ephemeral=True)
        return

    if action.value == "setkey":
        if not api_key:
            await interaction.response.send_message(
                "⚠️ الصق المفتاح فقط وسأكتشف المزوّد تلقائياً.\n"
                "Just paste the key — I'll detect the provider.\n"
                "مثال / Example: `/model setkey sk-ant-xxx...`",
                ephemeral=True)
            return
        # Provider is optional — auto-detect from the key prefix if not given.
        prov = provider.value if provider else _detect_provider(api_key)
        if not prov:
            await interaction.response.send_message(
                "❓ لم أتعرّف على نوع المفتاح. اختر المزوّد يدوياً.\n"
                "Couldn't detect the provider — pick it manually with the "
                "`provider` option (openai / google / anthropic).",
                ephemeral=True)
            return
        memory.set_user_api_key(interaction.user.id, prov, api_key.strip())
        await interaction.response.send_message(
            f"🔑 تم حفظ مفتاح **{prov}** تلقائياً! المفتاح مخفي ولن يراه أحد.\n"
            f"**{prov}** API key saved (auto-detected)! It's private to you.",
            ephemeral=True)
        return

    if action.value == "rmkey":
        if not provider:
            await interaction.response.send_message(
                "⚠️ استخدم: `/model rmkey <provider>`\n"
                "Example: `/model rmkey openai`",
                ephemeral=True)
            return
        memory.remove_user_api_key(interaction.user.id, provider.value)
        await interaction.response.send_message(
            f"🗑️ تم حذف مفتاح **{provider.value}** / key removed.", ephemeral=True)
        return

    if action.value == "mykeys":
        lines = []
        for prov in ("openai", "google", "anthropic"):
            key = memory.get_user_api_key(interaction.user.id, prov)
            if key:
                masked = key[:8] + "…" + key[-4:]
                lines.append(f"🔑 **{prov}**: `{masked}`")
            else:
                lines.append(f"⚪ **{prov}**: غير مضبوط / not set")
        await interaction.response.send_message(
            "👤 **مفاتيح API الخاصة بك / Your API keys**\n" + "\n".join(lines),
            ephemeral=True)
        return


@tree.command(name="imagine", description="ولّد صورة / Generate an image")
@app_commands.describe(prompt="وصف الصورة / image description",
                       provider="openai أو google")
@app_commands.choices(provider=[
    app_commands.Choice(name="OpenAI (DALL·E)", value="openai"),
    app_commands.Choice(name="Google (Imagen)", value="google"),
])
async def imagine(interaction: discord.Interaction, prompt: str,
                  provider: app_commands.Choice[str] = None):
    if _rate_limited(interaction.user.id):
        await interaction.response.send_message(
            "⏳ مهلاً قليلاً / slow down a sec.", ephemeral=True)
        return
    prov = provider.value if provider else config.DEFAULT_IMAGE_PROVIDER
    await interaction.response.defer(thinking=True)
    try:
        data = await router.image(prov, prompt, user_id=interaction.user.id)
    except router.ProviderError as e:
        await interaction.followup.send(f"⚠️ تعذّر توليد الصورة / image failed:\n`{e}`")
        return
    file = discord.File(io.BytesIO(data), filename="image.png")
    embed = discord.Embed(description=f"🎨 {prompt}")
    embed.set_image(url="attachment://image.png")
    await interaction.followup.send(embed=embed, file=file)


@tree.command(name="setchannel", description="فعّل غرفة الذكاء الاصطناعي هنا / Make this an AI room")
async def setchannel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "🔒 للمشرفين فقط / admins only.", ephemeral=True)
        return
    memory.add_channel(interaction.channel_id, interaction.guild_id)
    await interaction.response.send_message(
        "✅ هذه الغرفة الآن غرفة ذكاء اصطناعي. اكتب أي رسالة وسأرد!\n"
        "This channel is now an AI room — just type to chat.")


@tree.command(name="unsetchannel", description="أوقف غرفة الذكاء الاصطناعي / Stop AI room")
async def unsetchannel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "🔒 للمشرفين فقط / admins only.", ephemeral=True)
        return
    memory.remove_channel(interaction.channel_id)
    await interaction.response.send_message("🛑 تم الإيقاف / AI room disabled here.")


@tree.command(name="reset", description="امسح ذاكرة المحادثة / Clear this channel's memory")
async def reset(interaction: discord.Interaction):
    memory.clear_history(interaction.channel_id)
    await interaction.response.send_message("🧹 تم مسح المحادثة / conversation cleared.")


@tree.command(name="help", description="مساعدة / Help")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 AI Bot — مساعدة / Help",
        description=(
            "**/ask** — اسأل سؤالاً / ask a question\n"
            "**/model** — غيّر النموذج أو المفتاح / switch model or set API key\n"
            "**/imagine** — ولّد صورة / generate an image\n"
            "**/setchannel** — فعّل غرفة الدردشة الذكية (مشرف) / enable AI room (admin)\n"
            "**/unsetchannel** — إيقاف الغرفة / disable AI room\n"
            "**/reset** — امسح ذاكرة المحادثة / clear memory\n"
            "**/info** — معلومات البوت / about this bot\n"
            "**/steamrip** — أحدث ألعاب SteamRIP (جديد فقط) / latest new SteamRIP games\n"
            "**/steamrip-search** — ابحث في SteamRIP / search SteamRIP games\n"
            "**/steamrip-auto** — بث لعبة جديدة كل دقيقة / auto-post a new game every 1 min\n\n"
            "داخل غرفة الذكاء الاصطناعي، فقط اكتب رسالتك وسأرد تلقائياً.\n"
            "Inside an AI room, just type and I'll reply automatically."
        ),
        color=0xE8001C,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Colored dot per provider — matches the brand promo banners.
_PROVIDER_DOT = {"openai": "🟢", "google": "🔵", "anthropic": "🟣"}

HERO_PATH = os.path.join(os.path.dirname(__file__), "assets", "promo", "01-hero.png")


@tree.command(name="info", description="معلومات البوت / About this bot")
async def info_cmd(interaction: discord.Interaction):
    """Public, pro-looking 'about' card — colored icons + branded banner,
    so the info is screenshot-ready."""
    current = (memory.get_model(interaction.guild_id)
               if interaction.guild_id else config.DEFAULT_MODEL)

    # Group models by provider, each line led by its colored dot. The active
    # model is shown in bold.
    by_provider: dict[str, list[str]] = {}
    for key in config.MODEL_MENU:
        prov = config.provider_for(key)
        label = f"**{key}**" if key == current else f"`{key}`"
        by_provider.setdefault(prov, []).append(label)
    model_lines = "\n".join(
        f"{_PROVIDER_DOT.get(prov, '⚪')} {' · '.join(items)}"
        for prov, items in by_provider.items()
    )

    embed = discord.Embed(
        title="🤖 AI Bot — المعلومات / Info",
        description=(
            "بوت ذكاء اصطناعي متعدد النماذج، عربي أولاً.\n"
            "Multi-model AI assistant — Arabic-first, works in any server."
        ),
        color=0xE8001C,
    )
    if bot.user and bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    # --- the 5 colored-icon fields ---
    embed.add_field(
        name="🧠 النماذج / Models",
        value=f"{model_lines}\n— الحالي / active: **{current}**",
        inline=False,
    )
    embed.add_field(
        name="🎨 توليد الصور / Image gen",
        value="🟡 `/imagine` — DALL·E + Google Imagen",
        inline=True,
    )
    embed.add_field(
        name="🌐 اللغات / Languages",
        value="🔴 عربي + English (كشف تلقائي / auto)",
        inline=True,
    )
    embed.add_field(
        name="💻 الكود / Source",
        value=f"⚫ [GitHub]({config.GITHUB_URL}) · open source",
        inline=True,
    )
    embed.add_field(
        name="➕ أضف البوت / Add the bot",
        value=f"🔵 [Invite]({config.invite_url()}) · [Website]({config.LANDING_URL})",
        inline=True,
    )

    embed.set_footer(
        text=f"في {len(bot.guilds)} سيرفر / in {len(bot.guilds)} servers · /help")

    # Attach the branded hero banner as the embed image when it's available.
    if os.path.exists(HERO_PATH):
        file = discord.File(HERO_PATH, filename="hero.png")
        embed.set_image(url="attachment://hero.png")
        await interaction.response.send_message(embed=embed, file=file)
    else:
        await interaction.response.send_message(embed=embed)


# --------------------------------------------------------------------------- #
#  SteamRIP commands — no duplicates, auto every 1 min
# --------------------------------------------------------------------------- #

_STEAMRIP_COLOR = 0x1B2838
_steamrip_auto_jobs: dict[int, asyncio.Task] = {}
_steamrip_last_post: dict[int, float] = {}  # guild_id -> timestamp of last post


def _steamrip_embed(game: dict, index: int = 0) -> discord.Embed:
    embed = discord.Embed(
        title=f"{index + 1}. {game['title']}",
        color=_STEAMRIP_COLOR,
    )
    if game.get("genre"):
        embed.add_field(name="🎮 Genre", value=game["genre"], inline=True)
    if game.get("size") and game["size"] != "—":
        embed.add_field(name="💾 Size", value=game["size"], inline=True)
    if game.get("version"):
        embed.add_field(name="📦 Version", value=game["version"], inline=False)
    if game.get("upload_date"):
        try:
            dt = datetime.fromisoformat(game["upload_date"])
            embed.add_field(name="📅 Added", value=dt.strftime("%Y-%m-%d"), inline=True)
        except ValueError:
            pass
    if game.get("image_url"):
        embed.set_image(url=game["image_url"])
    dl = game.get("download_urls", [])
    if dl:
        links = "\n".join(f"• [{u.split('/')[2]}]({u})" if "//" in u else f"• {u}" for u in dl)
        embed.add_field(name="⬇️ Download", value=links, inline=False)
    return embed


async def _steamrip_fresh(
    guild_id: int, limit: int = 5, skip_titles: set[str] | None = None,
) -> list[dict]:
    """Unposted games from the FULL catalog (newest first), so every command
    run yields new games until the whole catalog is exhausted.
    `skip_titles` (lowercased) are also excluded — used to skip games already
    visible in the channel, not just the ones in the posted-DB."""
    skip = skip_titles or set()
    all_games = await steamrip.list_all_games()
    fresh = []
    for g in all_games:
        if len(fresh) >= limit:
            break
        title = g.get("title", "")
        if not title:
            continue
        if memory.is_steamrip_posted(guild_id, title):
            continue
        if title.strip().lower() in skip:
            continue
        fresh.append(g)
    await steamrip.attach_images(fresh)
    return fresh


def _strip_index(title: str) -> str:
    """'1. Game Name' -> 'Game Name'. Embeds are titled with an ordinal prefix."""
    head, sep, rest = title.partition(". ")
    return rest if (sep and head.isdigit()) else title


async def _steamrip_dedupe_channel(channel) -> set[str]:
    """Scan recent history, delete duplicate SteamRIP game posts (keeping one
    of each), and return the set of game titles (lowercased) still in the
    channel — so we never re-post a game that's already visible there.
    
    Deletes are paced (max 5/loop with 1.5s delay) to avoid Discord rate limits."""
    seen: set[str] = set()
    to_delete: list = []
    try:
        async for msg in channel.history(limit=200):
            if msg.author.id != bot.user.id or not msg.embeds:
                continue
            embed = msg.embeds[0]
            color = embed.color.value if embed.color else None
            if color != _STEAMRIP_COLOR or not embed.title:
                continue
            key = _strip_index(embed.title).strip().lower()
            if key in seen:
                to_delete.append(msg)
            else:
                seen.add(key)
        # Delete duplicates slowly to avoid 429 rate limits
        deleted = 0
        for msg in to_delete:
            if deleted >= 5:
                break
            try:
                await msg.delete()
                deleted += 1
                await asyncio.sleep(1.5)
            except (discord.Forbidden, discord.NotFound):
                pass
    except discord.Forbidden:
        log.warning("steamrip dedupe: missing Read History permission")
    return seen


@tree.command(
    name="steamrip",
    description="أحدث ألعاب SteamRIP (جديد فقط) / Latest new SteamRIP games",
)
@app_commands.describe(count="عدد الألعاب / number of games (1-10, default 5)")
async def steamrip_latest(
    interaction: discord.Interaction,
    count: app_commands.Range[int, 1, 10] = 5,
):
    await interaction.response.defer(thinking=True)
    try:
        games = await _steamrip_fresh(interaction.guild_id, limit=count)
    except Exception as e:
        await interaction.followup.send(f"⚠️ فشل في جلب الألعاب / Failed to fetch games:\n`{e}`")
        return
    if not games:
        await interaction.followup.send(
            "✅ كل الألعاب الجديدة تم عرضها مسبقاً! كل الألعاب منشورة بالفعل.\n"
            "✅ All new games have been shown already!"
        )
        return
    for g in games:
        memory.mark_steamrip_posted(interaction.guild_id, g.get("title", ""))
    embeds = [_steamrip_embed(g, i) for i, g in enumerate(games)]
    embed = embeds[0]
    embed.description = f"🎮 أحدث {len(games)} ألعاب من **SteamRIP** / Latest from SteamRIP"
    embed.set_footer(text=f"طلب من {interaction.user.display_name}")
    await interaction.followup.send(embed=embed)
    for e in embeds[1:]:
        await interaction.channel.send(embed=e)


@tree.command(
    name="steamrip-search",
    description="ابحث عن لعبة في SteamRIP / Search a game on SteamRIP",
)
@app_commands.describe(query="اسم اللعبة / game name")
async def steamrip_search(interaction: discord.Interaction, query: str):
    if len(query) < 2:
        await interaction.response.send_message(
            "⚠️ أدخل على الأقل حرفين / Enter at least 2 characters.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        games = await steamrip.search_games(query, limit=5)
    except Exception as e:
        await interaction.followup.send(f"⚠️ فشل في البحث / Search failed:\n`{e}`")
        return
    if not games:
        await interaction.followup.send(
            f"⚠️ لا توجد نتائج لـ \"{query}\" / No results for \"{query}\"."
        )
        return
    embeds = [_steamrip_embed(g, i) for i, g in enumerate(games)]
    embed = embeds[0]
    embed.description = f"نتائج البحث عن \"{query}\" في **SteamRIP** / Search results"
    embed.set_footer(text=f"طلب من {interaction.user.display_name}")
    await interaction.followup.send(embed=embed)
    for e in embeds[1:]:
        await interaction.channel.send(embed=e)


# ---- steamrip auto-post helpers (persistent + watchdog) -------------------

async def _start_steamrip_auto(guild_id: int, channel, *, persist: bool = True) -> None:
    """Create and store an auto-post loop for this guild/channel."""
    if guild_id in _steamrip_auto_jobs:
        _steamrip_auto_jobs[guild_id].cancel()
        del _steamrip_auto_jobs[guild_id]

    async def _loop():
        while True:
            try:
                seen = await _steamrip_dedupe_channel(channel)
                games = await _steamrip_fresh(guild_id, limit=1, skip_titles=seen)
                if games:
                    g = games[0]
                    memory.mark_steamrip_posted(guild_id, g.get("title", ""))
                    embed = _steamrip_embed(g)
                    embed.description = None
                    await channel.send(embed=embed)
                    _steamrip_last_post[guild_id] = time.time()
            except Exception as e:
                log.warning("steamrip-auto error: %s", e)
            await asyncio.sleep(60)

    task = asyncio.create_task(_loop())
    _steamrip_auto_jobs[guild_id] = task
    if persist:
        memory.save_auto_channel(guild_id, channel.id)


def _stop_steamrip_auto(guild_id: int) -> None:
    """Cancel the auto-post loop and remove from DB."""
    task = _steamrip_auto_jobs.pop(guild_id, None)
    if task:
        task.cancel()
    _steamrip_last_post.pop(guild_id, None)
    memory.remove_auto_channel(guild_id)


async def _steamrip_watchdog():
    """Every 60s: restart any dead auto task, if it's been silent >3 min restart it."""
    await bot.wait_until_ready()
    while True:
        await asyncio.sleep(60)
        for guild_id, task in list(_steamrip_auto_jobs.items()):
            if task.done():
                log.warning("steamrip watchdog: task for guild %s died, restarting", guild_id)
                rows = memory.get_auto_channels()
                for gid, cid in rows:
                    if gid == guild_id:
                        channel = bot.get_channel(cid)
                        if channel:
                            await _start_steamrip_auto(guild_id, channel, persist=False)
                        break
        # Auto-restart if silent >3 min (task alive but stuck)
        now = time.time()
        for guild_id, last in list(_steamrip_last_post.items()):
            if now - last > 180:
                log.warning("steamrip watchdog: guild %s silent >3min, restarting", guild_id)
                rows = memory.get_auto_channels()
                for gid, cid in rows:
                    if gid == guild_id:
                        channel = bot.get_channel(cid)
                        if channel:
                            await _start_steamrip_auto(guild_id, channel, persist=False)
                        break


@tree.command(
    name="steamrip-auto",
    description="شغّل بث ألعاب SteamRIP كل دقيقة / Auto-post new games every 1 min",
)
async def steamrip_auto(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    if guild_id in _steamrip_auto_jobs:
        _stop_steamrip_auto(guild_id)
        await interaction.response.send_message(
            "🛑 تم إيقاف البث التلقائي / Auto-post stopped.", ephemeral=True)
        return

    await _start_steamrip_auto(guild_id, interaction.channel)
    try:
        await interaction.response.send_message(
            "▶️ تم تشغيل البث التلقائي! سأنشر لعبة جديدة كل دقيقة وأحذف المكرّر.\n"
            "▶️ Auto-post started! A new game every minute — I read the channel "
            "first and delete duplicates so it stays clean.\n"
            "`/steamrip-auto` مرة أخرى للإيقاف / run again to stop.",
            ephemeral=True)
    except:
        pass


# ---- resume auto-post on restart + start watchdog -------------------------

async def _resume_steamrip_auto():
    """On bot ready, restart auto-post for every guild that had it enabled."""
    rows = memory.get_auto_channels()
    for guild_id, channel_id in rows:
        guild = bot.get_guild(guild_id)
        if not guild:
            continue
        channel = guild.get_channel(channel_id)
        if channel:
            await _start_steamrip_auto(guild_id, channel, persist=False)
            log.info("Resumed steamrip-auto in guild %s", guild_id)


if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set — see .env.example")
    if not intents.message_content:
        log.warning("Running slash-command-only (MESSAGE_CONTENT=0). "
                    "Enable Message Content Intent in the portal + set MESSAGE_CONTENT=1 for channel chat.")
    bot.run(config.DISCORD_TOKEN)
