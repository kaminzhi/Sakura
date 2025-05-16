import discord
from discord.ext import commands
from discord import app_commands
import re
from ..utils import redis_manager
from ..utils import checks

redis_client = redis_manager.get_redis_client()


class LinkFixerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_auto_fix_enabled(self, guild_id: int) -> bool:
        """檢查伺服器的自動連結修正是否啟用。"""
        return redis_client.get(f"server:{guild_id}:auto_link_fix") == "True"

    async def set_auto_fix_enabled(self, guild_id: int, enabled: bool):
        """設定伺服器的自動連結修正狀態。"""
        redis_client.set(
            f"server:{guild_id}:auto_link_fix", "True" if enabled else "False"
        )

    @app_commands.command(
        name="toggle_autofix", description="切換自動轉換 Twitter/X/Bluesky 連結功能"
    )
    @checks.is_guild_admin()
    async def toggle_autofix_command(
        self, interaction: discord.Interaction, enable: bool
    ):
        """切換伺服器的自動連結修正功能。"""
        await self.set_auto_fix_enabled(interaction.guild_id, enable)
        status = "啟用" if enable else "禁用"
        await interaction.response.send_message(
            f"✅ 自動連結修正功能已{status}。", ephemeral=True
        )

    @app_commands.command(
        name="link_fixer",
        description="手動將指定的 Twitter/X/Bluesky 連結轉換為嵌入格式",
    )
    async def link_fixer_command(self, interaction: discord.Interaction, url: str):
        if re.search(r"(twitter\.com|x\.com)", url):
            fixed_url = url.replace("twitter.com", "fxtwitter.com").replace(
                "x.com", "fixupx.com"
            )
        elif re.search(r"blueskyweb\.xyz", url):
            fixed_url = url.replace("blueskyweb.xyz", "fxbluesky.com")
        else:
            await interaction.response.send_message(
                "❌ 這個連結不是 Twitter/X 或 Bluesky 的連結。", ephemeral=True
            )
            return
        await interaction.response.send_message(fixed_url)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if not message.guild:
            return  # 忽略私訊

        if await self.is_auto_fix_enabled(message.guild.id):
            content = message.content
            urls = re.findall(
                r"(https?://(?:www\.)?(?:twitter\.com|x\.com)/[^\s]+)|(https?://(?:www\.)?blueskyweb\.xyz/profile/[^\s]+)",
                content,
            )
            if not urls:
                return

            fixed_content = content
            for url_tuple in urls:
                url = url_tuple[0] or url_tuple[1]
                if re.search(r"(twitter\.com|x\.com)", url):
                    fixed_url = url.replace("twitter.com", "fxtwitter.com").replace(
                        "x.com", "fixupx.com"
                    )
                    fixed_content = fixed_content.replace(url, fixed_url)
                elif re.search(r"blueskyweb\.xyz", url):
                    fixed_url = url.replace("blueskyweb.xyz", "fxbluesky.com")
                    fixed_content = fixed_content.replace(url, fixed_url)

            if fixed_content != content:
                webhook = None
                for wh in await message.channel.webhooks():
                    if wh.name == "AutoLinkFixer":
                        webhook = wh
                        break

                if webhook is None:
                    webhook = await message.channel.create_webhook(name="AutoLinkFixer")

                try:
                    await webhook.send(
                        content=fixed_content,
                        username=message.author.display_name,
                        avatar_url=message.author.avatar.url,
                    )
                    await message.delete()
                except discord.Forbidden:
                    await message.channel.send(
                        f"⚠️ 無法自動修正連結，Bot 需要管理訊息的權限才能刪除原始訊息。",
                        delete_after=5,
                    )
                except Exception as e:
                    logging.error(f"自動修正連結時發生錯誤：{e}")


async def setup(bot):
    await bot.add_cog(LinkFixerCog(bot))
