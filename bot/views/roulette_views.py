# bot/views/roulette_views.py
import discord
from discord.ui import Modal, TextInput, View, Button
import asyncio
import logging
import random
from datetime import datetime
from .embed_builder import build_roulette_embed, build_error_embed

logger = logging.getLogger("roulette_views")
logger.setLevel(logging.DEBUG)


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
            embed = build_error_embed(
                title="參與者不足",
                description="請至少提供兩位參與者！",
                bot_user=self.bot_user
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            num_winners = int(self.num_winners.value)
            if num_winners < 1 or num_winners > 10:
                embed = build_error_embed(
                    title="得獎者數量錯誤",
                    description="得獎者數量必須介於1到10之間！",
                    bot_user=self.bot_user
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if num_winners > len(participants):
                embed = build_error_embed(
                    title="得獎者數量過多",
                    description=f"得獎者數量 ({num_winners}) 不能多於參與者數量 ({len(participants)})！",
                    bot_user=self.bot_user
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        except ValueError:
            embed = build_error_embed(
                title="輸入錯誤",
                description="得獎者數量請輸入有效的數字！",
                bot_user=self.bot_user
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        return build_roulette_embed(
            activity_name=self.activity_name,
            participants=self.all_participants,
            num_winners=self.num_winners,
            winners=self.winners,
            bot_user=self.bot_user
        )

    async def start_drawing_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.creator_id:
            embed = build_error_embed(
                title="權限不足",
                description="只有活動發起人可以開始抽籤！",
                bot_user=self.bot_user
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not self.remaining_participants:
            embed = build_error_embed(
                title="無參與者",
                description="沒有可供抽籤的參與者了！",
                bot_user=self.bot_user
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if self.winners:
            embed = build_error_embed(
                title="重複操作",
                description="抽籤已經完成，請勿重複操作！",
                bot_user=self.bot_user
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        self.winners = random.sample(self.remaining_participants, self.num_winners)

        for item in self.children:
            item.disabled = True

        embed = self.create_roulette_embed()

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
        self.stop()
