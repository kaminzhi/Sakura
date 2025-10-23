import discord
from discord import app_commands
from discord.ext import commands
import logging
from bot.views.poll_views import PollCreationModal

logging.basicConfig(level=discord.utils.MISSING)
logger = logging.getLogger(__name__)

class PollCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="poll",
        description="創建一個投票，最多8個選項，持續時間1到24小時",
    )
    async def create_poll(self, interaction: discord.Interaction):
        if self.bot.user is None:
            logger.error("Bot user is None")
            await interaction.response.send_message(
                "Bot 未正確初始化。", ephemeral=True
            )
            return
        await interaction.response.send_modal(PollCreationModal(self.bot.user))

async def setup(bot: commands.Bot):
    await bot.add_cog(PollCog(bot))
