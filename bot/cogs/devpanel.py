import os
import discord
from discord import ui, app_commands, Interaction
from discord.ext import commands
from datetime import datetime

BOT_OWNER_IDS = int(os.getenv("BOT_OWNER_IDS"))
START_TIME = datetime.utcnow()


class DevPanelView(ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(StatusSelect(bot))

    async def build_embed(self) -> discord.Embed:
        server_count = len(self.bot.guilds)
        uptime = datetime.utcnow() - START_TIME
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        embed = discord.Embed(
            title="🛠️ 開發者面板",
            description="僅限機器人擁有者可看見的面板。",
            color=discord.Color.blue(),
        )
        embed.add_field(name="🧑‍🤝‍🧑 總服務數量", value=f"{server_count}", inline=False)
        embed.add_field(
            name="⏱️ 上線時間",
            value=f"{hours} 小時 {minutes} 分 {seconds} 秒",
            inline=False,
        )
        embed.set_footer(
            text=f"由 {self.bot.user.name} 提供服務", icon_url=self.bot.user.avatar.url
        )
        return embed


class StatusSelect(ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="🎮 遊玩", value="playing"),
            discord.SelectOption(label="🎧 聆聽", value="listening"),
            discord.SelectOption(label="📺 觀看", value="watching"),
            discord.SelectOption(label="🏆 競賽", value="competing"),
            discord.SelectOption(label="📝 自定", value="custom"),
            discord.SelectOption(label="🎥 直播", value="streaming"),
        ]
        super().__init__(
            placeholder="選擇新的狀態類型",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_bot_status",
        )

    async def callback(self, interaction: Interaction):
        selected = self.values[0]

        class StatusInputModal(ui.Modal, title="自訂狀態設定"):
            name = ui.TextInput(label="狀態文字", placeholder="輸入顯示的文字")
            url = ui.TextInput(label="串流網址 (僅 Streaming 使用)", required=False)

            async def on_submit(inner_self, inner_interaction: Interaction):
                text = str(inner_self.name)
                url = str(inner_self.url).strip()

                if selected == "streaming" and url:
                    activity = discord.Streaming(name=text, url=url)
                elif selected == "custom":
                    activity = discord.CustomActivity(name=text)
                elif selected == "playing":
                    activity = discord.Game(name=text)
                elif selected == "listening":
                    activity = discord.Activity(
                        type=discord.ActivityType.listening, name=text
                    )
                elif selected == "watching":
                    activity = discord.Activity(
                        type=discord.ActivityType.watching, name=text
                    )
                elif selected == "competing":
                    activity = discord.Activity(
                        type=discord.ActivityType.competing, name=text
                    )
                else:
                    activity = None

                if activity:
                    await self.bot.change_presence(activity=activity)
                    await inner_interaction.response.send_message(
                        f"✅ 狀態已更新為 `{text}`。", ephemeral=True
                    )
                else:
                    await inner_interaction.response.send_message(
                        "❌ 無法設定此狀態。", ephemeral=True
                    )

        await interaction.response.send_modal(StatusInputModal())


class DevPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="devpanel", description="僅限機器人擁有者可見的開發者控制面板"
    )
    async def devpanel(self, interaction: discord.Interaction):
        if interaction.user.id != BOT_OWNER_IDS:
            return await interaction.response.send_message(
                "❌ 僅限機器人擁有者可使用此指令。", ephemeral=True
            )

        view = DevPanelView(self.bot)
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(DevPanel(bot))
