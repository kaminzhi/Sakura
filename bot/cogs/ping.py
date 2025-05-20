import discord
from discord import app_commands
from discord.ext import commands
import random


class Ping(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ping", description="用超中二方式測試機器人延遲（有夠重要）"
    )
    async def ping(self, interaction: discord.Interaction):
        latency = self.bot.latency * 1000

        if latency < 100:
            status = f"延遲為`{latency:.2f}`ms"
            responses = [
                f"Wow, 比你打開冰箱還快！",
                f"你是不是住在我隔壁",
                f"這速度我都懷疑你是不是用光纖直連的！",
            ]
        elif latency < 300:
            status = f"延遲為`{latency:.2f}ms`"
            responses = [
                f"穩穩的，感覺像 4G...不是5G。",
                f"中規中矩，至少沒爆炸。",
                f"這延遲，還能接受。",
            ]
        else:
            status = f"延遲為`{latency:.2f}ms`"
            responses = [
                f"爆ping拉, 卡的跟狗一樣。",
                f"你這是從火星 ping 我嗎？",
                f"嗯...這延遲有點像在打麻將，等了半天才出牌。",
            ]

        description = f"{status}\n{random.choice(responses)}"

        embed = discord.Embed(
            title="🏓  Pong!",
            description=description,
            color=discord.Color.red()
            if latency > 300
            else (discord.Color.blue() if latency > 100 else discord.Color.green()),
        )
        embed.set_footer(
            text=f"由 {self.bot.user.name} 提供服務",
            icon_url=self.bot.user.display_avatar.url,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Ping(bot))
