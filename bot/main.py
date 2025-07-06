import discord
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from discord.ext import commands
from .utils.database import mongo_client  # 確保你有這個模組

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

SERVER_GUILD_ID = os.getenv("SERVER_GUILD_ID")
if SERVER_GUILD_ID:
    SERVER_GUILD_ID = int(SERVER_GUILD_ID)

SYNC_COMMANDS_GLOBAL = os.getenv("SYNC_COMMANDS_GLOBAL", "False").lower() == "true"
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
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")

    try:
        await mongo_client.admin.command("ping")
        logger.info("✅ MongoDB Connection Sucess!")
    except Exception as e:
        logger.error(f"❌ MongoDB Connection Fail: {e}")

    # 自動載入 bot/cogs 下所有 cogs
    cogs_path = Path(__file__).parent / "cogs"
    loaded_count = 0
    failed_count = 0

    for file in cogs_path.rglob("*.py"):
        if file.name.startswith("_"):
            continue
        relative = file.relative_to(Path(__file__).parent.parent)
        module_name = ".".join(relative.with_suffix("").parts)
        try:
            await bot.load_extension(module_name)
            logger.info(f"✅ 成功載入模組：{module_name}")
            loaded_count += 1
        except Exception as e:
            logger.error(f"❌ 載入模組 {module_name} 失敗：{e}")
            failed_count += 1

    logger.info(f"📦 共載入 {loaded_count} 個模組，失敗 {failed_count} 個。")

    # 指令同步邏輯
    if SYNC_COMMANDS_GLOBAL:
        try:
            commands = await bot.tree.sync()
            logger.info(f"✅ 已全局同步 {len(commands)} 個指令。")
        except Exception as e:
            logger.error(f"❌ 全域指令同步時發生錯誤：{e}")
    else:
        guild_ids_to_sync = []
        if SERVER_GUILD_ID:
            guild_ids_to_sync.append(SERVER_GUILD_ID)
        guild_ids_to_sync.extend(DEV_GUILD_IDS)
        guild_ids_to_sync = list(set(guild_ids_to_sync))

        if not guild_ids_to_sync:
            logger.warning(
                "DEV_GUILD_IDS 和 SERVER_GUILD_ID 都未設定，將不進行指令同步。"
            )
        else:
            for guild_id in guild_ids_to_sync:
                guild = bot.get_guild(guild_id)
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
                        f"ℹ️ 無法找到 ID 為 {guild_id} 的伺服器，跳過指令同步。"
                    )

    activity = get_activity(ACTIVITY_TYPE, ACTIVITY_TEXT, ACTIVITY_URL)
    status = status_map.get(BOT_STATUS)
    await bot.change_presence(status=status, activity=activity)
    logger.info(
        f"✅ 狀態已設置為 {BOT_STATUS}，類型為 {ACTIVITY_TYPE}, 文字為 {ACTIVITY_TEXT}。"
    )


if __name__ == "__main__":
    bot.run(BOT_TOKEN)

