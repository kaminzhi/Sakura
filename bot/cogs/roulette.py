# bot/cogs/roulette.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Button
import asyncio
import logging
import random  # Import for random selection
from datetime import datetime  # Only datetime needed here

# Set up logging for this cog
logger = logging.getLogger("roulette_cog")
logger.setLevel(logging.DEBUG)  # You might want to adjust this level in production


class RouletteSetupModal(Modal):
    def __init__(self, bot_user: discord.User):
        super().__init__(title="設定抽籤輪盤")
        self.bot_user = bot_user
        self.activity_name = TextInput(
            label="抽籤活動名稱",
            placeholder="例如：幸運大轉盤、禮物抽獎",
            max_length=50,
            required=True,
            style=discord.TextStyle.short,
        )
        self.participants = TextInput(
            label="參與者 (用逗號分隔，至少2個)",
            placeholder="小明,小華,小美,傑克",
            max_length=1000,
            required=True,
            style=discord.TextStyle.paragraph,
        )
        self.num_winners = TextInput(
            label="得獎者數量 (1到10之間)",
            placeholder="例如：1",
            max_length=2,
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.activity_name)
        self.add_item(self.participants)
        self.add_item(self.num_winners)

    async def on_submit(self, interaction: discord.Interaction):
        activity_name = self.activity_name.value
        participants = [
            p.strip() for p in self.participants.value.split(",") if p.strip()
        ]

        if len(participants) < 2:
            await interaction.response.send_message(
                "請至少提供兩位參與者！", ephemeral=True
            )
            return

        try:
            num_winners = int(self.num_winners.value)
            if num_winners < 1 or num_winners > 10:
                await interaction.response.send_message(
                    "得獎者數量必須介於1到10之間！", ephemeral=True
                )
                return
            if num_winners > len(participants):
                await interaction.response.send_message(
                    f"得獎者數量 ({num_winners}) 不能多於參與者數量 ({len(participants)})！",
                    ephemeral=True,
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "得獎者數量請輸入有效的數字！", ephemeral=True
            )
            return

        view = RouletteView(
            activity_name=activity_name,
            participants=participants,
            num_winners=num_winners,
            creator_id=interaction.user.id,
            bot_user=interaction.client.user,  # Use client.user here
        )
        embed = view.create_roulette_embed()
        await interaction.response.send_message(embed=embed, view=view)


class RouletteView(View):
    def __init__(
        self,
        activity_name: str,
        participants: list[str],
        num_winners: int,
        creator_id: int,
        bot_user: discord.User,
    ):
        super().__init__(timeout=None)  # Roulette view doesn't timeout automatically
        self.activity_name = activity_name
        self.all_participants = participants
        self.remaining_participants = list(participants)
        self.num_winners = num_winners
        self.creator_id = creator_id
        self.bot_user = bot_user
        self.winners = []
        self.message = None  # To store the message this view is attached to

        self.add_item(
            Button(
                label="開始抽籤",
                style=discord.ButtonStyle.green,
                custom_id="roulette_start",
            )
        )
        self.children[0].callback = self.start_drawing_callback

    def create_roulette_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🎲 抽籤輪盤: {self.activity_name}",
            description="點擊按鈕開始抽籤！",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(
            name="✨ 參與者",
            value="\n".join(self.all_participants) if self.all_participants else "無",
            inline=False,
        )
        embed.add_field(name="🏆 選中數量", value=str(self.num_winners), inline=True)

        if self.winners:
            winner_list = "\n".join([f"選中 {winner}！" for winner in self.winners])
            embed.add_field(name="🎉 ", value=winner_list, inline=False)
            embed.color = discord.Color.gold()

        embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務 | 抽籤活動",
            icon_url=self.bot_user.display_avatar.url,
        )
        return embed

    async def start_drawing_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message(
                "只有活動發起人可以開始抽籤！", ephemeral=True
            )
            return

        if not self.remaining_participants:
            await interaction.response.send_message(
                "沒有可供抽籤的參與者了！", ephemeral=True
            )
            return

        if self.winners:
            await interaction.response.send_message(
                "抽籤已經完成，請勿重複操作！", ephemeral=True
            )
            return

        await interaction.response.defer()

        self.winners = random.sample(self.remaining_participants, self.num_winners)

        for item in self.children:
            item.disabled = True

        embed = self.create_roulette_embed()
        embed.description = "抽籤已完成，如下："
        embed.title = f"🎊 抽籤結果: {self.activity_name}"

        try:
            self.message = (
                await interaction.original_response()
            )  # Ensure message is set
            await self.message.edit(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Failed to update roulette message after drawing: {e}")
            await interaction.followup.send(
                "抽籤後更新訊息時發生錯誤。", ephemeral=True
            )

        logger.debug(
            f"Roulette drawing completed for '{self.activity_name}'. Winners: {self.winners}"
        )
        self.stop()  # Stop the view after drawing


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
