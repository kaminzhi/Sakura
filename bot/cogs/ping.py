import discord
from discord.ext import commands
from discord.ui import Button, View


class PingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.slash_command(
        name="cog_ping_button", description="Embed with button below text"
    )
    async def cog_ping_button(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(
            title="Cog Pong!",
            description="這個 Cog 運作正常！點擊下面的按鈕來做一些事情。",
            color=discord.Color.green(),
        )

        # 創建一個 View 來包含按鈕
        view = View()

        # 創建一個按鈕
        button = Button(label="點擊我！", style=discord.ButtonStyle.primary)

        async def button_callback(interaction: discord.Interaction):
            await interaction.response.send_message("你點擊了按鈕！", ephemeral=True)

        button.callback = button_callback

        # 將按鈕添加到 View
        view.add_item(button)

        # 回應包含 Embed 和 View 的訊息
        await ctx.respond(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(PingCog(bot))
