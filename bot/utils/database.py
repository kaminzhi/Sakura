# bot/utils/database.py
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
        "threads.net": {"replacement": "fixthreads.net", "label": "Thread"},
        "threads.com": {"replacement": "fixthreads.net", "label": "Thread"},
        "mastodon.social": {"replacement": "fxmastodon.net", "label": "Mastodon"},
        "deviantart.com": {"replacement": "fixdeviantart.com", "label": "DeviantArt"},
        "tiktok.com": {"replacement": "fixtiktok.com", "label": "Tiktok"},
        "twitch.tv": {"replacement": "fxtwitch.com", "label": "Twitch"},
    },
    "custom_banner_url": None,
    "generate_gif_profile_image": True,
    "welcome_channel_id": None,
    "welcome_message_template": "歡迎 {member} 加入 {guild}！",
    "welcome_image_enabled": True,
    "welcome_generate_gif": True,
    "welcome_custom_banner_url": None,
    "leave_channel_id": None,
    "leave_message_template": "{member} 已離開 {guild}！",
    "leave_image_enabled": True,
    "leave_generate_gif": True,
    "leave_custom_banner_url": None,
    "welcome_initial_role_id": None,
    "selectable_roles": [],  # 新增：可選身份組列表
    "role_selection_channel_id": None,  # 新增：身份組選擇功能激活的頻道
}


async def get_guild_data(guild_id: int) -> dict:
    doc = await config_collection.find_one({"guild_id": guild_id})
    if not doc:
        new_doc = {"guild_id": guild_id, **DEFAULT_CONFIG}
        await config_collection.insert_one(new_doc)
        return new_doc

    updated = False
    for key, val in DEFAULT_CONFIG.items():
        if key not in doc:
            doc[key] = val
            updated = True
        elif isinstance(val, dict) and isinstance(doc.get(key), dict):
            for subkey, subval in val.items():
                if subkey not in doc[key]:
                    doc[key][subkey] = subval
                    updated = True

    if "custom_avatar_url" in doc:
        await config_collection.update_one(
            {"guild_id": guild_id}, {"$unset": {"custom_avatar_url": ""}}
        )
        del doc["custom_avatar_url"]
        updated = True

    if updated:
        await config_collection.update_one({"guild_id": guild_id}, {"$set": doc})
    return doc


async def update_guild_data(guild_id: int, data: dict):
    if "custom_avatar_url" in data:
        print(
            f"Debug: Removing 'custom_avatar_url' from update data for guild {guild_id}."
        )
        del data["custom_avatar_url"]
    await config_collection.update_one(
        {"guild_id": guild_id}, {"$set": data}, upsert=True
    )
