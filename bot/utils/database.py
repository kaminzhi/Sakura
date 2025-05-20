import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
mongo_client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
config_collection = mongo_client[MONGO_DB_NAME]["guild_configs"]


DEFAULT_CONFIG = {
    "auto_link_fix": True,
    "platforms": {
        "Twitter/X": True,
        "Bluesky": True,
        "Instagram": True,
        "Youtube": True,
        "Reddit": True,
        "Pixiv": True,
        "Spotify": True,
        "Bilibili": True,
        "Thread": True,
        "Mastodon": True,
        "DeviantArt": True,
        "Tiktok": True,
        "Twitch": True,
    },
    "preserve_original_link": True,
    "platform_replacements": {
        "twitter.com": ["fxtwitter.com", "Twitter/X"],
        "x.com": ["fixupx.com", "Twitter/X"],
        "bsky.app": ["fxbsky.app", "Bluesky"],
        "instagram.com": ["ddinstagram.com", "Instagram"],
        "youtube.com": ["koutube.com", "Youtube"],
        "youtu.be": ["koutube.com", "Youtube"],
        "reddit.com": ["rxddit.com", "Reddit"],
        "pixiv.net": ["phixiv.net", "Pixiv"],
        "spotify.com": ["fxspotify.com", "Spotify"],
        "bilibili.com": ["vxbilibili.com", "Bilibili"],
        "threads.net": ["fixthread.com", "Thread"],
        "mastodon.social": ["fxmastodon.net", "Mastodon"],
        "deviantart.com": ["fixdeviantart.com", "DeviantArt"],
        "tiktok.com": ["fixtiktok.com", "Tiktok"],
        "twitch.tv": ["fxtwitch.com", "Twitch"],
    },
}


async def get_guild_data(guild_id: int) -> dict:
    doc = await config_collection.find_one({"guild_id": guild_id})
    if not doc:
        await config_collection.insert_one({"guild_id": guild_id, **DEFAULT_CONFIG})
        return {"guild_id": guild_id, **DEFAULT_CONFIG}

    updated = False
    for key, val in DEFAULT_CONFIG.items():
        if key not in doc:
            doc[key] = val
            updated = True
        elif isinstance(val, dict):
            for subkey, subval in val.items():
                if subkey not in doc[key]:
                    doc[key][subkey] = subval
                    updated = True

    if updated:
        await config_collection.update_one({"guild_id": guild_id}, {"$set": doc})
    return doc


async def update_guild_data(guild_id: int, data: dict):
    await config_collection.update_one(
        {"guild_id": guild_id}, {"$set": data}, upsert=True
    )
