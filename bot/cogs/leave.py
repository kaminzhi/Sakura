# bot/cogs/leave.py
import discord
from discord.ext import commands
import aiohttp
import io
import logging
from datetime import datetime
import asyncio

from bot.utils.database import get_guild_data
from bot.utils.image_processing import ImageProcessor


class Leave(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.image_processor = ImageProcessor()
        if not hasattr(self.bot, "session") or not isinstance(
            self.bot.session, aiohttp.ClientSession
        ):
            self.bot.session = aiohttp.ClientSession()
            print("Debug: Initialized bot.session within Leave cog.")

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

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild_data = await get_guild_data(member.guild.id)
        leave_channel_id = guild_data.get("leave_channel_id")
        leave_message_template = guild_data.get(
            "leave_message_template", "{member} 已離開 {guild}！"
        )
        leave_image_enabled = guild_data.get("leave_image_enabled", True)
        leave_generate_gif = guild_data.get("leave_generate_gif", True)
        leave_custom_banner_url = guild_data.get("leave_custom_banner_url")

        # Skip leave message if channel is disabled (None)
        if leave_channel_id is None:
            logging.info(f"Leave messages disabled for guild {member.guild.id}")
            return

        channel = member.guild.get_channel(leave_channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            logging.error(f"Leave channel {leave_channel_id} not found or invalid.")
            return

        avatar_url = member.display_avatar.url
        user = await self.bot.fetch_user(member.id)
        banner_to_download_url = (
            user.banner.url if user.banner else (leave_custom_banner_url or avatar_url)
        )

        file = None
        if leave_image_enabled:
            avatar_data = await self.download_image(avatar_url)
            banner_data = await self.download_image(banner_to_download_url)
            created_at_str = (
                member.created_at.strftime("%Y/%m/%d %H:%M")
                if member.created_at
                else "未知日期"
            )

            processed_image_buffer = await asyncio.to_thread(
                self.image_processor.process_image_sync,
                banner_data,
                avatar_data,
                member.display_name,
                member.name,
                member.discriminator,
                created_at_str,
                leave_generate_gif,
            )

            if processed_image_buffer:
                is_gif = processed_image_buffer.getvalue()[:4] == b"GIF8"
                filename = "leave_profile.gif" if is_gif else "leave_profile.png"
                file = discord.File(processed_image_buffer, filename=filename)
                logging.info(f"Debug: Leave file prepared: {filename}")
            else:
                logging.error(
                    "Debug: processed_image_buffer is None for leave message."
                )

        leave_message = leave_message_template.format(
            member=member.display_name, guild=member.guild.name
        )
        embed = discord.Embed(
            title=leave_message,
            color=discord.Color.red(),
            timestamp=datetime.utcnow(),
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)

        if file:
            embed.set_image(url=f"attachment://{file.filename}")
        elif leave_image_enabled:
            embed.add_field(
                name="⚠️ **無法生成離開橫幅**",
                value="請確保用戶有設定橫幅，或伺服器有設定自定義離開橫幅。若無，將使用頭像作為替代橫幅。",
                inline=False,
            )

        embed.add_field(
            name="📅 **帳號創建於**",
            value=member.created_at.strftime("%Y/%m/%d %H:%M")
            if member.created_at
            else "未知日期",
            inline=True,
        )
        embed.add_field(
            name="📤 **離開伺服器於**",
            value=datetime.utcnow().strftime("%Y/%m/%d %H:%M"),
            inline=True,
        )
        embed.set_footer(
            text=f"由 {self.bot.user.name} 提供服務",
            icon_url=self.bot.user.display_avatar.url,
        )

        try:
            if file:
                await channel.send(embed=embed, file=file)
            else:
                await channel.send(embed=embed)
            logging.info(
                f"Sent leave message for {member.display_name} in {member.guild.name}"
            )
        except discord.Forbidden:
            logging.error(
                f"Bot lacks permission to send messages in leave channel {leave_channel_id}."
            )
        except Exception as e:
            logging.error(f"Error sending leave message: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Leave(bot))
