# bot/cogs/user_profile.py
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import io
import warnings
import aiohttp
import logging

from bot.utils.database import get_guild_data
from bot.utils.image_processing import ImageProcessor

warnings.filterwarnings("ignore", category=UserWarning, module="imageio.plugins.pillow")


class UserProfile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.image_processor = ImageProcessor()
        if not hasattr(self.bot, "session") or not isinstance(
            self.bot.session, aiohttp.ClientSession
        ):
            self.bot.session = aiohttp.ClientSession()
            print("Debug: Initialized bot.session within UserProfile cog.")

    async def cog_unload(self):
        if (
            hasattr(self.bot, "session")
            and self.bot.session
            and self.bot.session._owner
        ):
            await self.bot.session.close()

    async def download_image(self, url: str) -> io.BytesIO | None:
        if not url:
            return None
        try:
            async with self.bot.session.get(url) as response:
                response.raise_for_status()
                image_bytes = await response.read()
                return io.BytesIO(image_bytes)
        except aiohttp.ClientError as e:
            logging.error(f"Error downloading image from {url}: {e}")
            return None

    @app_commands.command(name="user-profile", description="查詢用戶資訊")
    async def user_profile(
        self, interaction: discord.Interaction, member: discord.Member = None
    ):
        await interaction.response.defer()
        original_member = member or interaction.user
        guild = interaction.guild
        member_to_use = original_member

        if guild:
            try:
                full_member = await guild.fetch_member(original_member.id)
                member_to_use = full_member
            except (discord.NotFound, discord.HTTPException):
                try:
                    full_member = await self.bot.fetch_user(original_member.id)
                    member_to_use = full_member
                except (discord.NotFound, discord.HTTPException) as e:
                    logging.error(
                        f"Debug: Failed to fetch user {original_member.id}: {e}"
                    )

        guild_data = await get_guild_data(interaction.guild_id)
        custom_banner_url = guild_data.get("custom_banner_url")
        generate_gif_enabled = guild_data.get("generate_gif_profile_image", True)

        avatar_url = member_to_use.display_avatar.url
        user = await self.bot.fetch_user(member_to_use.id)
        banner_to_download_url = (
            user.banner.url if user.banner else (custom_banner_url or avatar_url)
        )

        avatar_data = await self.download_image(avatar_url)
        banner_data = await self.download_image(banner_to_download_url)

        created_at_str = (
            member_to_use.created_at.strftime("%Y/%m/%d %H:%M")
            if member_to_use.created_at
            else "未知日期"
        )

        processed_image_buffer = await asyncio.to_thread(
            self.image_processor.process_image_sync,
            banner_data,
            avatar_data,
            member_to_use.display_name,
            member_to_use.name,
            member_to_use.discriminator,
            created_at_str,
            generate_gif_enabled,
        )

        file = None
        if processed_image_buffer:
            is_gif = processed_image_buffer.getvalue()[:4] == b"GIF8"
            filename = "user_profile.gif" if is_gif else "user_profile.png"
            file = discord.File(processed_image_buffer, filename=filename)
            logging.info(f"Debug: Output file prepared: {filename}")
        else:
            logging.error(
                "Debug: processed_image_buffer is None. File will not be attached."
            )

        embed = discord.Embed(
            title=f"**{member_to_use.display_name}** 的個人資訊",
            color=discord.Color.from_rgb(245, 140, 175),
            timestamp=datetime.utcnow(),
        )
        author_name = (
            member_to_use.name
            if member_to_use.discriminator == "0"
            else f"{member_to_use.name}#{member_to_use.discriminator}"
        )
        embed.set_author(
            name=f"查詢者：{interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )

        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        if file:
            embed.set_image(url=f"attachment://{file.filename}")
        else:
            embed.add_field(
                name="⚠️ **無法生成個人橫幅**",
                value="請確保用戶有設定橫幅，或伺服器有設定自定義橫幅。若無，將使用頭像作為替代橫幅。",
                inline=False,
            )

        embed.add_field(
            name="🔗 **帳號 ID**", value=f"`{member_to_use.id}`", inline=True
        )
        user_type = "🤖 機器人" if member_to_use.bot else "👤 使用者"
        embed.add_field(name="✨ **此帳號的類型**", value=user_type, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="📅 **加入Discord於**", value=created_at_str, inline=True)
        if isinstance(member_to_use, discord.Member) and guild:
            joined_at = (
                member_to_use.joined_at.strftime("%Y/%m/%d %H:%M")
                if member_to_use.joined_at
                else "未知"
            )
            embed.add_field(
                name=f"📥 **加入`{guild.name}`於**", value=joined_at, inline=True
            )
            embed.add_field(name="\u200b", value="\u200b", inline=True)
        else:
            embed.add_field(
                name="📥 **加入伺服器於**",
                value="`該用戶目前不在本伺服器`",
                inline=True,
            )
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        if isinstance(member_to_use, discord.Member):
            boosting_status = (
                "💎 正在加成" if member_to_use.premium_since else "❌ 向未加成"
            )
            embed.add_field(
                name="🚀 **加成此伺服器**", value=boosting_status, inline=True
            )
            roles = [
                role.mention for role in member_to_use.roles if role.name != "@everyone"
            ]
            roles_str = ", ".join(roles) if roles else "無任何身分組"
            embed.add_field(name="🎭 **擁有的身分組**", value=roles_str, inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
        else:
            embed.add_field(
                name="🚀 **伺服器加成**",
                value="`無法獲取 (用戶不在伺服器)`",
                inline=True,
            )
            embed.add_field(
                name="🎭 **擁有的身分組**",
                value="`無法獲取 (用戶不在伺服器)`",
                inline=True,
            )
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.set_footer(
            text=f"由 {self.bot.user.name} 提供服務",
            icon_url=self.bot.user.display_avatar.url,
        )

        if file:
            await interaction.followup.send(embed=embed, file=file)
            print("Debug: Sent embed with file.")
        else:
            await interaction.followup.send(embed=embed)
            print("Debug: Sent embed without file (due to error).")


async def setup(bot: commands.Bot):
    await bot.add_cog(UserProfile(bot))
