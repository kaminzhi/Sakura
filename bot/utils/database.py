from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
MONGO_DATABASE_NAME = "sakuradatabase"  # 你的資料庫名稱

mongo_client = AsyncIOMotorClient(MONGODB_URI)
db = mongo_client[MONGO_DATABASE_NAME]  # 使用你定義的變數
guilds_collection = db["guilds"]


async def get_guild_data(guild_id: int) -> dict or None:
    logger.debug(f"Getting data for guild: {guild_id}")
    return await guilds_collection.find_one({"guild_id": guild_id})


async def update_guild_data(guild_id: int, data: dict, upsert: bool = True):
    logger.info(f"Updating data for guild: {guild_id} - {data}")
    await guilds_collection.update_one(
        {"guild_id": guild_id}, {"$set": data}, upsert=upsert
    )


async def push_guild_data(guild_id: int, key: str, value):
    logger.info(f"Pushing data for guild {guild_id}, key {key}: {value}")
    await guilds_collection.update_one(
        {"guild_id": guild_id}, {"$push": {key: value}}, upsert=True
    )


async def pull_guild_data(guild_id: int, key: str, value):
    logger.info(f"Pulling data for guild {guild_id}, key {key}: {value}")
    await guilds_collection.update_one({"guild_id": guild_id}, {"$pull": {key: value}})
