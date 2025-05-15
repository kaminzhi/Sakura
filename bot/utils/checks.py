from discord.ext import commands
from discord import app_commands
from .redis_manager import get_redis_client

redis_client = get_redis_client()


def is_guild_admin():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.manage_guild

    return app_commands.check(predicate)


def is_bot_manager():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        role_id = redis_client.get(f"server:{interaction.guild_id}:bot_manager_role")
        if role_id:
            role = interaction.guild.get_role(int(role_id))
            return role in interaction.user.roles
        return False

    return app_commands.check(predicate)


def is_bot_owner():
    async def predicate(interaction: discord.Interaction):
        import os
        from dotenv import load_dotenv

        load_dotenv()
        BOT_OWNER_IDS = [
            int(owner_id) for owner_id in os.getenv("BOT_OWNER_IDS", "").split(",")
        ]
        return interaction.user.id in BOT_OWNER_IDS

    return app_commands.check(predicate)
