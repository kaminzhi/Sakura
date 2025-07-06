# bot/cogs/devpanel.py
import os
import discord
from discord import ui, app_commands, Interaction
from discord.ext import commands
from datetime import datetime
import logging
from bot.utils.database import (
    get_guild_data,
    log_ban,
    is_server_banned,
    unban_server,
    get_banned_servers,
)

BOT_OWNER_IDS = int(os.getenv("BOT_OWNER_IDS"))
START_TIME = datetime.utcnow()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class DevPanelView(ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        # Add the Status Select dropdown
        self.add_item(StatusSelect(bot))
        # Add the NEW Server Management dropdown
        self.add_item(ServerManagementSelect(bot))
        # Keep the view buttons as they are
        self.add_item(ViewJoinedServersButton(bot))
        self.add_item(ViewBannedServersButton(bot))

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


class ServerManagementSelect(ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="🔨 封禁伺服器",
                value="ban_server",
                description="讓機器人離開指定伺服器並封禁",
            ),
            discord.SelectOption(
                label="✅ 解除伺服器封禁",
                value="unban_server",
                description="允許機器人重新加入被封禁的伺服器",
            ),
        ]
        super().__init__(
            placeholder="選擇伺服器管理操作",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_server_management_action",
        )

    async def callback(self, interaction: Interaction):
        selected = self.values[0]

        if selected == "ban_server":

            class BanServerModal(ui.Modal, title="封禁伺服器"):
                guild_id = ui.TextInput(
                    label="伺服器 ID",
                    placeholder="輸入要封禁的伺服器 ID",
                    style=discord.TextStyle.short,
                    required=True,
                )
                reason = ui.TextInput(
                    label="封禁原因",
                    placeholder="輸入封禁原因 (可選)",
                    style=discord.TextStyle.paragraph,
                    required=False,
                )

                async def on_submit(inner_self, inner_interaction: Interaction):
                    guild_id_str = str(inner_self.guild_id).strip()
                    reason = str(inner_self.reason).strip() or "開發者發起的伺服器封禁"

                    if not guild_id_str.isdigit():
                        await inner_interaction.response.send_message(
                            "❌ 伺服器 ID 必須是數字。", ephemeral=True
                        )
                        return

                    guild_id = int(guild_id_str)
                    guild = self.bot.get_guild(guild_id)

                    if not guild:
                        await inner_interaction.response.send_message(
                            f"❌ 找不到 ID 為 {guild_id} 的伺服器，或機器人不在該伺服器中。",
                            ephemeral=True,
                        )
                        return

                    if await is_server_banned(guild_id):
                        await inner_interaction.response.send_message(
                            f"ℹ️ 伺服器 `{guild.name}` (ID: {guild_id}) 已處於封禁狀態。",
                            ephemeral=True,
                        )
                        return

                    try:
                        ban_data = {
                            "guild_id": guild_id,
                            "guild_name": guild.name,
                            "user_id": 0,
                            "moderator_id": inner_interaction.user.id,
                            "reason": reason,
                            "type": "server",
                            "active": True,
                        }
                        await log_ban(ban_data)
                        logger.debug(
                            f"Logged server ban to database for guild {guild_id}"
                        )

                        guild_data = await get_guild_data(guild_id)
                        log_channel_id = guild_data.get("ban_log_channel_id")
                        if log_channel_id:
                            log_channel = guild.get_channel(log_channel_id)
                            if log_channel and isinstance(
                                log_channel, discord.TextChannel
                            ):
                                log_embed = discord.Embed(
                                    title="🚫 伺服器封禁記錄",
                                    description=f"機器人已離開伺服器。",
                                    color=discord.Color.red(),
                                    timestamp=datetime.utcnow(),
                                )
                                log_embed.add_field(
                                    name="伺服器",
                                    value=f"{guild.name} (ID: {guild_id})",
                                    inline=False,
                                )
                                log_embed.add_field(
                                    name="原因", value=reason, inline=False
                                )
                                log_embed.add_field(
                                    name="操作者",
                                    value=inner_interaction.user.mention,
                                    inline=False,
                                )
                                log_embed.set_footer(
                                    text=f"由 {self.bot.user.name} 提供服務",
                                    icon_url=self.bot.user.avatar.url,
                                )
                                await log_channel.send(embed=log_embed)
                                logger.debug(
                                    f"Sent ban log to channel {log_channel_id} for guild {guild_id}"
                                )

                        await guild.leave()
                        logger.info(
                            f"Bot left guild {guild.name} (ID: {guild_id}) by {inner_interaction.user.id}"
                        )

                        await inner_interaction.response.send_message(
                            f"✅ 已成功讓機器人離開伺服器 `{guild.name}` (ID: {guild_id})。\n原因：{reason}",
                            ephemeral=True,
                        )
                    except discord.errors.Forbidden:
                        await inner_interaction.response.send_message(
                            "❌ 機器人沒有權限離開伺服器。", ephemeral=True
                        )
                        logger.error(
                            f"Forbidden: Bot lacks permission to leave guild {guild_id}"
                        )
                    except Exception as e:
                        await inner_interaction.response.send_message(
                            f"❌ 封禁伺服器失敗：{str(e)}", ephemeral=True
                        )
                        logger.error(f"Failed to ban guild {guild_id}: {str(e)}")

            await interaction.response.send_modal(BanServerModal())

        elif selected == "unban_server":

            class UnbanServerModal(ui.Modal, title="解除伺服器封禁"):
                guild_id = ui.TextInput(
                    label="伺服器 ID",
                    placeholder="輸入要解除封禁的伺服器 ID",
                    style=discord.TextStyle.short,
                    required=True,
                )

                async def on_submit(inner_self, inner_interaction: Interaction):
                    guild_id_str = str(inner_self.guild_id).strip()

                    if not guild_id_str.isdigit():
                        await inner_interaction.response.send_message(
                            "❌ 伺服器 ID 必須是數字。", ephemeral=True
                        )
                        return

                    guild_id = int(guild_id_str)

                    if not await is_server_banned(guild_id):
                        await inner_interaction.response.send_message(
                            f"ℹ️ 伺服器 ID `{guild_id}` 並未處於封禁狀態。",
                            ephemeral=True,
                        )
                        return

                    try:
                        await unban_server(guild_id)
                        logger.info(
                            f"Server {guild_id} has been unbanned by {inner_interaction.user.id}"
                        )
                        await inner_interaction.response.send_message(
                            f"✅ 已成功解除伺服器 `{guild_id}` 的封禁。該伺服器現在可以重新邀請機器人。",
                            ephemeral=True,
                        )
                    except Exception as e:
                        logger.error(f"Failed to unban guild {guild_id}: {str(e)}")
                        await inner_interaction.response.send_message(
                            f"❌ 解除伺服器封禁失敗：{str(e)}", ephemeral=True
                        )

            await interaction.response.send_modal(UnbanServerModal())


