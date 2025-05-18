import discord
import os, logging
from dotenv import load_dotenv
from bot.utils.database import mongo_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = discord.Bot(intents=intents)  # 如果你只使用斜線指令，不需要 command_prefix


async def setup_hook():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                logger.info(f"Loaded extension: {filename[:-3]}")
            except Exception as e:
                logger.error(
                    f"Failed to load extension {filename[:-3]}.", exc_info=True
                )


bot.setup_hook = setup_hook


@bot.event
async def on_ready():
    logger.info(f"✅ Logged in as {bot.user.name} ({bot.user.id})")
    logger.info(f"Discord.py version: {discord.__version__}")  # 檢查 py-cord 版本
    if bot.is_ready():
        logger.info("Bot is ready and connected to Discord.")
    else:
        logger.warning("Bot is not yet fully ready.")

    try:
        await mongo_client.admin.command("ping")
        logger.info("MongoDB connection is alive.")
    except Exception as e:
        logger.error("MongoDB connection failed.", exc_info=True)


if __name__ == "__main__":
    bot.run(TOKEN)
