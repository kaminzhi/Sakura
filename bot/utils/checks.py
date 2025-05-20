import os
import discord
from discord import app_commands
from dotenv import load_dotenv
from .database import db

load_dotenv()
BOT_OWNER_IDS = [
    int(owner_id)
    for owner_id in os.getenv("BOT_OWNER_IDS", "").split(",")
    if owner_id.strip()
]
config_collection = db["guilds"]


def is_guild_admin():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.manage_guild

    return app_commands.check(predicate)


def is_bot_manager():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True

        doc = await config_collection.find_one({"guild_id": interaction.guild.id})
        role_id = doc.get("bot_manager_role") if doc else None
        if role_id:
            role = interaction.guild.get_role(int(role_id))
            return role in interaction.user.roles

        return False

    return app_commands.check(predicate)


def is_bot_owner():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.id in BOT_OWNER_IDS

    return app_commands.check(predicate)
