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
    "allow_channels": [],  # Note: You have both "allowed_channels" and "allow_channels". Double-check if this is intentional.
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
    "generate_gif_profile_image": True,  # This is the key we're working with
}


async def get_guild_data(guild_id: int) -> dict:
    doc = await config_collection.find_one({"guild_id": guild_id})
    if not doc:
        # If no document exists, insert a new one with all default fields
        new_doc = {"guild_id": guild_id, **DEFAULT_CONFIG}
        await config_collection.insert_one(new_doc)
        return new_doc

    updated = False
    # Iterate through DEFAULT_CONFIG to add missing keys to existing documents
    for key, val in DEFAULT_CONFIG.items():
        if key not in doc:
            doc[key] = val
            updated = True
        # Special handling for nested dictionaries
        elif isinstance(val, dict) and isinstance(doc.get(key), dict):
            for subkey, subval in val.items():
                if subkey not in doc[key]:
                    doc[key][subkey] = subval
                    updated = True

    # IMPORTANT: Handle old data cleanup for 'custom_avatar_url'
    # If old documents still have 'custom_avatar_url', remove it
    if "custom_avatar_url" in doc:
        # Use $unset to remove the field from MongoDB
        await config_collection.update_one(
            {"guild_id": guild_id}, {"$unset": {"custom_avatar_url": ""}}
        )
        del doc["custom_avatar_url"]  # Also remove from the Python dict
        updated = True

    if updated:
        # Use $set to update only the modified fields, rather than overwriting the whole doc
        # This will also save any new fields added from DEFAULT_CONFIG
        await config_collection.update_one({"guild_id": guild_id}, {"$set": doc})
    return doc


async def update_guild_data(guild_id: int, data: dict):
    # IMPORTANT: Ensure 'custom_avatar_url' is not passed to the update
    if "custom_avatar_url" in data:
        print(
            f"Debug: Removing 'custom_avatar_url' from update data for guild {guild_id}."
        )
        del data["custom_avatar_url"]

    await config_collection.update_one(
        {"guild_id": guild_id}, {"$set": data}, upsert=True
    )
