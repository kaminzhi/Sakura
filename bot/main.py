import discord, logging
import os
import json  # Import json for DEV_GUILD_IDS
from dotenv import load_dotenv
from discord.ext import commands
from .utils.database import mongo_client

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
# SERVER_GUILD_ID is used for specific guild sync, can be optional
# Consider using a list of DEV_GUILD_IDS for more flexibility
# For now, let's keep SERVER_GUILD_ID if it's explicitly set for a single guild.
SERVER_GUILD_ID = os.getenv("SERVER_GUILD_ID")  # Keep it as string initially
if SERVER_GUILD_ID:
    SERVER_GUILD_ID = int(SERVER_GUILD_ID)  # Convert to int if it exists

# New environment variable for global sync control
SYNC_COMMANDS_GLOBAL = os.getenv("SYNC_COMMANDS_GLOBAL", "False").lower() == "true"
# New environment variable for specific dev guilds (can be a comma-separated list or JSON array)
# Let's assume it's a comma-separated string of IDs for simplicity if not JSON.
DEV_GUILD_IDS_STR = os.getenv("DEV_GUILD_IDS", "")
DEV_GUILD_IDS = [
    int(gid.strip()) for gid in DEV_GUILD_IDS_STR.split(",") if gid.strip().isdigit()
]


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

BOT_STATUS = os.getenv("BOT_STATUS", "online")
ACTIVITY_TYPE = os.getenv("BOT_ACTIVITY_TYPE", None)
ACTIVITY_TEXT = os.getenv("BOT_ACTIVITY_TEXT")
ACTIVITY_URL = os.getenv("BOT_ACTIVITY_URL", None)

bot = commands.Bot(
    command_prefix=f"{os.getenv('command_prefix', '!')}", intents=intents
)


def get_activity(activity_type, activity_text, activity_url=None):
    if activity_type == "custom":
        return discord.CustomActivity(name=activity_text)
    elif activity_type == "streaming":
        return discord.Streaming(
            name=activity_text, url=activity_url or "https://twitch.tv/placeholder"
        )
    elif activity_type == "listening":
        return discord.Activity(type=discord.ActivityType.listening, name=activity_text)
    elif activity_type == "watching":
        return discord.Activity(type=discord.ActivityType.watching, name=activity_text)
    else:
        return discord.Game(name=activity_text or "啟動中...")


status_map = {
    "online": discord.Status.online,
    "idle": discord.Status.idle,
    "dnd": discord.Status.dnd,
    "invisible": discord.Status.invisible,
}


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    try:
        await mongo_client.admin.command("ping")
        logging.info("✅ MongoDB Connection Sucess!")
    except Exception as e:
        logging.error(f"❌ MongoDB Connection Fail: {e}")

    # Load your cogs (extensions) here.
    await bot.load_extension("bot.cogs.poll")
    await bot.load_extension("bot.cogs.role_selector")
    await bot.load_extension("bot.cogs.roulette")
    await bot.load_extension("bot.cogs.ban")
    await bot.load_extension("bot.cogs.devpanel")
    await bot.load_extension("bot.cogs.link_fixer")
    await bot.load_extension("bot.cogs.welcome")
    await bot.load_extension("bot.cogs.leave")
    await bot.load_extension("bot.cogs.settings_panel")
    await bot.load_extension("bot.cogs.announcement_panel")
    await bot.load_extension("bot.cogs.user_profile")
    await bot.load_extension("bot.cogs.ping")
    await bot.load_extension("bot.cogs.linkfix_settings")

    # --- Command Synchronization Logic ---
    if SYNC_COMMANDS_GLOBAL:
        try:
            commands = await bot.tree.sync()
            logger.info(f"✅ 已全局同步 {len(commands)} 個指令。")
        except Exception as e:
            logger.error(f"❌ 全域指令同步時發生錯誤：{e}")
    else:
        # Prioritize SERVER_GUILD_ID if set, otherwise use DEV_GUILD_IDS
        guild_ids_to_sync = []
        if SERVER_GUILD_ID:
            guild_ids_to_sync.append(SERVER_GUILD_ID)
        guild_ids_to_sync.extend(DEV_GUILD_IDS)  # Add any other dev guilds

        # Remove duplicates
        guild_ids_to_sync = list(set(guild_ids_to_sync))

        if not guild_ids_to_sync:
            logger.warning(
                "DEV_GUILD_IDS 和 SERVER_GUILD_ID 都未設定，將不進行指令同步。"
            )
        else:
            for guild_id in guild_ids_to_sync:
                guild = bot.get_guild(guild_id)  # Attempt to get the guild object

                if guild:
                    try:
                        commands = await bot.tree.sync(guild=guild)
                        logger.info(
                            f"✅ 已在伺服器 {guild.name} ({guild.id}) 強制同步 {len(commands)} 個指令。"
                        )
                    except discord.errors.Forbidden:
                        logger.error(
                            f"❌ 在伺服器 {guild.name} ({guild.id}) 同步指令時發生 Forbidden 錯誤。請檢查 Bot 是否擁有 '應用程式指令' 權限。"
                        )
                    except Exception as e:
                        logger.error(
                            f"❌ 在伺服器 {guild.name} ({guild.id}) 同步指令時發生錯誤：{e}"
                        )
                else:
                    logger.warning(
                        f"ℹ️ 無法找到 ID 為 {guild_id} 的伺服器 (機器人可能不在該伺服器中)，跳過指令同步。"
                    )

    # --- End Command Synchronization Logic ---

    activity = get_activity(ACTIVITY_TYPE, ACTIVITY_TEXT, ACTIVITY_URL)
    status = status_map.get(BOT_STATUS)
    await bot.change_presence(status=status, activity=activity)
    logger.info(
        f"✅ 狀態已設置為 {BOT_STATUS}，類型為 {ACTIVITY_TYPE}, 文字為 {ACTIVITY_TEXT}。"
    )


if __name__ == "__main__":
    bot.run(BOT_TOKEN)
