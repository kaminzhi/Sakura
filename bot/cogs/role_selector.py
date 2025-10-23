# bot/cogs/role_selector.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
from bot.utils.database import get_guild_data, update_guild_data
from bot.views.role_selector_view import RoleSelectorView

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class RoleSelector(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register persistent view with valid components
        placeholder_guild = bot.get_guild(0) or discord.Object(
            id=0
        )  # Fallback if no guilds available
        view = RoleSelectorView({}, placeholder_guild)
        self.bot.add_view(view)

    @app_commands.command(name="rolepanel", description="發送身份組選擇面板")
    @app_commands.default_permissions(manage_roles=True)
    async def role_panel(self, interaction: discord.Interaction):
        guild_data = await get_guild_data(interaction.guild_id)
        role_selection_channel_id = guild_data.get("role_selection_channel_id")
        logger.debug(
            f"Role panel requested: channel_id={interaction.channel_id}, expected={role_selection_channel_id}"
        )
        if not role_selection_channel_id:
            await interaction.response.send_message(
                "請先在設定面板中設定身份組選擇頻道！", ephemeral=True
            )
            return
        if interaction.channel_id != role_selection_channel_id:
            channel = interaction.guild.get_channel(role_selection_channel_id)
            await interaction.response.send_message(
                f"身份組選擇面板只能在 {channel.mention} 中發送！", ephemeral=True
            )
            return

        # Clean up old panels in the channel
        channel = interaction.guild.get_channel(role_selection_channel_id)
        if (
            channel
            and channel.permissions_for(interaction.guild.me).read_message_history
        ):
            async for message in channel.history(limit=100):
                if (
                    message.author == self.bot.user
                    and message.embeds
                    and message.embeds[0].title == "🎭 選擇你的身份組"
                ):
                    try:
                        await message.delete()
                        logger.debug(f"Deleted old role panel message: {message.id}")
                    except discord.Forbidden:
                        logger.warning(
                            "Failed to delete old panel: missing permissions"
                        )
                    except discord.HTTPException as e:
                        logger.error(f"Failed to delete old panel: {e}")

        embed = discord.Embed(
            title="🎭 選擇你的身份組",
            description="點擊下方按鈕以選擇或更改你的身份組。",
            color=discord.Color.purple(),
        )
        view = RoleSelectorView(guild_data, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"Sent new role panel in channel {role_selection_channel_id}")

    @app_commands.command(
        name="refresh_rolepanel", description="更新現有的身份組選擇面板"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def refresh_role_panel(self, interaction: discord.Interaction):
        guild_data = await get_guild_data(interaction.guild_id)
        role_selection_channel_id = guild_data.get("role_selection_channel_id")
        logger.debug(
            f"Refresh role panel requested: channel_id={interaction.channel_id}, expected={role_selection_channel_id}"
        )
        if not role_selection_channel_id:
            await interaction.response.send_message(
                "請先在設定面板中設定身份組選擇頻道！", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(role_selection_channel_id)
        if not channel:
            await interaction.response.send_message(
                "設定的頻道無效！請重新設定身份組選擇頻道。", ephemeral=True
            )
            return

        # Find and update existing panel
        updated = False
        if channel.permissions_for(interaction.guild.me).read_message_history:
            async for message in channel.history(limit=100):
                if (
                    message.author == self.bot.user
                    and message.embeds
                    and message.embeds[0].title == "🎭 選擇你的身份組"
                ):
                    try:
                        embed = discord.Embed(
                            title="🎭 選擇你的身份組",
                            description="點擊下方按鈕以選擇或更改你的身份組。",
                            color=discord.Color.purple(),
                        )
                        view = RoleSelectorView(guild_data, interaction.guild)
                        await message.edit(embed=embed, view=view)
                        logger.debug(
                            f"Updated existing role panel message: {message.id}"
                        )
                        updated = True
                        break
                    except discord.Forbidden:
                        logger.warning("Failed to edit panel: missing permissions")
                    except discord.HTTPException as e:
                        logger.error(f"Failed to edit panel: {e}")

        if not updated:
            # If no panel found or update failed, send a new one
            embed = discord.Embed(
                title="🎭 選擇你的身份組",
                description="點擊下方按鈕以選擇或更改你的身份組。",
                color=discord.Color.purple(),
            )
            view = RoleSelectorView(guild_data, interaction.guild)
            await channel.send(embed=embed, view=view)
            logger.info(
                f"Sent new role panel for refresh in channel {role_selection_channel_id}"
            )

        await interaction.response.send_message(
            "身份組選擇面板已更新！", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleSelector(bot))
