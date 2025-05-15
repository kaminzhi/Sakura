import discord, logging
from discord.ext import commands
import os
from dotenv import load_dotenv
from .utils import redis_manager

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
        logging.info("✅ Redis 連線成功!")  # 連線成功時的日誌
        redis_client.set("bot:status", "online")
        logging.info(f"✅ 已在 Redis 中設定 bot:status 為 online")
    except redis.exceptions.ConnectionError as e:
        logging.error(f"❌ Redis 連線失敗: {e}")  # 連線失敗時的日誌

    await bot.tree.sync()


if __name__ == "__main__":
    bot.run(TOKEN)
