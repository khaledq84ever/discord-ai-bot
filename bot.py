"""Multi-model AI Discord bot — chat rooms + image generation, Arabic-first.

Reads every message in designated AI rooms in real time, stores it in the
live SQLite DB, and replies using the server's selected model
(GPT / Gemini / Claude). Slash commands let users switch models and generate
images.
"""
import io
import os
import time
import hashlib
import logging

import discord
from discord import app_commands

import config
import memory
from ai import router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aibot")

intents = discord.Intents.default()
intents.message_content = True  # REQUIRED — enable in Developer Portal too.

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
    await _auto_setup()
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
            reply = await router.chat(model_key, history)
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
        reply = await router.chat(model_key, history)
    except router.ProviderError as e:
        await interaction.followup.send(f"⚠️ {e}")
        return
    # followup has the same 2000 cap; chunk it.
    chunks = [reply[i:i + 1990] for i in range(0, len(reply), 1990)]
    await interaction.followup.send(chunks[0])
    for c in chunks[1:]:
        await interaction.channel.send(c)


class ModelSelect(discord.ui.Select):
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        options = [discord.SelectOption(label=k) for k in config.MODEL_MENU]
        super().__init__(placeholder="اختر النموذج / pick a model", options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        memory.set_model(self.guild_id, choice)
        await interaction.response.edit_message(
            content=f"✅ النموذج الحالي / active model: **{choice}**", view=None)


@tree.command(name="model", description="غيّر نموذج الذكاء الاصطناعي / Switch the AI model")
async def model(interaction: discord.Interaction):
    current = memory.get_model(interaction.guild_id)
    view = discord.ui.View()
    view.add_item(ModelSelect(interaction.guild_id))
    await interaction.response.send_message(
        f"النموذج الحالي / current: **{current}**", view=view, ephemeral=True)


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
        data = await router.image(prov, prompt)
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
            "**/model** — غيّر النموذج (GPT/Gemini/Claude) / switch model\n"
            "**/imagine** — ولّد صورة / generate an image\n"
            "**/setchannel** — فعّل غرفة الدردشة الذكية (مشرف) / enable AI room (admin)\n"
            "**/unsetchannel** — إيقاف الغرفة / disable AI room\n"
            "**/reset** — امسح ذاكرة المحادثة / clear memory\n\n"
            "داخل غرفة الذكاء الاصطناعي، فقط اكتب رسالتك وسأرد تلقائياً.\n"
            "Inside an AI room, just type and I'll reply automatically."
        ),
        color=0xE8001C,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set — see .env.example")
    bot.run(config.DISCORD_TOKEN)
