# bot/cogs/settings_panel.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import datetime, timezone

from bot.utils.database import get_guild_data
from bot.views.settings_views import SettingsView

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SettingsManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="panel",
        description="管理伺服器設定，包括歡迎訊息、離開訊息、用戶檔案、身份組選擇、封禁管理和動態語音頻道",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def set_server_settings(self, interaction: discord.Interaction):
        if self.bot.user is None:
            logger.error("Bot user is None")
            await interaction.response.send_message(
                "Bot is not properly initialized.", ephemeral=True
            )
            return
        current_guild_data = await get_guild_data(interaction.guild_id)
        view = SettingsView(original_interaction=interaction, bot_user=self.bot.user)
        embed, view = view._create_current_page(current_guild_data, self.bot.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsManager(bot))