# bot/cogs/devpanel.py
import os
import discord
from discord import app_commands, Interaction
from discord.ext import commands
from datetime import datetime
import logging
from bot.utils.database import (
    is_server_banned,
)
from bot.views.dev_panel_views import DevPanelView

BOT_OWNER_IDS = int(os.getenv("BOT_OWNER_IDS"))

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class DevPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="panel-dev", description="僅限機器人擁有者可見的開發者控制面板"
    )
    async def devpanel(self, interaction: discord.Interaction):
        if interaction.user.id != BOT_OWNER_IDS:
            return await interaction.response.send_message(
                "僅限機器人擁有者可使用此指令。", ephemeral=True
            )

        view = DevPanelView(self.bot)
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"Bot joined guild: {guild.name} (ID: {guild.id})")
        if await is_server_banned(guild.id):
            logger.warning(
                f"Joined banned guild: {guild.name} (ID: {guild.id}). Leaving now."
            )
            try:
                await guild.leave()
                logger.info(
                    f"Successfully left banned guild: {guild.name} (ID: {guild.id})"
                )
            except discord.Forbidden:
                logger.error(
                    f"Failed to leave banned guild {guild.name} (ID: {guild.id}): Missing permissions."
                )
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred while leaving guild {guild.name} (ID: {guild.id}): {e}"
                )

            owner = self.bot.get_user(BOT_OWNER_IDS)
            if owner:
                try:
                    await owner.send(
                        f"警告: 機器人嘗試加入已封禁的伺服器 **{guild.name}** (ID: `{guild.id}`). 已自動離開。"
                    )
                except discord.Forbidden:
                    logger.warning(
                        f"Could not send message to bot owner {BOT_OWNER_IDS} about banned guild join."
                    )


async def setup(bot):
    await bot.add_cog(DevPanel(bot))
