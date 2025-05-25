# bot/cogs/settings_panel.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Select, Button
import re
import io
import aiohttp
import asyncio
import logging
from datetime import datetime, timezone

from bot.utils.database import get_guild_data, update_guild_data

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SettingsModal(Modal):
    def __init__(
        self,
        target_type: str,
        current_value: str = None,
        original_interaction: discord.Interaction = None,
        bot_user: discord.User = None,
        parent_view: View = None,
    ):
        modal_title = {
            "welcome_channel": "設定歡迎頻道",
            "welcome_message": "設定歡迎訊息模板",
            "welcome_banner": "設定橫幅圖片 URL",
            "clear_welcome_banner": "將橫幅圖設為使用者頭像",
            "welcome_initial_role": "設定初始身份組",
            "leave_channel": "設定離開頻道",
            "leave_message": "設定離開訊息模板",
            "leave_banner": "設定離開橫幅圖片 URL",
            "clear_leave_banner": "將橫幅圖設為使用者頭像",
            "profile_banner": "設定橫幅圖片 URL",
            "clear_profile_banner": "確認清除用戶檔案橫幅圖片",
            "role_selection_channel": "設定身份組選擇頻道",
            "manage_selectable_roles": "管理可選身份組",
        }.get(target_type, "設定伺服器選項")

        super().__init__(title=modal_title)
        self.target_type = target_type
        self.original_interaction = original_interaction
        self.bot_user = bot_user
        self.parent_view = parent_view

        if target_type in [
            "welcome_channel",
            "leave_channel",
            "role_selection_channel",
        ]:
            self.input = TextInput(
                label="頻道 ID",
                placeholder="輸入文字頻道的 ID (例如: 123456789012345678) 或 'None' 禁用",
                required=True,
                style=discord.TextStyle.short,
                default=current_value,
            )
            self.add_item(self.input)
        elif target_type == "welcome_initial_role":
            self.input = TextInput(
                label="身份組 ID",
                placeholder="輸入身份組的 ID",
                required=True,
                style=discord.TextStyle.short,
                default=current_value,
            )
            self.add_item(self.input)
        elif target_type == "manage_selectable_roles":
            self.input = TextInput(
                label="可選身份組 ID",
                placeholder="輸入身份組 ID (多個 ID 用逗號分隔，例如: 123,456,789)",
                required=True,
                style=discord.TextStyle.short,
                default=current_value,
            )
            self.add_item(self.input)
        elif target_type in ["welcome_message", "leave_message"]:
            self.input = TextInput(
                label="訊息模板",
                placeholder="輸入訊息模板 (使用 {member} 和 {guild} 作為佔位符)",
                required=True,
                style=discord.TextStyle.paragraph,
                default=(
                    "歡迎 {member} 加入 {guild}！"
                    if target_type == "welcome_message" and not current_value
                    else "{member} 已離開 {guild}！"
                    if target_type == "leave_message" and not current_value
                    else current_value
                ),
            )
            self.add_item(self.input)
        elif target_type in ["welcome_banner", "leave_banner", "profile_banner"]:
            self.input = TextInput(
                label="圖片 URL",
                placeholder="輸入圖片的 URL (例如: https://example.com/image.png)",
                required=True,
                style=discord.TextStyle.short,
                default=current_value,
            )
            self.add_item(self.input)
        elif target_type in [
            "clear_welcome_banner",
            "clear_leave_banner",
            "clear_profile_banner",
        ]:
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

        logger.debug(f"Modal submitted for {self.target_type}, guild_id: {guild_id}")

        if self.target_type == "welcome_channel":
            channel_input = self.input.value.strip()
            if channel_input.lower() == "none":
                guild_data["welcome_channel_id"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed.title = "✅ 設定成功"
                response_embed.description = "歡迎訊息`已禁用`。"
                response_embed.color = discord.Color.green()
            elif not channel_input.isdigit():
                response_embed.title = "❌ 操作失敗"
                response_embed.description = "頻道 ID 必須是數字或 'None'。請輸入有效的文字頻道 ID 或 'None' 禁用。"
                response_embed.color = discord.Color.red()
            else:
                channel = interaction.guild.get_channel(int(channel_input))
                if not channel or not isinstance(channel, discord.TextChannel):
                    response_embed.title = "❌ 操作失敗"
                    response_embed.description = (
                        "找不到指定的文字頻道。請確保 ID 正確且頻道為文字頻道。"
                    )
                    response_embed.color = discord.Color.red()
                else:
                    guild_data["welcome_channel_id"] = int(channel_input)
                    await update_guild_data(guild_id, guild_data)
                    response_embed.title = "✅ 設定成功"
                    response_embed.description = f"歡迎頻道已設定為: {channel.mention}"
                    response_embed.color = discord.Color.green()
        elif self.target_type == "welcome_message":
            message_template = self.input.value.strip()
            if not ("{member}" in message_template and "{guild}" in message_template):
                response_embed.title = "❌ 操作失敗"
                response_embed.description = (
                    "訊息模板必須包含 {member} 和 {guild} 佔位符。"
                )
                response_embed.color = discord.Color.red()
            else:
                guild_data["welcome_message_template"] = message_template
                await update_guild_data(guild_id, guild_data)
                response_embed.title = "✅ 設定成功"
                response_embed.description = (
                    f"歡迎訊息模板已設定為: `{message_template}`"
                )
                response_embed.color = discord.Color.green()
        elif self.target_type == "welcome_banner":
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
                                guild_data["welcome_custom_banner_url"] = url
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
        elif self.target_type == "clear_welcome_banner":
            if self.input.value.strip().lower() != "yes":
                response_embed.title = "❌ 操作失敗"
                response_embed.description = (
                    "輸入不正確。請輸入 **'Yes'** 來確認清除操作。"
                )
                response_embed.color = discord.Color.red()
            else:
                guild_data["welcome_custom_banner_url"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed.title = "✅ 操作成功"
                response_embed.description = "目前使用使用者的頭像作為歡迎橫幅圖"
                response_embed.color = discord.Color.green()
        elif self.target_type == "welcome_initial_role":
            role_id = self.input.value.strip()
            if not role_id.isdigit():
                response_embed.title = "❌ 操作失敗"
                response_embed.description = (
                    "身份組 ID 必須是數字。請輸入有效的身份組 ID。"
                )
                response_embed.color = discord.Color.red()
            else:
                role = interaction.guild.get_role(int(role_id))
                if not role or not role.is_assignable():
                    response_embed.title = "❌ 操作失敗"
                    response_embed.description = "找不到指定的身份組，或身份組不可指派。請確保 ID 正確且身份組可由機器人指派。"
                    response_embed.color = discord.Color.red()
                else:
                    guild_data["welcome_initial_role_id"] = int(role_id)
                    await update_guild_data(guild_id, guild_data)
                    response_embed.title = "✅ 設定成功"
                    response_embed.description = f"初始身份組已設定為: {role.mention}"
                    response_embed.color = discord.Color.green()
        elif self.target_type == "leave_channel":
            channel_input = self.input.value.strip()
            if channel_input.lower() == "none":
                guild_data["leave_channel_id"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed.title = "✅ 設定成功"
                response_embed.description = "離開訊息`已禁用`。"
                response_embed.color = discord.Color.green()
            elif not channel_input.isdigit():
                response_embed.title = "❌ 操作失敗"
                response_embed.description = "頻道 ID 必須是數字或 'None'。請輸入有效的文字頻道 ID 或 'None' 禁用。"
                response_embed.color = discord.Color.red()
            else:
                channel = interaction.guild.get_channel(int(channel_input))
                if not channel or not isinstance(channel, discord.TextChannel):
                    response_embed.title = "❌ 操作失敗"
                    response_embed.description = (
                        "找不到指定的文字頻道。請確保 ID 正確且頻道為文字頻道。"
                    )
                    response_embed.color = discord.Color.red()
                else:
                    guild_data["leave_channel_id"] = int(channel_input)
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
                response_embed.description = "目前使用使用者的頭像作為離開橫幅圖"
                response_embed.color = discord.Color.green()
        elif self.target_type == "profile_banner":
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
                                guild_data["custom_banner_url"] = url
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
        elif self.target_type == "clear_profile_banner":
            if self.input.value.strip().lower() != "yes":
                response_embed.title = "❌ 操作失敗"
                response_embed.description = (
                    "輸入不正確。請輸入 **'Yes'** 來確認清除操作。"
                )
                response_embed.color = discord.Color.red()
            else:
                guild_data["custom_banner_url"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed.title = "✅ 操作成功"
                response_embed.description = "目前使用使用者的頭像作為用戶檔案橫幅圖"
                response_embed.color = discord.Color.green()
        elif self.target_type == "role_selection_channel":
            channel_input = self.input.value.strip()
            if channel_input.lower() == "none":
                guild_data["role_selection_channel_id"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed.title = "✅ 設定成功"
                response_embed.description = "身份組選擇功能已禁用。"
                response_embed.color = discord.Color.green()
            elif not channel_input.isdigit():
                response_embed.title = "❌ 操作失敗"
                response_embed.description = "頻道 ID 必須是數字或 'None'。"
                response_embed.color = discord.Color.red()
            else:
                channel = interaction.guild.get_channel(int(channel_input))
                if not channel or not isinstance(channel, discord.TextChannel):
                    response_embed.title = "❌ 操作失敗"
                    response_embed.description = "找不到指定的文字頻道。"
                    response_embed.color = discord.Color.red()
                else:
                    guild_data["role_selection_channel_id"] = int(channel_input)
                    await update_guild_data(guild_id, guild_data)
                    response_embed.title = "✅ 設定成功"
                    response_embed.description = (
                        f"身份組選擇頻道已設定為: {channel.mention}"
                    )
                    response_embed.color = discord.Color.green()
        elif self.target_type == "manage_selectable_roles":
            role_ids = [
                rid.strip()
                for rid in self.input.value.split(",")
                if rid.strip().isdigit()
            ]
            valid_roles = []
            for rid in role_ids:
                role = interaction.guild.get_role(int(rid))
                if role and role.is_assignable():
                    valid_roles.append(int(rid))
            if not valid_roles:
                response_embed.title = "❌ 操作失敗"
                response_embed.description = "無效的身份組 ID 或身份組不可指派。"
                response_embed.color = discord.Color.red()
            else:
                guild_data["selectable_roles"] = valid_roles
                await update_guild_data(guild_id, guild_data)
                response_embed.title = "✅ 設定成功"
                response_embed.description = f"可選身份組已更新: {', '.join([interaction.guild.get_role(rid).mention for rid in valid_roles])}"
                response_embed.color = discord.Color.green()

        response_embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務",
            icon_url=self.bot_user.display_avatar.url,
        )
        await interaction.edit_original_response(
            embed=response_embed, attachments=response_files, view=None
        )
        if self.parent_view:
            logger.debug(f"準備更新原始消息，target_type: {self.target_type}")
            await asyncio.sleep(3)
            try:
                await self.parent_view._update_original_command_message(
                    interaction, guild_id
                )
            except Exception as e:
                logger.error(f"Modal 後更新原始消息失敗: {e}")

class SettingsView(View):
    def __init__(
        self,
        original_interaction: discord.Interaction = None,
        bot_user: discord.User = None,
    ):
        super().__init__(timeout=600)  # 10 minutes
        self.original_interaction = original_interaction
        self.bot_user = bot_user
        self.current_page = 0
        self.max_pages = 4  # 5 pages (0 to 4)
        self.created_at = datetime.now(timezone.utc)  # Track creation time
        if original_interaction is None:
            logger.warning("SettingsView initialized with None original_interaction")
        else:
            logger.debug(
                f"SettingsView initialized with original_interaction: {original_interaction.id}"
            )
        self.add_item(self.previous_button())
        self.add_item(self.next_button())

    def previous_button(self):
        button = Button(
            label="上一頁",
            style=discord.ButtonStyle.primary,
            disabled=self.current_page == 0,
        )
        button.callback = self.previous_page
        logger.debug(f"Created previous_button: {button}")
        return button

    def next_button(self):
        button = Button(
            label="下一頁",
            style=discord.ButtonStyle.primary,
            disabled=self.current_page == self.max_pages,
        )
        button.callback = self.next_page
        logger.debug(f"Created next_button: {button}")
        return button

    async def previous_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_page = max(0, self.current_page - 1)
        await self._update_original_command_message(interaction, interaction.guild_id)

    async def next_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_page = min(self.max_pages, self.current_page + 1)
        await self._update_original_command_message(interaction, interaction.guild_id)

    def welcome_select(self):
        select = Select(
            placeholder="選擇歡迎訊息設定...",
            options=[
                discord.SelectOption(
                    label="設定歡迎頻道",
                    value="welcome_channel",
                    description="設定新成員加入時的歡迎訊息頻道或禁用",
                ),
                discord.SelectOption(
                    label="設定歡迎訊息模板",
                    value="welcome_message",
                    description="自訂歡迎訊息文字",
                ),
                discord.SelectOption(
                    label="切換歡迎圖片生成",
                    value="toggle_welcome_image",
                    description="啟用或停用歡迎訊息中的圖片",
                ),
                discord.SelectOption(
                    label="切換歡迎GIF/靜態圖片",
                    value="toggle_welcome_gif",
                    description="啟用或停用歡迎訊息中的GIF生成",
                ),
                discord.SelectOption(
                    label="設定自訂歡迎橫幅圖",
                    value="welcome_banner",
                    description="設定自訂的歡迎橫幅圖片",
                ),
                discord.SelectOption(
                    label="使用使用者頭像作為歡迎橫幅",
                    value="clear_welcome_banner",
                    description="清除自訂橫幅，使用使用者頭像",
                ),
                discord.SelectOption(
                    label="設定初始身份組",
                    value="welcome_initial_role",
                    description="設定新成員加入時自動指派的身份組",
                ),
                discord.SelectOption(
                    label="清除初始身份組",
                    value="clear_welcome_initial_role",
                    description="移除自動指派的初始身份組",
                ),
            ],
            custom_id="welcome_select",
        )
        return select

    def leave_select(self):
        select = Select(
            placeholder="選擇離開訊息設定...",
            options=[
                discord.SelectOption(
                    label="設定離開頻道",
                    value="leave_channel",
                    description="設定成員離開時的訊息頻道或禁用",
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
            custom_id="leave_select",
        )
        return select

    def profile_select(self):
        select = Select(
            placeholder="選擇用戶檔案設定...",
            options=[
                discord.SelectOption(
                    label="切換用戶檔案GIF/靜態圖片",
                    value="toggle_profile_gif",
                    description="啟用或停用用戶檔案中的GIF生成",
                ),
                discord.SelectOption(
                    label="設定自訂用戶檔案橫幅圖",
                    value="profile_banner",
                    description="設定自訂的用戶檔案橫幅圖片",
                ),
                discord.SelectOption(
                    label="使用使用者頭像作為用戶檔案橫幅",
                    value="clear_profile_banner",
                    description="清除自訂橫幅，使用使用者頭像",
                ),
            ],
            custom_id="profile_select",
        )
        return select

    def role_select(self):
        select = Select(
            placeholder="選擇身份組設定...",
            options=[
                discord.SelectOption(
                    label="設定身份組選擇頻道",
                    value="role_selection_channel",
                    description="設定身份組選擇功能的頻道或禁用",
                ),
                discord.SelectOption(
                    label="管理可選身份組",
                    value="manage_selectable_roles",
                    description="設定可供選擇的身份組",
                ),
            ],
            custom_id="role_select",
        )
        return select

    def ban_select(self):
        select = Select(
            placeholder="選擇封禁設定...",
            options=[
                discord.SelectOption(
                    label="設定封禁管理頻道",
                    value="ban_channel",
                    description="選擇封禁管理面板的頻道",
                ),
                discord.SelectOption(
                    label="設定封禁日誌頻道",
                    value="ban_log_channel",
                    description="選擇封禁日誌的頻道",
                ),
                discord.SelectOption(
                    label="禁用封禁管理功能",
                    value="disable_ban_system",
                    description="清除封禁頻道設定",
                ),
            ],
            custom_id="ban_select",
        )
        return select

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Check if interaction is expired
        time_elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        if time_elapsed > 840:  # 14 minutes
            logger.warning(f"Interaction expired, interaction_id: {interaction.id}")
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ 面板已過期",
                    description="此設定面板已過期，請使用 `/panel` 重新開啟。",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            self.stop()  # Terminate view
            return False

        if interaction.data.get("component_type") == discord.ComponentType.select.value:
            selected_value = interaction.data["values"][0]
            logger.debug(
                f"Select interaction: {selected_value}, interaction: {interaction.id}"
            )
            await self.handle_selection(interaction, selected_value)
            return False
        return True

    async def handle_selection(
        self, interaction: discord.Interaction, selected_value: str
    ):
        guild_id = interaction.guild_id
        guild_data = await get_guild_data(guild_id)

        if selected_value == "toggle_welcome_image":
            await interaction.response.defer(ephemeral=True)
            current_image_setting = guild_data.get("welcome_image_enabled", True)
            new_image_setting = not current_image_setting
            guild_data["welcome_image_enabled"] = new_image_setting
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if new_image_setting else "停用"
            response_embed = discord.Embed(
                title="✅ 設定已更新",
                description=f"歡迎訊息圖片生成已 **{status}**。",
                color=discord.Color.green(),
            )
            response_embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務",
                icon_url=self.bot_user.display_avatar.url,
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        elif selected_value == "toggle_welcome_gif":
            await interaction.response.defer(ephemeral=True)
            current_gif_setting = guild_data.get("welcome_generate_gif", True)
            new_gif_setting = not current_gif_setting
            guild_data["welcome_generate_gif"] = new_gif_setting
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if new_gif_setting else "停用"
            response_embed = discord.Embed(
                title="✅ 設定已更新",
                description=f"GIF已 **{status}**。",
                color=discord.Color.green(),
            )
            response_embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務",
                icon_url=self.bot_user.display_avatar.url,
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        elif selected_value == "toggle_leave_image":
            await interaction.response.defer(ephemeral=True)
            current_image_setting = guild_data.get("leave_image_enabled", True)
            new_image_setting = not current_image_setting
            guild_data["leave_image_enabled"] = new_image_setting
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if new_image_setting else "停用"
            response_embed = discord.Embed(
                title="✅ 設定已更新",
                description=f"圖片生成已 **{status}**。",
                color=discord.Color.green(),
            )
            response_embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務",
                icon_url=self.bot_user.display_avatar.url,
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        elif selected_value == "toggle_leave_gif":
            await interaction.response.defer(ephemeral=True)
            current_gif_setting = guild_data.get("leave_generate_gif", True)
            new_gif_setting = not current_gif_setting
            guild_data["leave_generate_gif"] = new_gif_setting
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if new_gif_setting else "停用"
            response_embed = discord.Embed(
                title="✅ 設定已更新",
                description=f"GIF已 **{status}**。",
                color=discord.Color.green(),
            )
            response_embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務",
                icon_url=self.bot_user.display_avatar.url,
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        elif selected_value == "toggle_profile_gif":
            await interaction.response.defer(ephemeral=True)
            current_gif_setting = guild_data.get("generate_gif_profile_image", True)
            new_gif_setting = not current_gif_setting
            guild_data["generate_gif_profile_image"] = new_gif_setting
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if new_gif_setting else "停用"
            response_embed = discord.Embed(
                title="✅ 設定已更新",
                description=f"GIF已 **{status}**。",
                color=discord.Color.green(),
            )
            response_embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務",
                icon_url=self.bot_user.display_avatar.url,
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        elif selected_value == "clear_welcome_initial_role":
            await interaction.response.defer(ephemeral=True)
            guild_data["welcome_initial_role_id"] = None
            await update_guild_data(guild_id, guild_data)
            response_embed = discord.Embed(
                title="✅ 設定已更新",
                description="初始身份組已清除，新成員將不會自動獲得身份組。",
                color=discord.Color.green(),
            )
            response_embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務",
                icon_url=self.bot_user.display_avatar.url,
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        elif selected_value == "ban_channel":
            channels = [
                channel
                for channel in interaction.guild.text_channels
                if channel.permissions_for(interaction.guild.me).send_messages
            ]
            if not channels:
                await interaction.response.send_message(
                    "沒有可用的文字頻道！", ephemeral=True
                )
                return
            options = [
                discord.SelectOption(label=channel.name, value=str(channel.id))
                for channel in channels[:25]
            ]
            select = Select(
                placeholder="選擇封禁管理頻道",
                options=options,
                min_values=1,
                max_values=1,
                custom_id="ban_channel_select",
            )

            async def on_channel_select(interaction: discord.Interaction):
                channel_id = int(interaction.data["values"][0])
                channel = interaction.guild.get_channel(channel_id)
                if not channel or not isinstance(channel, discord.TextChannel):
                    await interaction.response.send_message(
                        "無效的頻道選擇！", ephemeral=True
                    )
                    return
                guild_data["ban_channel_id"] = channel_id
                await update_guild_data(guild_id, guild_data)
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="✅ 設定成功",
                        description=f"封禁管理頻道已設定為: {channel.mention}",
                        color=discord.Color.green(),
                    ),
                    ephemeral=True,
                )
                await self._update_original_command_message(interaction, guild_id)

            select.callback = on_channel_select
            view = View(timeout=60)
            view.add_item(select)
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="選擇封禁管理頻道",
                    description="請選擇一個文字頻道用於封禁管理面板。",
                    color=discord.Color.blue(),
                ),
                view=view,
                ephemeral=True,
            )
            return
        elif selected_value == "ban_log_channel":
            channels = [
                channel
                for channel in interaction.guild.text_channels
                if channel.permissions_for(interaction.guild.me).send_messages
            ]
            if not channels:
                await interaction.response.send_message(
                    "沒有可用的文字頻道！", ephemeral=True
                )
                return
            options = [
                discord.SelectOption(label=channel.name, value=str(channel.id))
                for channel in channels[:25]
            ]
            select = Select(
                placeholder="選擇封禁日誌頻道",
                options=options,
                min_values=1,
                max_values=1,
                custom_id="ban_log_channel_select",
            )

            async def on_channel_select(interaction: discord.Interaction):
                channel_id = int(interaction.data["values"][0])
                channel = interaction.guild.get_channel(channel_id)
                if not channel or not isinstance(channel, discord.TextChannel):
                    await interaction.response.send_message(
                        "無效的頻道選擇！", ephemeral=True
                    )
                    return
                guild_data["ban_log_channel_id"] = channel_id
                await update_guild_data(guild_id, guild_data)
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="✅ 設定成功",
                        description=f"封禁日誌頻道已設定為: {channel.mention}",
                        color=discord.Color.green(),
                    ),
                    ephemeral=True,
                )
                await self._update_original_command_message(interaction, guild_id)

            select.callback = on_channel_select
            view = View(timeout=60)
            view.add_item(select)
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="選擇封禁日誌頻道",
                    description="請選擇一個文字頻道用於封禁日誌。",
                    color=discord.Color.blue(),
                ),
                view=view,
                ephemeral=True,
            )
            return
        elif selected_value == "disable_ban_system":
            await interaction.response.defer(ephemeral=True)
            guild_data["ban_channel_id"] = None
            guild_data["ban_log_channel_id"] = None
            await update_guild_data(guild_id, guild_data)
            response_embed = discord.Embed(
                title="✅ 設定已更新",
                description="封禁管理功能已禁用。",
                color=discord.Color.green(),
            )
            response_embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務",
                icon_url=self.bot_user.display_avatar.url,
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
            await self._update_original_command_message(interaction, guild_id)
            return
        elif selected_value == "welcome_channel":
            current_value = (
                str(guild_data.get("welcome_channel_id", ""))
                if guild_data.get("welcome_channel_id")
                else ""
            )
            await interaction.response.send_modal(
                SettingsModal(
                    "welcome_channel",
                    current_value,
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "welcome_message":
            current_value = guild_data.get("welcome_message_template")
            await interaction.response.send_modal(
                SettingsModal(
                    "welcome_message",
                    current_value,
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "welcome_banner":
            current_value = guild_data.get("welcome_custom_banner_url")
            await interaction.response.send_modal(
                SettingsModal(
                    "welcome_banner",
                    current_value,
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "clear_welcome_banner":
            await interaction.response.send_modal(
                SettingsModal(
                    "clear_welcome_banner",
                    original_interaction=self.original_interaction,
                    bot_user=self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "welcome_initial_role":
            current_value = (
                str(guild_data.get("welcome_initial_role_id", ""))
                if guild_data.get("welcome_initial_role_id")
                else ""
            )
            await interaction.response.send_modal(
                SettingsModal(
                    "welcome_initial_role",
                    current_value,
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "leave_channel":
            current_value = (
                str(guild_data.get("leave_channel_id", ""))
                if guild_data.get("leave_channel_id")
                else ""
            )
            await interaction.response.send_modal(
                SettingsModal(
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
                SettingsModal(
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
                SettingsModal(
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
                SettingsModal(
                    "clear_leave_banner",
                    original_interaction=self.original_interaction,
                    bot_user=self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "profile_banner":
            current_value = guild_data.get("custom_banner_url")
            await interaction.response.send_modal(
                SettingsModal(
                    "profile_banner",
                    current_value,
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "clear_profile_banner":
            await interaction.response.send_modal(
                SettingsModal(
                    "clear_profile_banner",
                    original_interaction=self.original_interaction,
                    bot_user=self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "role_selection_channel":
            current_value = (
                str(guild_data.get("role_selection_channel_id", ""))
                if guild_data.get("role_selection_channel_id")
                else ""
            )
            await interaction.response.send_modal(
                SettingsModal(
                    "role_selection_channel",
                    current_value,
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "manage_selectable_roles":
            await interaction.response.send_modal(
                SettingsModal(
                    "manage_selectable_roles",
                    ",".join(map(str, guild_data.get("selectable_roles", []))),
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,
                )
            )
            return

        logger.debug(f"Updating view after toggle selection: {selected_value}")
        await self._update_original_command_message(interaction, guild_id)

    async def _update_original_command_message(
        self, interaction: discord.Interaction, guild_id: int
    ):
        updated_guild_data = await get_guild_data(guild_id)
        embed, view = self._create_current_page(updated_guild_data, self.bot_user)
        for item in view.children:
            if isinstance(item, Button):
                if item.label == "上一頁":
                    item.disabled = self.current_page == 0
                elif item.label == "下一頁":
                    item.disabled = self.current_page == self.max_pages

        # Check if interaction is expired
        time_elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        if time_elapsed > 840:  # 14 minutes
            logger.warning(f"Interaction expired, interaction_id: {interaction.id}")
            try:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="⚠️ 面板已過期",
                        description="此設定面板已過期，請使用 `/panel` 重新開啟。",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
            except Exception as e:
                logger.error(f"Failed to send expiration message: {e}")
            self.stop()  # Terminate view
            return

        try:
            # Try editing the original message
            await interaction.edit_original_response(embed=embed, view=view)
            logger.debug(
                f"Updated interaction, page: {self.current_page}, embed: {embed.title}, interaction_id: {interaction.id}"
            )
        except discord.errors.NotFound as e:
            logger.debug(
                f"Webhook unavailable, attempting to send new message, interaction_id: {interaction.id}, error: {e}"
            )
            try:
                # Use followup to send new message
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                logger.debug(f"Sent new message via followup, interaction_id: {interaction.id}")
            except discord.errors.NotFound as followup_e:
                logger.error(f"Followup send failed: {followup_e}")
                try:
                    # Final fallback: Send via channel
                    await interaction.channel.send(
                        embed=embed, view=view, ephemeral=True
                    )
                    logger.debug(f"Sent new message via channel, interaction_id: {interaction.id}")
                except Exception as channel_e:
                    logger.error(f"Channel send failed: {channel_e}")
                    try:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ 更新失敗",
                                description="無法更新設定面板，請重試或使用 `/panel` 重新開啟。",
                                color=discord.Color.red(),
                            ),
                            ephemeral=True,
                        )
                    except Exception as final_e:
                        logger.error(f"Final send failed: {final_e}")
        except discord.errors.InteractionResponded:
            logger.debug(
                f"Interaction already responded, attempting to send new message, interaction_id: {interaction.id}"
            )
            try:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception as e:
                logger.error(f"Followup send failed: {e}")
                try:
                    await interaction.channel.send(
                        embed=embed, view=view, ephemeral=True
                    )
                except Exception as channel_e:
                    logger.error(f"Channel send failed: {channel_e}")
                    try:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ 更新失敗",
                                description="無法更新設定面板，請重試或使用 `/panel` 重新開啟。",
                                color=discord.Color.red(),
                            ),
                            ephemeral=True,
                        )
                    except Exception as final_e:
                        logger.error(f"Final send failed: {final_e}")
        except discord.errors.Forbidden:
            logger.error("Bot lacks permissions to edit or send messages")
            try:
                await interaction.followup.send(
                    "機器人缺少更新面板的權限。", ephemeral=True
                )
            except Exception as e:
                logger.error(f"Failed to send permission error message: {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating message: {e}")
            try:
                await interaction.followup.send(
                    "更新面板時發生錯誤。", ephemeral=True
                )
            except Exception as final_e:
                logger.error(f"Final send failed: {final_e}")

    def _create_current_page(
        self, guild_data: dict, bot_user: discord.User
    ) -> tuple[discord.Embed, View]:
        view = SettingsView(
            original_interaction=self.original_interaction, bot_user=bot_user
        )
        view.current_page = min(self.current_page, view.max_pages)  # Cap page number
        logger.debug(f"Creating page {view.current_page}")

        if view.current_page == 0:
            embed = discord.Embed(
                title="📬 歡迎訊息設定",
                description="使用下方的下拉選單來設定歡迎訊息選項。",
                color=discord.Color.green(),
            )
            welcome_channel_id = guild_data.get("welcome_channel_id")
            welcome_message_template = guild_data.get(
                "welcome_message_template", "未設定"
            )
            welcome_image_enabled = guild_data.get("welcome_image_enabled", True)
            welcome_generate_gif = guild_data.get("welcome_generate_gif", True)
            welcome_custom_banner_url = guild_data.get("welcome_custom_banner_url")
            welcome_initial_role_id = guild_data.get("welcome_initial_role_id")
            welcome_channel = (
                self.original_interaction.guild.get_channel(welcome_channel_id)
                if welcome_channel_id and self.original_interaction.guild
                else None
            )
            welcome_role = (
                self.original_interaction.guild.get_role(welcome_initial_role_id)
                if welcome_initial_role_id and self.original_interaction.guild
                else None
            )
            welcome_field = (
                f"**歡迎頻道**: {welcome_channel.mention if welcome_channel else '禁用'}\n"
                f"**訊息模板**: `{welcome_message_template}`\n"
                f"**圖片生成**: {'啟用' if welcome_image_enabled else '停用'}\n"
                f"**GIF**: {'啟用' if welcome_generate_gif else '停用'}\n"
                f"**自訂橫幅**: {'[圖片連結](' + welcome_custom_banner_url + ')' if welcome_custom_banner_url else '使用使用者頭像'}\n"
                f"**初始身份組**: {welcome_role.mention if welcome_role else '未設定'}"
            )
            embed.add_field(name="目前設定", value=welcome_field, inline=False)
            if welcome_custom_banner_url:
                embed.set_image(url=welcome_custom_banner_url)
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務 | 頁面 1/5",
                icon_url=bot_user.display_avatar.url,
            )
            select = view.welcome_select()
            view.add_item(select)
        elif view.current_page == 1:
            embed = discord.Embed(
                title="📤 離開訊息設定",
                description="使用下方的下拉選單來設定離開訊息選項。",
                color=discord.Color.red(),
            )
            leave_channel_id = guild_data.get("leave_channel_id")
            leave_message_template = guild_data.get("leave_message_template", "未設定")
            leave_image_enabled = guild_data.get("leave_image_enabled", True)
            leave_generate_gif = guild_data.get("leave_generate_gif", True)
            leave_custom_banner_url = guild_data.get("leave_custom_banner_url")
            leave_channel = (
                self.original_interaction.guild.get_channel(leave_channel_id)
                if leave_channel_id and self.original_interaction.guild
                else None
            )
            leave_field = (
                f"**離開頻道**: {leave_channel.mention if leave_channel else '禁用'}\n"
                f"**訊息模板**: `{leave_message_template}`\n"
                f"**圖片生成**: {'啟用' if leave_image_enabled else '停用'}\n"
                f"**GIF**: {'啟用' if leave_generate_gif else '停用'}\n"
                f"**自訂橫幅**: {'[圖片連結](' + leave_custom_banner_url + ')' if leave_custom_banner_url else '使用使用者頭像'}"
            )
            embed.add_field(name="目前設定", value=leave_field, inline=False)
            if leave_custom_banner_url:
                embed.set_image(url=leave_custom_banner_url)
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務 | 頁面 2/5",
                icon_url=bot_user.display_avatar.url,
            )
            select = view.leave_select()
            view.add_item(select)
        elif view.current_page == 2:
            embed = discord.Embed(
                title="📷 用戶檔案設定",
                description="使用下方的下拉選單來設定用戶檔案選項。",
                color=discord.Color.blue(),
            )
            generate_gif_profile_image = guild_data.get(
                "generate_gif_profile_image", True
            )
            custom_banner_url = guild_data.get("custom_banner_url")
            profile_field = (
                f"**GIF**: {'啟用' if generate_gif_profile_image else '停用'}\n"
                f"**自訂橫幅**: {'[圖片連結](' + custom_banner_url + ')' if custom_banner_url else '使用使用者頭像'}"
            )
            embed.add_field(name="目前設定", value=profile_field, inline=False)
            if custom_banner_url:
                embed.set_image(url=custom_banner_url)
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務 | 頁面 3/5",
                icon_url=bot_user.display_avatar.url,
            )
            select = view.profile_select()
            view.add_item(select)
        elif view.current_page == 3:
            embed = discord.Embed(
                title="🎭 身份組選擇設定",
                description="使用下方的下拉選單來設定身份組選擇功能。",
                color=discord.Color.purple(),
            )
            role_selection_channel_id = guild_data.get("role_selection_channel_id")
            selectable_roles = guild_data.get("selectable_roles", [])
            role_selection_channel = (
                self.original_interaction.guild.get_channel(role_selection_channel_id)
                if role_selection_channel_id and self.original_interaction.guild
                else None
            )
            role_mentions = [
                self.original_interaction.guild.get_role(role_id).mention
                for role_id in selectable_roles
                if self.original_interaction.guild.get_role(role_id)
            ]
            roles_field = (
                f"**選擇頻道**: {role_selection_channel.mention if role_selection_channel else '未設定'}\n"
                f"**可選身份組**: {', '.join(role_mentions) if role_mentions else '無'}"
            )
            embed.add_field(name="目前設定", value=roles_field, inline=False)
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務 | 頁面 4/5",
                icon_url=bot_user.display_avatar.url,
            )
            select = view.role_select()
            view.add_item(select)
        elif view.current_page == 4:
            embed = discord.Embed(
                title="🔨 封禁管理設定",
                description="使用下方的下拉選單來設定封禁管理功能。",
                color=discord.Color.red(),
            )
            ban_channel_id = guild_data.get("ban_channel_id")
            ban_log_channel_id = guild_data.get("ban_log_channel_id")
            ban_channel = (
                self.original_interaction.guild.get_channel(ban_channel_id)
                if ban_channel_id and self.original_interaction.guild
                else None
            )
            ban_log_channel = (
                self.original_interaction.guild.get_channel(ban_log_channel_id)
                if ban_log_channel_id and self.original_interaction.guild
                else None
            )
            ban_field = (
                f"**封禁管理頻道**: {ban_channel.mention if ban_channel else '未設定'}\n"
                f"**封禁日誌頻道**: {ban_log_channel.mention if ban_log_channel else '未設定'}"
            )
            embed.add_field(name="目前設定", value=ban_field, inline=False)
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務 | 頁面 5/5",
                icon_url=bot_user.display_avatar.url,
            )
            select = view.ban_select()
            view.add_item(select)
        else:
            # Fallback for invalid page
            embed = discord.Embed(
                title="⚙️ 錯誤",
                description="無效的頁面！請返回主頁。",
                color=discord.Color.red(),
            )
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務",
                icon_url=bot_user.display_avatar.url,
            )

        return embed, view

class SettingsManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="panel",
        description="管理伺服器設定，包括歡迎訊息、離開訊息、用戶檔案、身份組選擇和封禁管理",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def set_server_settings(self, interaction: discord.Interaction):
        if self.bot.user is None:
            logger.error("Bot user is None")
            await interaction.response.send_message(
                "Bot is not properly initialized.", ephemeral=True
            )
            return
        current_guild_data = await get_guild_data(interaction.guild_id)
        view = SettingsView(original_interaction=interaction, bot_user=self.bot.user)
        embed, view = view._create_current_page(current_guild_data, self.bot.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsManager(bot))
