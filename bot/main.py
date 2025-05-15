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

    await bot.tree.sync()


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
