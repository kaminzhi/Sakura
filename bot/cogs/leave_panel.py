# bot/cogs/leave_panel.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Select
import re
import io
import aiohttp
import asyncio

from bot.utils.database import get_guild_data, update_guild_data


class LeaveSettingsModal(Modal):
    def __init__(
        self,
        target_type: str,
        current_value: str = None,
        original_interaction: discord.Interaction = None,
        bot_user: discord.User = None,
        parent_view: View = None,
    ):
        modal_title = {
            "leave_channel": "設定離開頻道",
            "leave_message": "設定離開訊息模板",
            "leave_banner": "設定離開橫幅圖片 URL",
            "clear_leave_banner": "確認清除離開橫幅圖片",
        }.get(target_type, "設定離開選項")

        super().__init__(title=modal_title)
        self.target_type = target_type
        self.original_interaction = original_interaction
        self.bot_user = bot_user
        self.parent_view = parent_view

        if target_type == "leave_channel":
            self.input = TextInput(
                label="頻道 ID",
                placeholder="輸入文字頻道的 ID (例如: 123456789012345678)",
                required=True,
                style=discord.TextStyle.short,
            )
            if current_value:
                self.input.default = current_value
            self.add_item(self.input)
        elif target_type == "leave_message":
            self.input = TextInput(
                label="離開訊息模板",
                placeholder="輸入訊息模板 (使用 {member} 和 {guild} 作為佔位符)",
                required=True,
                style=discord.TextStyle.paragraph,
                default="{member} 已離開 {guild}！"
                if not current_value
                else current_value,
            )
            self.add_item(self.input)
        elif target_type == "leave_banner":
            self.input = TextInput(
                label="圖片 URL",
                placeholder="輸入圖片的 URL (例如: https://example.com/image.png)",
                required=True,
                style=discord.TextStyle.short,
            )
            if current_value:
                self.input.default = current_value
            self.add_item(self.input)
        elif target_type == "clear_leave_banner":
            self.input = TextInput(
                label="輸入 'Yes' 以清除橫幅",
                placeholder="輸入 'Yes'",
                required=True,
                style=discord.TextStyle.short,
            )
            self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        guild_data = await get_guild_data(guild_id)
        response_embed = discord.Embed(color=discord.Color.blue())
        response_files = []

        if self.target_type == "leave_channel":
            channel_id = self.input.value.strip()
            if not channel_id.isdigit():
                response_embed.title = "❌ 操作失敗"
                response_embed.description = (
                    "頻道 ID 必須是數字。請輸入有效的文字頻道 ID。"
                )
                response_embed.color = discord.Color.red()
            else:
                channel = interaction.guild.get_channel(int(channel_id))
                if not channel or not isinstance(channel, discord.TextChannel):
                    response_embed.title = "❌ 操作失敗"
                    response_embed.description = (
                        "找不到指定的文字頻道。請確保 ID 正確且頻道為文字頻道。"
                    )
                    response_embed.color = discord.Color.red()
                else:
                    guild_data["leave_channel_id"] = int(channel_id)
                    await update_guild_data(guild_id, guild_data)
                    response_embed.title = "✅ 設定成功"
                    response_embed.description = f"離開頻道已設定為: {channel.mention}"
                    response_embed.color = discord.Color.green()
        elif self.target_type == "leave_message":
            message_template = self.input.value.strip()
            if not ("{member}" in message_template and "{guild}" in message_template):
                response_embed.title = "❌ 操作失敗"
                response_embed.description = (
                    "訊息模板必須包含 {member} 和 {guild} 佔位符。"
                )
                response_embed.color = discord.Color.red()
            else:
                guild_data["leave_message_template"] = message_template
                await update_guild_data(guild_id, guild_data)
                response_embed.title = "✅ 設定成功"
                response_embed.description = (
                    f"離開訊息模板已設定為: `{message_template}`"
                )
                response_embed.color = discord.Color.green()
        elif self.target_type == "leave_banner":
            url = self.input.value.strip()
            if not re.match(
                r"https?://.*\.(?:png|jpg|jpeg|gif|webp)", url, re.IGNORECASE
            ):
                response_embed.title = "❌ 操作失敗"
                response_embed.description = "無效的 URL 格式。請輸入有效的圖片 URL (png, jpg, jpeg, gif, webp)。"
                response_embed.color = discord.Color.red()
            else:
                image_bytes = None
                bot_session = getattr(interaction.client, "session", None)
                should_close_session = False
                if not isinstance(bot_session, aiohttp.ClientSession):
                    bot_session = aiohttp.ClientSession()
                    should_close_session = True
                try:
                    async with bot_session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            image_bytes = io.BytesIO(await resp.read())
                            content_type = resp.headers.get("Content-Type", "").lower()
                            if not content_type.startswith("image/"):
                                response_embed.title = "❌ 操作失敗"
                                response_embed.description = (
                                    "URL 指向的內容不是圖片。請確認 URL。"
                                )
                                response_embed.color = discord.Color.red()
                            else:
                                guild_data["leave_custom_banner_url"] = url
                                await update_guild_data(guild_id, guild_data)
                                response_embed.title = "✅ 設定成功"
                                response_embed.description = (
                                    f"已成功設定為: [圖片連結]({url})"
                                )
                                response_embed.color = discord.Color.green()
                                image_bytes.seek(0)
                                is_gif = image_bytes.getvalue()[:4] == b"GIF8"
                                filename = (
                                    "preview_banner.gif"
                                    if is_gif
                                    else "preview_banner.png"
                                )
                                file_obj = discord.File(image_bytes, filename=filename)
                                response_files.append(file_obj)
                                response_embed.set_image(url=f"attachment://{filename}")
                        else:
                            response_embed.title = "⚠️ 下載失敗"
                            response_embed.description = f"無法下載圖片。HTTP 狀態碼: {resp.status}。請檢查 URL 是否正確或可訪問。"
                            response_embed.color = discord.Color.gold()
                except aiohttp.ClientError as e:
                    response_embed.title = "❌ 網路錯誤"
                    response_embed.description = (
                        f"下載圖片時發生網路錯誤: {e}。請檢查 URL。"
                    )
                    response_embed.color = discord.Color.red()
                except asyncio.TimeoutError:
                    response_embed.title = "⏳ 下載逾時"
                    response_embed.description = (
                        "下載圖片逾時 (10秒)。請檢查 URL 是否有效或伺服器響應緩慢。"
                    )
                    response_embed.color = discord.Color.red()
                except Exception as e:
                    response_embed.title = "❌ 未知錯誤"
                    response_embed.description = (
                        f"下載圖片時發生未知錯誤: {e}。請檢查 URL。"
                    )
                    response_embed.color = discord.Color.red()
                finally:
                    if should_close_session:
                        await bot_session.close()
        elif self.target_type == "clear_leave_banner":
            if self.input.value.strip().lower() != "yes":
                response_embed.title = "❌ 操作失敗"
                response_embed.description = (
                    "輸入不正確。請輸入 **'Yes'** 來確認清除操作。"
                )
                response_embed.color = discord.Color.red()
            else:
                guild_data["leave_custom_banner_url"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed.title = "✅ 操作成功"
                response_embed.description = "目前使用使用者的頭像作爲離開橫幅圖"
                response_embed.color = discord.Color.green()

        response_embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務",
            icon_url=self.bot_user.display_avatar.url,
        )
        await interaction.edit_original_response(
            embed=response_embed, attachments=response_files
        )
        if self.parent_view:
            await self.parent_view._update_original_command_message(
                interaction, guild_id
            )


