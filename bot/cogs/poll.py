import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Select, Button
import asyncio
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=discord.utils.MISSING) # Use discord's default logging level for cleaner output
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
            custom_id="poll_question_input" # Add custom_id for potential re-use or debugging
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
            await interaction.response.send_message(
                "請至少提供兩個選項！", ephemeral=True
            )
            return
        if len(options) > 8:
            await interaction.response.send_message(
                "最多支援8個選項！", ephemeral=True
            )
            return
        
        try:
            duration = int(self.duration.value)
            if duration < 1 or duration > 24:
                await interaction.response.send_message(
                    "持續時間必須介於1到24小時之間！", ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "請輸入有效的數字！", ephemeral=True
            )
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
        # It's better to get the message object after sending the initial response
        view.message = await interaction.original_response() 
        logger.debug(f"Poll created by {interaction.user.id}: {self.question.value}, duration: {duration} hours")
        asyncio.create_task(view.send_reminders())

class PollView(View):
    def __init__(self, question: str, options: list[str], duration_hours: int, bot_user: discord.User, creator_id: int):
        super().__init__(timeout=duration_hours * 3600)  # Convert hours to seconds
        self.question = question
        self.options = options
        self.bot_user = bot_user
        self.creator_id = creator_id
        self.votes = {i: [] for i in range(len(options))}  # List of user IDs per option
        self.message = None # This will be set after the message is sent
        self.end_time = datetime.utcnow() + timedelta(hours=duration_hours)
        self.add_item(self.create_select())
        self.add_item(self.create_end_button())

    def create_select(self):
        # Define a list of unicode number emojis for clarity
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]

        select = Select(
            placeholder="選擇一個選項進行投票...",
            options=[
                discord.SelectOption(
                    label=option,
                    value=str(i),
                    description=f"選項 {i+1}",
                    # Use the direct unicode emoji string here
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
        
        # Check if user has already voted for this option
        if user_id in self.votes[option_index]:
            await interaction.response.send_message(
                "你已經投過這個選項了！", ephemeral=True
            )
            return

        # Remove user's previous vote if any
        for opt, voters in self.votes.items():
            if user_id in voters:
                voters.remove(user_id)
                break
        
        # Record new vote
        self.votes[option_index].append(user_id)
        logger.debug(f"User {user_id} voted for option {option_index} in poll: {self.question}")
        
        # Defer the interaction before updating the message to avoid "This interaction failed"
        await interaction.response.defer() 
        await self.update_poll_message(interaction)

    async def end_poll_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message(
                "只有投票發起人可以結算投票！", ephemeral=True
            )
            return
        await interaction.response.defer()
        logger.debug(f"Poll ended manually by creator {self.creator_id}: {self.question}")
        await self.finalize_poll(interaction)

    async def update_poll_message(self, interaction: discord.Interaction):
        embed = self.create_poll_embed()
        try:
            # Use self.message directly if available, otherwise interaction.edit_original_response
            # The interaction here is from the select_callback, so it refers to the same message.
            await interaction.edit_original_response(embed=embed, view=self)
        except discord.NotFound:
            logger.error("Poll message not found for updating (update_poll_message)")
            # No need for follow_up here, as edit_original_response should handle it
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
            elif interaction: # Fallback if message wasn't set, but interaction is available
                await interaction.edit_original_response(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Failed to finalize poll: {e}")
            if interaction:
                # Use followup if the initial response was deferred and we're sending a final message
                await interaction.followup.send("結算投票時發生錯誤。", ephemeral=True)
        self.stop()

    async def send_reminders(self):
        # Ensure self.message is set before trying to send reminders
        while self.message is None:
            await asyncio.sleep(0.1) # Wait for message to be set

        while not self.is_finished():
            time_left = self.end_time - datetime.utcnow()
            seconds_left = time_left.total_seconds()
            
            if seconds_left <= 0:
                break # Poll has ended

            if seconds_left <= 60:  # 1-minute reminder
                await self.message.channel.send(
                    f"📊 投票 `{self.question}` 將在1分鐘後結束！請把握最後機會投票！"
                )
                break # Exit loop after sending final reminder
            elif seconds_left <= 3600 and seconds_left > 60:  # Last hour, wait until 1 min mark
                await asyncio.sleep(seconds_left - 60)
                continue
            else:  # Hourly reminder
                # Calculate sleep time to reach the next full hour mark
                seconds_until_next_hour = seconds_left % 3600
                if seconds_until_next_hour == 0 and seconds_left > 0: # Exactly on an hour boundary
                    seconds_until_next_hour = 3600
                
                # If less than an hour left but more than a minute, sleep until 1 min mark
                if seconds_left <= 3600:
                     await asyncio.sleep(seconds_left - 60)
                else: # Sleep for the remaining part of the current hour to hit the next full hour
                     await asyncio.sleep(seconds_until_next_hour)
                     
                if not self.is_finished() and self.message:
                    # Recalculate hours_left after sleeping
                    remaining_time_after_sleep = self.end_time - datetime.utcnow()
                    hours_left = max(0, int(remaining_time_after_sleep.total_seconds() // 3600))
                    
                    if hours_left > 0: # Only send if there are full hours left
                        await self.message.channel.send(
                            f"📊 投票 `{self.question}` 還有 {hours_left} 小時結束！快來投票吧！"
                        )
                    # If hours_left is 0 but still more than 1 minute, the next iteration will handle the 1-minute reminder.


    def create_poll_embed(self) -> discord.Embed:
        total_votes = sum(len(voters) for voters in self.votes.values())
        embed = discord.Embed(
            title=f"📊 投票: {self.question}",
            description="請從下拉選單選擇一個選項進行投票！每人限投一票。",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )
        # Define a list of unicode number emojis for clarity in embed
        number_emojis_embed = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]

        for i, option in enumerate(self.options):
            vote_count = len(self.votes[i])
            percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
            # Add a simple bar representation
            bar = "█" * int(percentage // 10) # 10 blocks for 100%
            empty_bar = "░" * (10 - len(bar))
            
            # Use the correct emoji for the embed field name
            emoji_char = number_emojis_embed[i] if i < len(number_emojis_embed) else ""

            embed.add_field(
                name=f"{emoji_char} {option}", # Use emoji_char directly
                value=f"{bar}{empty_bar} {vote_count} 票 ({percentage:.1f}%)",
                inline=False,
            )
        
        time_left = self.end_time - datetime.utcnow()
        if time_left.total_seconds() > 0 and not self.is_finished():
            hours_left = max(0, int(time_left.total_seconds() // 3600))
            minutes_left = max(0, int((time_left.total_seconds() % 3600) // 60))
            time_text = f"{hours_left} 小時 {minutes_left} 分鐘" if hours_left > 0 else f"{minutes_left} 分鐘"
            embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務 | 投票剩餘時間: {time_text}",
                icon_url=self.bot_user.display_avatar.url,
            )
        else: # Poll has ended or is about to
             embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務 | 投票已結束",
                icon_url=self.bot_user.display_avatar.url,
            )
        return embed

    async def on_timeout(self):
        logger.debug(f"Poll timed out: {self.question}")
        if self.message:
            await self.finalize_poll(None)
        self.stop()

class PollCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="poll",
        description="創建一個投票，最多8個選項，持續時間1到24小時",
    )
    async def create_poll(self, interaction: discord.Interaction):
        if self.bot.user is None:
            logger.error("Bot user is None")
            await interaction.response.send_message(
                "Bot 未正確初始化。", ephemeral=True
            )
            return
        await interaction.response.send_modal(PollCreationModal(self.bot.user))

async def setup(bot: commands.Bot):
    await bot.add_cog(PollCog(bot))
