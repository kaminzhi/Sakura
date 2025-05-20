import discord, logging
from discord.ext import commands
import os
from dotenv import load_dotenv
from .utils.database import mongo_client

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SERVER_GUILD_ID = os.getenv("SERVER_GUILD_ID")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    try:
        await mongo_client.admin.command("ping")
        logging.info("✅ MongoDB Connection Sucess!")
    except Exception as e:
        logging.error(f"❌ MongoDB Connection Fail: {e}")

    # await bot.load_extension("bot.cogs.messaging")
    await bot.load_extension("bot.cogs.link_fixer")
    # await bot.load_extension("bot.cogs.welcome")
    await bot.load_extension("bot.cogs.ping")
    await bot.load_extension("bot.cogs.linkfix_settings")

    guild = bot.get_guild(SERVER_GUILD_ID)
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


if __name__ == "__main__":
    bot.run(BOT_TOKEN)
