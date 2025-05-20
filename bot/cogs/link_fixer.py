from discord.ext import commands
import discord
import re
from urllib.parse import urlparse
from ..utils.database import get_guild_data


class LinkFixer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        config = await get_guild_data(guild_id)

        if not config.get("auto_link_fix", False):
            return

        allowed_channels = config.get("allowed_channels", [])
        if allowed_channels and str(message.channel.id) not in allowed_channels:
            return

        platforms_config = config.get("platforms", {})
        platform_replacements = config.get("platform_replacements", {})
        preserve = config.get("preserve_original_link", False)

        url_pattern = re.compile(r"https?://[^\s]+")
        matches = url_pattern.findall(message.content)

        if not matches:
            return

        fixed_content = message.content

        for url in matches:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")

            if domain in platform_replacements:
                replacement_domain, platform_label = platform_replacements[domain]
                if platforms_config.get(platform_label, False):
                    fixed_url = url.replace(domain, replacement_domain)

                    if preserve:
                        replacement = f"[{platform_label}]({fixed_url})"
                    else:
                        replacement = fixed_url

                    fixed_content = fixed_content.replace(url, replacement)

        if fixed_content != message.content:
            webhook = None
            for wh in await message.channel.webhooks():
                if wh.name == "AutoLinkFixer":
                    webhook = wh
                    break

            if webhook is None:
                webhook = await message.channel.create_webhook(name="AutoLinkFixer")

            await webhook.send(
                content=fixed_content,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )
            await message.delete()


async def setup(bot):
    await bot.add_cog(LinkFixer(bot))
