import discord
from discord import app_commands
from discord.ext import commands
from ..views.linkfix_settings_view import LinkFixSettingsView
from ..utils.database import get_guild_data


class LinkFixSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="linkfix-settings", description="設定自動連結修正功能")
    async def linkfix_settings(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        #        config = await get_guild_data(interaction.guild.id)
        view = LinkFixSettingsView(guild_id=interaction.guild.id)
        embed = await view.build_embed()
        view.add_platform_select()

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(LinkFixSettings(bot))
