# bot/cogs/announcement_panel.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import List, Optional
import os
from dotenv import load_dotenv

from bot.views.announcement_views import AnnouncementView, GlobalAnnouncementView

load_dotenv()
BOT_OWNER_IDS = os.getenv("BOT_OWNER_IDS", "").split(",")
BOT_OWNER_IDS = [int(id.strip()) for id in BOT_OWNER_IDS if id.strip().isdigit()]

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class AnnouncementManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot_owner_ids = BOT_OWNER_IDS 

    @app_commands.command(name="announce", description="創建並發送伺服器公告")
    @app_commands.default_permissions(manage_guild=True)
    async def announce(self, interaction: discord.Interaction):
        if self.bot.user is None:
            logger.error("Bot user is None")
            await interaction.response.send_message(
                "Bot is not properly initialized.", ephemeral=True
            )
            return
        if not interaction.guild:
            await interaction.response.send_message(
                "此命令只能在伺服器中使用。", ephemeral=True
            )
            return
        view = AnnouncementView(
            original_interaction=interaction,
            bot_user=self.bot.user,
            guild=interaction.guild,
        )
        embed = discord.Embed(
            title="公告面板",
            description="選擇頻道並創建公告。使用「預覽」查看效果，然後決定是否發送。",
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text=f"由 {self.bot.user.display_name} 提供服務",
            icon_url=self.bot.user.display_avatar.url,
        )
        logger.debug(
            f"Sending initial announce response, interaction_id: {interaction.id}"
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(
        name="announce-dev", description="給Bot Owner發送全局公告至所有伺服器的公告頻道"
    )
    async def global_announce(self, interaction: discord.Interaction):
        if self.bot.user is None:
            logger.error("Bot user is None")
            await interaction.response.send_message(
                "Bot is not properly initialized.", ephemeral=True
            )
            return
        logger.debug(
            f"Global announce attempted by user_id: {interaction.user.id}, bot_owner_ids: {self.bot_owner_ids}"
        )
        if interaction.user.id not in self.bot_owner_ids:
            logger.warning(
                f"Unauthorized global-announce attempt by user_id: {interaction.user.id}"
            )
            await interaction.response.send_message(
                "僅限Bot擁有者使用此命令。", ephemeral=True
            )
            return
        view = GlobalAnnouncementView(
            original_interaction=interaction,
            bot_user=self.bot.user,
            bot=self.bot,
        )
        embed = discord.Embed(
            title="全局公告面板",
            description="創建將發送至所有伺服器公告頻道的公告。使用「預覽」查看效果，然後決定是否發送。",
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text=f"由 {self.bot.user.display_name} 提供服務",
            icon_url=self.bot.user.display_avatar.url,
        )
        logger.debug(
            f"Sending initial global-announce response, interaction_id: {interaction.id}"
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AnnouncementManager(bot))