# bot/views/poll_views.py
import discord
from discord.ui import Modal, TextInput, View, Select, Button
import asyncio
import logging
from datetime import datetime, timedelta
from .embed_builder import build_poll_embed, build_error_embed

logger = logging.getLogger(__name__)


class PollCreationModal(Modal):
    def __init__(self, bot_user: discord.User):
        super().__init__(title="創建投票")
        self.bot_user = bot_user
        self.question = TextInput(
            label="投票問題",
            placeholder="輸入投票的問題 (最多100字)",
            max_length=100,
            required=True,
            style=discord.TextStyle.short,
            custom_id="poll_question_input"
        )
        self.options = TextInput(
            label="投票選項 (用逗號分隔，至少2個，最多8個)",
            placeholder="選項1,選項2,選項3...",
            max_length=500,
            required=True,
            style=discord.TextStyle.paragraph,
            custom_id="poll_options_input"
        )
        self.duration = TextInput(
            label="投票持續時間 (小時)",
            placeholder="輸入1到24之間的數字",
            default="24",
            max_length=2,
            required=True,
            style=discord.TextStyle.short,
            custom_id="poll_duration_input"
        )
        self.add_item(self.question)
        self.add_item(self.options)
        self.add_item(self.duration)

    async def on_submit(self, interaction: discord.Interaction):
        options = [opt.strip() for opt in self.options.value.split(",") if opt.strip()]
        if len(options) < 2:
            embed = build_error_embed(
                title="選項不足",
                description="請至少提供兩個選項！",
                bot_user=self.bot_user
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if len(options) > 8:
            embed = build_error_embed(
                title="選項過多",
                description="最多支援8個選項！",
                bot_user=self.bot_user
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            duration = int(self.duration.value)
            if duration < 1 or duration > 24:
                embed = build_error_embed(
                    title="時間範圍錯誤",
                    description="持續時間必須介於1到24小時之間！",
                    bot_user=self.bot_user
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        except ValueError:
            embed = build_error_embed(
                title="輸入錯誤",
                description="請輸入有效的數字！",
                bot_user=self.bot_user
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = PollView(
            question=self.question.value,
            options=options,
            duration_hours=duration,
            bot_user=self.bot_user,
            creator_id=interaction.user.id,
        )
        embed = view.create_poll_embed()
        
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response() 
        logger.debug(f"Poll created by {interaction.user.id}: {self.question.value}, duration: {duration} hours")
        asyncio.create_task(view.send_reminders())


class PollView(View):
    def __init__(self, question: str, options: list[str], duration_hours: int, bot_user: discord.User, creator_id: int):
        super().__init__(timeout=duration_hours * 3600)
        self.question = question
        self.options = options
        self.bot_user = bot_user
        self.creator_id = creator_id
        self.votes = {i: [] for i in range(len(options))}
        self.message = None
        self.end_time = datetime.utcnow() + timedelta(hours=duration_hours)
        self.add_item(self.create_select())
        self.add_item(self.create_end_button())

    def create_select(self):
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]

        select = Select(
            placeholder="選擇一個選項進行投票...",
            options=[
                discord.SelectOption(
                    label=option,
                    value=str(i),
                    description=f"選項 {i+1}",
                    emoji=number_emojis[i] if i < len(number_emojis) else None, 
                )
                for i, option in enumerate(self.options)
            ],
            custom_id="poll_select",
        )
        select.callback = self.select_callback
        return select

    def create_end_button(self):
        button = Button(
            label="結算投票",
            style=discord.ButtonStyle.danger,
            custom_id="poll_end",
        )
        button.callback = self.end_poll_callback
        return button

    async def select_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        option_index = int(interaction.data["values"][0])
        
        if user_id in self.votes[option_index]:
            embed = build_error_embed(
                title="重複投票",
                description="你已經投過這個選項了！",
                bot_user=self.bot_user
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        for opt, voters in self.votes.items():
            if user_id in voters:
                voters.remove(user_id)
                break
        
        self.votes[option_index].append(user_id)
        logger.debug(f"User {user_id} voted for option {option_index} in poll: {self.question}")
        
        await interaction.response.defer() 
        await self.update_poll_message(interaction)

    async def end_poll_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.creator_id:
            embed = build_error_embed(
                title="權限不足",
                description="只有投票發起人可以結算投票！",
                bot_user=self.bot_user
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await interaction.response.defer()
        logger.debug(f"Poll ended manually by creator {self.creator_id}: {self.question}")
        await self.finalize_poll(interaction)

    async def update_poll_message(self, interaction: discord.Interaction):
        embed = self.create_poll_embed()
        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except discord.NotFound:
            logger.error("Poll message not found for updating (update_poll_message)")
        except discord.Forbidden:
            logger.error("Bot lacks permissions to edit poll message (update_poll_message)")
            await interaction.followup.send("Bot 缺少編輯訊息的權限。", ephemeral=True)
        except Exception as e:
            logger.error(f"Unexpected error updating poll: {e} (update_poll_message)")
            await interaction.followup.send("更新投票時發生錯誤。", ephemeral=True)

    async def finalize_poll(self, interaction: discord.Interaction = None):
        for item in self.children:
            item.disabled = True
        embed = self.create_poll_embed()
        embed.title = f"📊 投票結束: {self.question}"
        embed.description = "投票已結束，感謝參與！以下是最終結果："
        embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務 | 投票已結束",
            icon_url=self.bot_user.display_avatar.url,
        )
        try:
            if self.message:
                await self.message.edit(embed=embed, view=self)
            elif interaction:
                await interaction.edit_original_response(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Failed to finalize poll: {e}")
            if interaction:
                await interaction.followup.send("結算投票時發生錯誤。", ephemeral=True)
        self.stop()

    async def send_reminders(self):
        while self.message is None:
            await asyncio.sleep(0.1)

        while not self.is_finished():
            time_left = self.end_time - datetime.utcnow()
            seconds_left = time_left.total_seconds()
            
            if seconds_left <= 0:
                break

            if seconds_left <= 60:
                await self.message.channel.send(
                    f"📊 投票 `{self.question}` 將在1分鐘後結束！請把握最後機會投票！"
                )
                break
            elif seconds_left <= 3600 and seconds_left > 60:
                await asyncio.sleep(seconds_left - 60)
                continue
            else:
                seconds_until_next_hour = seconds_left % 3600
                if seconds_until_next_hour == 0 and seconds_left > 0:
                    seconds_until_next_hour = 3600
                
                if seconds_left <= 3600:
                     await asyncio.sleep(seconds_left - 60)
                else:
                     await asyncio.sleep(seconds_until_next_hour)
                     
                if not self.is_finished() and self.message:
                    remaining_time_after_sleep = self.end_time - datetime.utcnow()
                    hours_left = max(0, int(remaining_time_after_sleep.total_seconds() // 3600))
                    
                    if hours_left > 0:
                        await self.message.channel.send(
                            f"📊 投票 `{self.question}` 還有 {hours_left} 小時結束！快來投票吧！"
                        )

    def create_poll_embed(self) -> discord.Embed:
        return build_poll_embed(
            question=self.question,
            options=self.options,
            votes=self.votes,
            end_time=self.end_time,
            bot_user=self.bot_user
        )

    async def on_timeout(self):
        logger.debug(f"Poll timed out: {self.question}")
        if self.message:
            await self.finalize_poll(None)
        self.stop()
