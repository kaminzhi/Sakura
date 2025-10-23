import discord
from discord import app_commands
from discord.ext import commands
import logging
from bot.utils.database import get_guild_data
from bot.views.ban_views import BanSystemView

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class BanSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        placeholder_guild = discord.Object(id=0)
        view = BanSystemView({}, placeholder_guild)
        self.bot.add_view(view)

    @app_commands.command(name="ban_panel", description="發送封禁管理面板")
    @app_commands.default_permissions(manage_guild=True)
    async def ban_panel(self, interaction: discord.Interaction):
        guild_data = await get_guild_data(interaction.guild_id)
        ban_channel_id = guild_data.get("ban_channel_id")
        if not ban_channel_id:
            await interaction.response.send_message(
                "請先在設定面板中設定封禁管理頻道！", ephemeral=True
            )
            return
        if interaction.channel_id != ban_channel_id:
            channel = interaction.guild.get_channel(ban_channel_id)
            await interaction.response.send_message(
                f"封禁管理面板只能在 {channel.mention} 中發送！", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(ban_channel_id)
        if (
            channel
            and channel.permissions_for(interaction.guild.me).read_message_history
        ):
            async for message in channel.history(limit=100):
                if (
                    message.author == self.bot.user
                    and message.embeds
                    and message.embeds[0].title == "封禁管理面板"
                ):
                    try:
                        await message.delete()
                        logger.debug(f"Deleted old ban panel: message_id={message.id}")
                    except discord.Forbidden:
                        logger.error("Missing permissions to delete old ban panel")
                    except discord.HTTPException as e:
                        logger.error(f"Failed to delete old ban panel: {e}")

        embed = discord.Embed(
            title="封禁管理面板",
            description=(
                "使用以下按鈕管理封禁：\n"
                "- **選擇成員**: 管理員專用，選擇並封禁伺服器內成員\n"
                "- **取消**: 取消操作\n"
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(
            text=f"由 {self.bot.user.display_name} 提供服務",
            icon_url=self.bot.user.display_avatar.url,
        )
        view = BanSystemView(guild_data, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="refresh_ban_panel", description="重新整理封禁管理面板")
    @app_commands.default_permissions(manage_guild=True)
    async def refresh_ban_panel(self, interaction: discord.Interaction):
        guild_data = await get_guild_data(interaction.guild_id)
        ban_channel_id = guild_data.get("ban_channel_id")
        logger.debug(
            f"Refresh ban panel requested: channel_id={interaction.channel_id}, expected={ban_channel_id}"
        )
        if not ban_channel_id:
            await interaction.response.send_message(
                "請先在設定面板中設定封禁管理頻道！", ephemeral=True
            )
            return
        if interaction.channel_id != ban_channel_id:
            channel = interaction.guild.get_channel(ban_channel_id)
            await interaction.response.send_message(
                f"封禁管理面板只能在 {channel.mention} 中重新整理！", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(ban_channel_id)
        if (
            channel
            and channel.permissions_for(interaction.guild.me).read_message_history
        ):
            async for message in channel.history(limit=100):
                if (
                    message.author == self.bot.user
                    and message.embeds
                    and message.embeds[0].title == "封禁管理面板"
                ):
                    try:
                        await message.delete()
                    except discord.Forbidden:
                        logger.error("Missing permissions to delete old ban panel")
                    except discord.HTTPException as e:
                        logger.error(f"Failed to delete old ban panel: {e}")

        embed = discord.Embed(
            title="封禁管理面板",
            description=(
                "使用以下按鈕管理封禁：\n"
                "- **選擇成員**: 管理員專用，選擇並封禁伺服器內成員\n"
                "- **取消**: 取消操作\n"
                "\n*伺服器封禁請使用 `/devpanel` 指令*"
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(
            text=f"由 {self.bot.user.display_name} 提供服務",
            icon_url=self.bot.user.display_avatar.url,
        )
        view = BanSystemView(guild_data, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(BanSystem(bot))
