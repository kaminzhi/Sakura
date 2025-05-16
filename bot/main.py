import discord, logging, redis
from discord.ext import commands
import os
from dotenv import load_dotenv
from .utils import redis_manager, checks

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
redis_client = redis_manager.get_redis_client()


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    try:
        redis_client.ping()
        logging.info("✅ Redis Connection Sucess!")
        redis_client.set("bot:status", "online")
        logging.info(f"✅ Bot Status: {redis_client.get('bot:status')}")
    except redis.exceptions.ConnectionError as e:
        logging.error(f"❌ Redis Connection Fail: {e}")

    # await bot.load_extension("bot.cogs.messaging")
    await bot.load_extension("bot.cogs.link_fixer")
    await bot.load_extension("bot.cogs.welcome")

    guild_id_to_sync = "1188104401093668866"  # 將這裡替換為你的伺服器 ID
    guild = bot.get_guild(guild_id_to_sync)
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
        try:
            commands = await bot.tree.sync()
            logger.info(f"✅ 已進行全域指令同步 {len(commands)} 個指令。")
        except Exception as e:
            logger.error(f"❌ 全域指令同步時發生錯誤：{e}")


@bot.event
async def on_guild_join(guild):
    logging.info(f"Bot Joined Server: {guild.name} (ID: {guild.id})")


@bot.event
async def on_guild_remove(guild):
    logging.info(f"Bot Left Server: {guild.name} (ID: {guild.id})")
    keys_to_delete = redis_client.keys(f"guild:{guild.id}:*")
    if keys_to_delete:
        redis_client.delete(*keys_to_delete)
        logging.info(f"Cleared keys for guild {guild.id}: {keys_to_delete}")


if __name__ == "__main__":
    bot.run(TOKEN)