class LeaveSettingsView(View):
    def __init__(
        self,
        original_interaction: discord.Interaction = None,
        bot_user: discord.User = None,
    ):
        super().__init__(timeout=180)
        self.original_interaction = original_interaction
        self.bot_user = bot_user

    @discord.ui.select(
        cls=Select,
        placeholder="選擇要設定的離開選項...",
        options=[
            discord.SelectOption(
                label="設定離開頻道",
                value="leave_channel",
                description="設定成員離開時的訊息頻道",
            ),
            discord.SelectOption(
                label="設定離開訊息模板",
                value="leave_message",
                description="自訂離開訊息文字",
            ),
            discord.SelectOption(
                label="切換離開圖片生成",
                value="toggle_leave_image",
                description="啟用或停用離開訊息中的圖片",
            ),
            discord.SelectOption(
                label="切換離開GIF/靜態圖片",
                value="toggle_leave_gif",
                description="啟用或停用離開訊息中的GIF生成",
            ),
            discord.SelectOption(
                label="設定自訂離開橫幅圖",
                value="leave_banner",
                description="設定自訂的離開橫幅圖片",
            ),
            discord.SelectOption(
                label="使用使用者頭像作為離開橫幅",
                value="clear_leave_banner",
                description="清除自訂橫幅，使用使用者頭像",
            ),
        ],
    )
    async def select_leave_option(
        self, interaction: discord.Interaction, select: Select
    ):
        selected_value = select.values[0]
        guild_id = interaction.guild_id
        guild_data = await get_guild_data(guild_id)

        if selected_value == "toggle_leave_image":
            await interaction.response.defer(ephemeral=True)
            current_image_setting = guild_data.get("leave_image_enabled", True)
            new_image_setting = not current_image_setting
            guild_data["leave_image_enabled"] = new_image_setting
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if new_image_setting else "停用"
            response_embed = discord.Embed(
                title="✅ 設定已更新",
                description=f"離開訊息圖片生成已 **{status}**。",
                color=discord.Color.green(),
            )
            response_embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務",
                icon_url=self.bot_user.display_avatar.url,
            )
            await interaction.edit_original_response(embed=response_embed)
        elif selected_value == "toggle_leave_gif":
            await interaction.response.defer(ephemeral=True)
            current_gif_setting = guild_data.get("leave_generate_gif", True)
            new_gif_setting = not current_gif_setting
            guild_data["leave_generate_gif"] = new_gif_setting
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if new_gif_setting else "停用"
            response_embed = discord.Embed(
                title="✅ 設定已更新",
                description=f"離開訊息GIF生成已 **{status}**。",
                color=discord.Color.green(),
            )
            response_embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務",
                icon_url=self.bot_user.display_avatar.url,
            )
            await interaction.edit_original_response(embed=response_embed)
        elif selected_value == "leave_channel":
            current_value = str(guild_data.get("leave_channel_id", ""))
            await interaction.response.send_modal(
                LeaveSettingsModal(
                    "leave_channel",
                    current_value,
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "leave_message":
            current_value = guild_data.get("leave_message_template")
            await interaction.response.send_modal(
                LeaveSettingsModal(
                    "leave_message",
                    current_value,
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "leave_banner":
            current_value = guild_data.get("leave_custom_banner_url")
            await interaction.response.send_modal(
                LeaveSettingsModal(
                    "leave_banner",
                    current_value,
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "clear_leave_banner":
            await interaction.response.send_modal(
                LeaveSettingsModal(
                    "clear_leave_banner",
                    original_interaction=self.original_interaction,
                    bot_user=self.bot_user,
                    parent_view=self,
                )
            )
            return

        if selected_value not in [
            "leave_channel",
            "leave_message",
            "leave_banner",
            "clear_leave_banner",
        ]:
            await self._update_original_command_message(interaction, guild_id)

    async def _update_original_command_message(
        self, interaction: discord.Interaction, guild_id: int
    ):
        if self.original_interaction and self.original_interaction.message:
            try:
                updated_guild_data = await get_guild_data(guild_id)
                original_command_embed = self._create_leave_settings_embed(
                    updated_guild_data, self.bot_user
                )
                await self.original_interaction.edit_original_response(
                    embed=original_command_embed,
                    view=LeaveSettingsView(
                        original_interaction=self.original_interaction,
                        bot_user=self.bot_user,
                    ),
                )
            except discord.NotFound:
                print("Original message not found for editing.")
            except discord.Forbidden:
                print(
                    "Bot lacks permissions to edit the original command message. Please check the bot's permissions."
                )
            except Exception as e:
                print(
                    f"An unexpected error occurred while updating the original command message: {e}"
                )
        else:
            print(
                "Cannot update original command message because original_interaction or its message is None."
            )

    def _create_leave_settings_embed(self, guild_data: dict, bot_user: discord.User):
        embed = discord.Embed(
            title="📤 離開訊息設定",
            description="請使用下方的選單來設定離開頻道、訊息模板、圖片生成、GIF生成或自訂橫幅。",
            color=discord.Color.blue(),
        )
        leave_channel_id = guild_data.get("leave_channel_id")
        leave_message_template = guild_data.get("leave_message_template", "未設定")
        leave_image_enabled = guild_data.get("leave_image_enabled", True)
        leave_generate_gif = guild_data.get("leave_generate_gif", True)
        leave_custom_banner_url = guild_data.get("leave_custom_banner_url")

        field_value = f"離開頻道: {leave_channel_id if leave_channel_id else '未設定'}"
        field_value += f"\n訊息模板: `{leave_message_template}`"
        field_value += f"\n圖片生成: {'啟用' if leave_image_enabled else '停用'}"
        field_value += f"\nGIF生成: {'啟用' if leave_generate_gif else '停用'}"
        if leave_custom_banner_url:
            field_value += f"\n自訂橫幅: [圖片連結]({leave_custom_banner_url})"
            embed.set_image(url=leave_custom_banner_url)
        else:
            field_value += f"\n自訂橫幅: 使用使用者頭像"
            embed.set_image(url=None)
        embed.add_field(name="目前設定", value=field_value, inline=False)

        if bot_user:
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務",
                icon_url=bot_user.display_avatar.url,
            )
        return embed


class LeaveManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="set-leave-settings", description="管理離開訊息設定")
    @app_commands.default_permissions(manage_guild=True)
    async def set_leave_settings(self, interaction: discord.Interaction):
        current_guild_data = await get_guild_data(interaction.guild_id)
        embed = LeaveSettingsView(
            original_interaction=interaction, bot_user=self.bot.user
        )._create_leave_settings_embed(current_guild_data, self.bot.user)
        view = LeaveSettingsView(
            original_interaction=interaction, bot_user=self.bot.user
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaveManager(bot))