class ViewJoinedServersButton(ui.Button):
    def __init__(self, bot: commands.Bot):
        super().__init__(
            label="查看已加入伺服器",
            style=discord.ButtonStyle.blurple,
            custom_id="view_joined_servers_button",
        )
        self.bot = bot

    async def callback(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_list = []
        for guild in self.bot.guilds:
            guild_list.append(f"伺服器名稱: {guild.name}, 伺服器 ID: {guild.id}")

        if not guild_list:
            await interaction.followup.send(
                "機器人目前沒有加入任何伺服器。", ephemeral=True
            )
            return

        import io

        file_content = "\n".join(guild_list)
        file_data = io.BytesIO(file_content.encode("utf-8"))

        await interaction.followup.send(
            file=discord.File(file_data, filename="joined_servers.txt"),
            ephemeral=True,
            content="以下是機器人已加入的伺服器列表：",
        )
        logger.info(f"Generated and sent joined servers list to {interaction.user.id}")


class ViewBannedServersButton(ui.Button):
    def __init__(self, bot: commands.Bot):
        super().__init__(
            label="查看已封禁伺服器",
            style=discord.ButtonStyle.red,
            custom_id="view_banned_servers_button",
        )
        self.bot = bot

    async def callback(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        banned_servers_data = await get_banned_servers()
        banned_list = []

        if not banned_servers_data:
            await interaction.followup.send(
                "目前沒有任何封禁的伺服器。", ephemeral=True
            )
            return

        for ban_record in banned_servers_data:
            guild_id = ban_record.get("guild_id")
            guild_name = ban_record.get("guild_name", "未知伺服器名稱")
            ban_timestamp = ban_record.get("timestamp")

            formatted_date = (
                ban_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
                if ban_timestamp
                else "未知時間"
            )

            banned_list.append(
                f"伺服器名稱: {guild_name}, 伺服器 ID: {guild_id}, 封禁時間: {formatted_date}"
            )

        import io

        file_content = "\n".join(banned_list)
        file_data = io.BytesIO(file_content.encode("utf-8"))

        await interaction.followup.send(
            file=discord.File(file_data, filename="banned_servers.txt"),
            ephemeral=True,
            content="以下是已封禁的伺服器列表：",
        )
        logger.info(f"Generated and sent banned servers list to {interaction.user.id}")


class StatusSelect(ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="🎮 遊玩",
                value="playing",
                description="設定機器人狀態為『遊玩中』",
            ),
            discord.SelectOption(
                label="🎧 聆聽",
                value="listening",
                description="設定機器人狀態為『聆聽中』",
            ),
            discord.SelectOption(
                label="📺 觀看",
                value="watching",
                description="設定機器人狀態為『觀看中』",
            ),
            discord.SelectOption(
                label="🏆 競賽",
                value="competing",
                description="設定機器人狀態為『競賽中』",
            ),
            discord.SelectOption(
                label="📝 自定", value="custom", description="設定機器人狀態為『自訂』"
            ),
            discord.SelectOption(
                label="🎥 直播",
                value="streaming",
                description="設定機器人狀態為『直播中』",
            ),
        ]
        super().__init__(
            placeholder="選擇操作",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_dev_action",
        )

    async def callback(self, interaction: Interaction):
        selected = self.values[0]

        class StatusInputModal(ui.Modal, title="自訂狀態設定"):
            name = ui.TextInput(
                label="狀態文字",
                placeholder="輸入顯示的文字",
                style=discord.TextStyle.short,
            )
            url = ui.TextInput(
                label="串流網址 (僅 Streaming 使用)",
                style=discord.TextStyle.short,
                required=False,
            )

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
                    logger.debug(f"Bot status updated to {selected}: {text}")
                else:
                    await inner_interaction.response.send_message(
                        "❌ 無法設定此狀態。", ephemeral=True
                    )
                    logger.error(f"Failed to set status: {selected}")

        await interaction.response.send_modal(StatusInputModal())


class DevPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="panel-dev", description="僅限機器人擁有者可見的開發者控制面板"
    )
    async def devpanel(self, interaction: discord.Interaction):
        if interaction.user.id != BOT_OWNER_IDS:
            return await interaction.response.send_message(
                "❌ 僅限機器人擁有者可使用此指令。", ephemeral=True
            )

        view = DevPanelView(self.bot)
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Called when the bot joins a new guild."""
        logger.info(f"Bot joined guild: {guild.name} (ID: {guild.id})")
        if await is_server_banned(guild.id):
            logger.warning(
                f"Joined banned guild: {guild.name} (ID: {guild.id}). Leaving now."
            )
            try:
                await guild.leave()
                logger.info(
                    f"Successfully left banned guild: {guild.name} (ID: {guild.id})"
                )
            except discord.Forbidden:
                logger.error(
                    f"Failed to leave banned guild {guild.name} (ID: {guild.id}): Missing permissions."
                )
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred while leaving guild {guild.name} (ID: {guild.id}): {e}"
                )

            owner = self.bot.get_user(BOT_OWNER_IDS)
            if owner:
                try:
                    await owner.send(
                        f"警告: 機器人嘗試加入已封禁的伺服器 **{guild.name}** (ID: `{guild.id}`). 已自動離開。"
                    )
                except discord.Forbidden:
                    logger.warning(
                        f"Could not send message to bot owner {BOT_OWNER_IDS} about banned guild join."
                    )


async def setup(bot):
    await bot.add_cog(DevPanel(bot))
