# bot/cogs/roulette.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
from bot.views.roulette_views import RouletteSetupModal

logger = logging.getLogger("roulette_cog")
logger.setLevel(logging.DEBUG)


class RouletteCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="roulette",
        description="創建一個隨機抽籤輪盤活動",
    )
    async def create_roulette(self, interaction: discord.Interaction):
        # The bot.user is available via interaction.client.user for modals
        await interaction.response.send_modal(
            RouletteSetupModal(interaction.client.user)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RouletteCog(bot))
