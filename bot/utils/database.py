import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
mongo_client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
config_collection = mongo_client[MONGO_DB_NAME]["guild_configs"]

DEFAULT_CONFIG = {
    "auto_link_fix": True,
    "preserve_original_link": True,
    "allowed_channels": [],
    "allow_channels": [],
    "allowed_roles": [],
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
    "platform_replacements": {
        "twitter.com": {"replacement": "fxtwitter.com", "label": "Twitter/X"},
        "x.com": {"replacement": "fixupx.com", "label": "Twitter/X"},
        "bsky.app": {"replacement": "fxbsky.app", "label": "Bluesky"},
        "instagram.com": {"replacement": "ddinstagram.com", "label": "Instagram"},
        "youtube.com": {"replacement": "koutube.com", "label": "Youtube"},
        "youtu.be": {"replacement": "koutube.com", "label": "Youtube"},
        "reddit.com": {"replacement": "rxddit.com", "label": "Reddit"},
        "pixiv.net": {"replacement": "phixiv.net", "label": "Pixiv"},
        "open.spotify.com": {
            "replacement": "open.fxspotify.com",
            "label": "Spotify",
            "path_prefix": "/track",
        },
        "bilibili.com": {"replacement": "vxbilibili.com", "label": "Bilibili"},
        "threads.net": {"replacement": "fixthread.com", "label": "Thread"},
        "mastodon.social": {"replacement": "fxmastodon.net", "label": "Mastodon"},
        "deviantart.com": {"replacement": "fixdeviantart.com", "label": "DeviantArt"},
        "tiktok.com": {"replacement": "fixtiktok.com", "label": "Tiktok"},
        "twitch.tv": {"replacement": "fxtwitch.com", "label": "Twitch"},
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
