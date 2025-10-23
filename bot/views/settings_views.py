import discord
from discord.ui import Modal, TextInput, View, Select, Button
import re
import io
import aiohttp
import asyncio
import logging
from datetime import datetime, timezone
from bot.utils.database import get_guild_data, update_guild_data
from bot.views.embed_builder import build_success_embed, build_error_embed, build_info_embed, build_warning_embed

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
            "dvc_trigger_channel": "設定觸發語音頻道",
            "dvc_category": "設定語音頻道分類",
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
            "dvc_trigger_channel",
            "dvc_category",
        ]:
            placeholder = (
                "輸入語音頻道 ID (例如: 123456789012345678) 或 'None' 禁用"
                if target_type == "dvc_trigger_channel"
                else "輸入分類 ID (例如: 123456789012345678) 或 'None' 禁用"
                if target_type == "dvc_category"
                else "輸入文字頻道 ID (例如: 123456789012345678) 或 'None' 禁用"
            )
            self.input = TextInput(
                label="頻道 ID" if target_type != "dvc_category" else "分類 ID",
                placeholder=placeholder,
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
                response_embed = build_success_embed("設定成功", "歡迎訊息`已禁用`。", bot_user=self.bot_user)
            elif not channel_input.isdigit():
                response_embed = build_error_embed("操作失敗", "頻道 ID 必須是數字或 'None'。請輸入有效的文字頻道 ID 或 'None' 禁用。", bot_user=self.bot_user)
            else:
                channel = interaction.guild.get_channel(int(channel_input))
                if not channel or not isinstance(channel, discord.TextChannel):
                    response_embed = build_error_embed("操作失敗", "找不到指定的文字頻道。請確保 ID 正確且頻道為文字頻道。", bot_user=self.bot_user)
                else:
                    guild_data["welcome_channel_id"] = int(channel_input)
                    await update_guild_data(guild_id, guild_data)
                    response_embed = build_success_embed("設定成功", f"歡迎頻道已設定為: {channel.mention}", bot_user=self.bot_user)
        elif self.target_type == "welcome_message":
            message_template = self.input.value.strip()
            if not ("{member}" in message_template and "{guild}" in message_template):
                response_embed = build_error_embed("操作失敗", "訊息模板必須包含 {member} 和 {guild} 佔位符。", bot_user=self.bot_user)
            else:
                guild_data["welcome_message_template"] = message_template
                await update_guild_data(guild_id, guild_data)
                response_embed = build_success_embed("設定成功", f"歡迎訊息模板已設定為: `{message_template}`", bot_user=self.bot_user)
        elif self.target_type == "welcome_banner":
            url = self.input.value.strip()
            if not re.match(
                r"https?://.*\.(?:png|jpg|jpeg|gif|webp)", url, re.IGNORECASE
            ):
                response_embed = build_error_embed("操作失敗", "無效的 URL 格式。請輸入有效的圖片 URL (png, jpg, jpeg, gif, webp)。", bot_user=self.bot_user)
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
                                response_embed = build_error_embed("操作失敗", "URL 指向的內容不是圖片。請確認 URL。", bot_user=self.bot_user)
                            else:
                                guild_data["welcome_custom_banner_url"] = url
                                await update_guild_data(guild_id, guild_data)
                                response_embed = build_success_embed("設定成功", f"已成功設定為: [圖片連結]({url})", bot_user=self.bot_user)
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
                            response_embed = build_warning_embed("下載失敗", f"無法下載圖片。HTTP 狀態碼: {resp.status}。請檢查 URL 是否正確或可訪問。", bot_user=self.bot_user)
                except aiohttp.ClientError as e:
                    response_embed = build_error_embed("網路錯誤", f"下載圖片時發生網路錯誤: {e}。請檢查 URL。", bot_user=self.bot_user)
                except asyncio.TimeoutError:
                    response_embed = build_error_embed("下載逾時", "下載圖片逾時 (10秒)。請檢查 URL 是否有效或伺服器響應緩慢。", bot_user=self.bot_user)
                except Exception as e:
                    response_embed = build_error_embed("未知錯誤", f"下載圖片時發生未知錯誤: {e}。請檢查 URL。", bot_user=self.bot_user)
                finally:
                    if should_close_session:
                        await bot_session.close()
        elif self.target_type == "clear_welcome_banner":
            if self.input.value.strip().lower() != "yes":
                response_embed = build_error_embed("操作失敗", "輸入不正確。請輸入 **'Yes'** 來確認清除操作。", bot_user=self.bot_user)
            else:
                guild_data["welcome_custom_banner_url"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed = build_success_embed("操作成功", "目前使用使用者的頭像作為歡迎橫幅圖", bot_user=self.bot_user)
        elif self.target_type == "welcome_initial_role":
            role_id = self.input.value.strip()
            if not role_id.isdigit():
                response_embed = build_error_embed("操作失敗", "身份組 ID 必須是數字。請輸入有效的身份組 ID。", bot_user=self.bot_user)
            else:
                role = interaction.guild.get_role(int(role_id))
                if not role or not role.is_assignable():
                    response_embed = build_error_embed("操作失敗", "找不到指定的身份組，或身份組不可指派。請確保 ID 正確且身份組可由機器人指派。", bot_user=self.bot_user)
                else:
                    guild_data["welcome_initial_role_id"] = int(role_id)
                    await update_guild_data(guild_id, guild_data)
                    response_embed = build_success_embed("設定成功", f"初始身份組已設定為: {role.mention}", bot_user=self.bot_user)
        elif self.target_type == "leave_channel":
            channel_input = self.input.value.strip()
            if channel_input.lower() == "none":
                guild_data["leave_channel_id"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed = build_success_embed("設定成功", "離開訊息`已禁用`。", bot_user=self.bot_user)
            elif not channel_input.isdigit():
                response_embed = build_error_embed("操作失敗", "頻道 ID 必須是數字或 'None'。請輸入有效的文字頻道 ID 或 'None' 禁用。", bot_user=self.bot_user)
            else:
                channel = interaction.guild.get_channel(int(channel_input))
                if not channel or not isinstance(channel, discord.TextChannel):
                    response_embed = build_error_embed("操作失敗", "找不到指定的文字頻道。請確保 ID 正確且頻道為文字頻道。", bot_user=self.bot_user)
                else:
                    guild_data["leave_channel_id"] = int(channel_input)
                    await update_guild_data(guild_id, guild_data)
                    response_embed = build_success_embed("設定成功", f"離開頻道已設定為: {channel.mention}", bot_user=self.bot_user)
        elif self.target_type == "leave_message":
            message_template = self.input.value.strip()
            if not ("{member}" in message_template and "{guild}" in message_template):
                response_embed = build_error_embed("操作失敗", "訊息模板必須包含 {member} 和 {guild} 佔位符。", bot_user=self.bot_user)
            else:
                guild_data["leave_message_template"] = message_template
                await update_guild_data(guild_id, guild_data)
                response_embed = build_success_embed("設定成功", f"離開訊息模板已設定為: `{message_template}`", bot_user=self.bot_user)
        elif self.target_type == "leave_banner":
            url = self.input.value.strip()
            if not re.match(
                r"https?://.*\.(?:png|jpg|jpeg|gif|webp)", url, re.IGNORECASE
            ):
                response_embed = build_error_embed("操作失敗", "無效的 URL 格式。請輸入有效的圖片 URL (png, jpg, jpeg, gif, webp)。", bot_user=self.bot_user)
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
                                response_embed = build_error_embed("操作失敗", "URL 指向的內容不是圖片。請確認 URL。", bot_user=self.bot_user)
                            else:
                                guild_data["leave_custom_banner_url"] = url
                                await update_guild_data(guild_id, guild_data)
                                response_embed = build_success_embed("設定成功", f"已成功設定為: [圖片連結]({url})", bot_user=self.bot_user)
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
                            response_embed = build_warning_embed("下載失敗", f"無法下載圖片。HTTP 狀態碼: {resp.status}。請檢查 URL 是否正確或可訪問。", bot_user=self.bot_user)
                except aiohttp.ClientError as e:
                    response_embed = build_error_embed("網路錯誤", f"下載圖片時發生網路錯誤: {e}。請檢查 URL。", bot_user=self.bot_user)
                except asyncio.TimeoutError:
                    response_embed = build_error_embed("下載逾時", "下載圖片逾時 (10秒)。請檢查 URL 是否有效或伺服器響應緩慢。", bot_user=self.bot_user)
                except Exception as e:
                    response_embed = build_error_embed("未知錯誤", f"下載圖片時發生未知錯誤: {e}。請檢查 URL。", bot_user=self.bot_user)
                finally:
                    if should_close_session:
                        await bot_session.close()
        elif self.target_type == "clear_leave_banner":
            if self.input.value.strip().lower() != "yes":
                response_embed = build_error_embed("操作失敗", "輸入不正確。請輸入 **'Yes'** 來確認清除操作。", bot_user=self.bot_user)
            else:
                guild_data["leave_custom_banner_url"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed = build_success_embed("操作成功", "目前使用使用者的頭像作為離開橫幅圖", bot_user=self.bot_user)
        elif self.target_type == "profile_banner":
            url = self.input.value.strip()
            if not re.match(
                r"https?://.*\.(?:png|jpg|jpeg|gif|webp)", url, re.IGNORECASE
            ):
                response_embed = build_error_embed("操作失敗", "無效的 URL 格式。請輸入有效的圖片 URL (png, jpg, jpeg, gif, webp)。", bot_user=self.bot_user)
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
                                response_embed = build_error_embed("操作失敗", "URL 指向的內容不是圖片。請確認 URL。", bot_user=self.bot_user)
                            else:
                                guild_data["profile_custom_banner_url"] = url
                                await update_guild_data(guild_id, guild_data)
                                response_embed = build_success_embed("設定成功", f"已成功設定為: [圖片連結]({url})", bot_user=self.bot_user)
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
                            response_embed = build_warning_embed("下載失敗", f"無法下載圖片。HTTP 狀態碼: {resp.status}。請檢查 URL 是否正確或可訪問。", bot_user=self.bot_user)
                except aiohttp.ClientError as e:
                    response_embed = build_error_embed("網路錯誤", f"下載圖片時發生網路錯誤: {e}。請檢查 URL。", bot_user=self.bot_user)
                except asyncio.TimeoutError:
                    response_embed = build_error_embed("下載逾時", "下載圖片逾時 (10秒)。請檢查 URL 是否有效或伺服器響應緩慢。", bot_user=self.bot_user)
                except Exception as e:
                    response_embed = build_error_embed("未知錯誤", f"下載圖片時發生未知錯誤: {e}。請檢查 URL。", bot_user=self.bot_user)
                finally:
                    if should_close_session:
                        await bot_session.close()
        elif self.target_type == "clear_profile_banner":
            if self.input.value.strip().lower() != "yes":
                response_embed = build_error_embed("操作失敗", "輸入不正確。請輸入 **'Yes'** 來確認清除操作。", bot_user=self.bot_user)
            else:
                guild_data["profile_custom_banner_url"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed = build_success_embed("操作成功", "已清除用戶檔案橫幅圖片", bot_user=self.bot_user)
        elif self.target_type == "role_selection_channel":
            channel_input = self.input.value.strip()
            if channel_input.lower() == "none":
                guild_data["role_selection_channel_id"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed = build_success_embed("設定成功", "身份組選擇`已禁用`。", bot_user=self.bot_user)
            elif not channel_input.isdigit():
                response_embed = build_error_embed("操作失敗", "頻道 ID 必須是數字或 'None'。請輸入有效的文字頻道 ID 或 'None' 禁用。", bot_user=self.bot_user)
            else:
                channel = interaction.guild.get_channel(int(channel_input))
                if not channel or not isinstance(channel, discord.TextChannel):
                    response_embed = build_error_embed("操作失敗", "找不到指定的文字頻道。請確保 ID 正確且頻道為文字頻道。", bot_user=self.bot_user)
                else:
                    guild_data["role_selection_channel_id"] = int(channel_input)
                    await update_guild_data(guild_id, guild_data)
                    response_embed = build_success_embed("設定成功", f"身份組選擇頻道已設定為: {channel.mention}", bot_user=self.bot_user)
        elif self.target_type == "manage_selectable_roles":
            role_ids_input = self.input.value.strip()
            if role_ids_input.lower() == "none":
                guild_data["selectable_roles"] = []
                await update_guild_data(guild_id, guild_data)
                response_embed = build_success_embed("設定成功", "可選身份組`已清空`。", bot_user=self.bot_user)
            else:
                role_ids = [rid.strip() for rid in role_ids_input.split(",")]
                valid_role_ids = []
                invalid_ids = []
                for role_id in role_ids:
                    if not role_id.isdigit():
                        invalid_ids.append(role_id)
                    else:
                        role = interaction.guild.get_role(int(role_id))
                        if not role or not role.is_assignable():
                            invalid_ids.append(role_id)
                        else:
                            valid_role_ids.append(int(role_id))
                if invalid_ids:
                    response_embed = build_error_embed("操作失敗", f"以下身份組 ID 無效或不可指派: {', '.join(invalid_ids)}", bot_user=self.bot_user)
                else:
                    guild_data["selectable_roles"] = valid_role_ids
                    await update_guild_data(guild_id, guild_data)
                    role_mentions = [interaction.guild.get_role(rid).mention for rid in valid_role_ids]
                    response_embed = build_success_embed("設定成功", f"可選身份組已設定為: {', '.join(role_mentions)}", bot_user=self.bot_user)
        elif self.target_type == "dvc_trigger_channel":
            channel_input = self.input.value.strip()
            if channel_input.lower() == "none":
                guild_data["dvc_trigger_channel_id"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed = build_success_embed("設定成功", "動態語音頻道`已禁用`。", bot_user=self.bot_user)
            elif not channel_input.isdigit():
                response_embed = build_error_embed("操作失敗", "頻道 ID 必須是數字或 'None'。請輸入有效的語音頻道 ID 或 'None' 禁用。", bot_user=self.bot_user)
            else:
                channel = interaction.guild.get_channel(int(channel_input))
                if not channel or not isinstance(channel, discord.VoiceChannel):
                    response_embed = build_error_embed("操作失敗", "找不到指定的語音頻道。請確保 ID 正確且頻道為語音頻道。", bot_user=self.bot_user)
                else:
                    guild_data["dvc_trigger_channel_id"] = int(channel_input)
                    await update_guild_data(guild_id, guild_data)
                    response_embed = build_success_embed("設定成功", f"觸發語音頻道已設定為: {channel.mention}", bot_user=self.bot_user)
        elif self.target_type == "dvc_category":
            category_input = self.input.value.strip()
            if category_input.lower() == "none":
                guild_data["dvc_category_id"] = None
                await update_guild_data(guild_id, guild_data)
                response_embed = build_success_embed("設定成功", "語音頻道分類`已清空`，將使用伺服器預設位置。", bot_user=self.bot_user)
            elif not category_input.isdigit():
                response_embed = build_error_embed("操作失敗", "分類 ID 必須是數字或 'None'。請輸入有效的分類 ID 或 'None' 清空。", bot_user=self.bot_user)
            else:
                category = interaction.guild.get_channel(int(category_input))
                if not category or not isinstance(category, discord.CategoryChannel):
                    response_embed = build_error_embed("操作失敗", "找不到指定的分類。請確保 ID 正確且為分類頻道。", bot_user=self.bot_user)
                else:
                    guild_data["dvc_category_id"] = int(category_input)
                    await update_guild_data(guild_id, guild_data)
                    response_embed = build_success_embed("設定成功", f"語音頻道分類已設定為: {category.name}", bot_user=self.bot_user)

        await interaction.followup.send(embed=response_embed, files=response_files, ephemeral=True)

        # Update the original message if possible
        try:
            if self.original_interaction and not self.original_interaction.response.is_done():
                await self._update_original_command_message(
                    interaction, guild_id
                )
        except Exception as e:
            logger.error(f"Modal 後更新原始消息失敗: {e}")

    async def _update_original_command_message(self, interaction, guild_id):
        """Update the original command message with current settings"""
        try:
            current_guild_data = await get_guild_data(guild_id)
            if self.parent_view:
                embed, view = self.parent_view._create_current_page(
                    current_guild_data, self.bot_user
                )
                await self.original_interaction.edit_original_response(
                    embed=embed, view=view
                )
        except Exception as e:
            logger.error(f"Failed to update original command message: {e}")


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
        self.max_pages = 5  # 6 pages (0 to 5)
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
        )
        select.callback = self.welcome_callback
        return select

    async def welcome_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]
        if selected == "toggle_welcome_image":
            guild_id = interaction.guild_id
            guild_data = await get_guild_data(guild_id)
            current_state = guild_data.get("welcome_image_enabled", True)
            guild_data["welcome_image_enabled"] = not current_state
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if not current_state else "停用"
            await interaction.response.send_message(
                embed=build_success_embed("設定成功", f"歡迎圖片生成已{status}。", bot_user=self.bot_user), ephemeral=True
            )
        elif selected == "toggle_welcome_gif":
            guild_id = interaction.guild_id
            guild_data = await get_guild_data(guild_id)
            current_state = guild_data.get("welcome_gif_enabled", True)
            guild_data["welcome_gif_enabled"] = not current_state
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if not current_state else "停用"
            await interaction.response.send_message(
                embed=build_success_embed("設定成功", f"歡迎GIF生成已{status}。", bot_user=self.bot_user), ephemeral=True
            )
        elif selected == "clear_welcome_initial_role":
            guild_id = interaction.guild_id
            guild_data = await get_guild_data(guild_id)
            guild_data["welcome_initial_role_id"] = None
            await update_guild_data(guild_id, guild_data)
            await interaction.response.send_message(
                embed=build_success_embed("設定成功", "初始身份組已清除。", bot_user=self.bot_user), ephemeral=True
            )
        else:
            modal = SettingsModal(
                target_type=selected,
                original_interaction=self.original_interaction,
                bot_user=self.bot_user,
                parent_view=self,
            )
            await interaction.response.send_modal(modal)

    def leave_select(self):
        select = Select(
            placeholder="選擇離開訊息設定...",
            options=[
                discord.SelectOption(
                    label="設定離開頻道",
                    value="leave_channel",
                    description="設定成員離開時的離開訊息頻道或禁用",
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
        select.callback = self.leave_callback
        return select

    async def leave_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]
        if selected == "toggle_leave_image":
            guild_id = interaction.guild_id
            guild_data = await get_guild_data(guild_id)
            current_state = guild_data.get("leave_image_enabled", True)
            guild_data["leave_image_enabled"] = not current_state
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if not current_state else "停用"
            await interaction.response.send_message(
                embed=build_success_embed("設定成功", f"離開圖片生成已{status}。", bot_user=self.bot_user), ephemeral=True
            )
        elif selected == "toggle_leave_gif":
            guild_id = interaction.guild_id
            guild_data = await get_guild_data(guild_id)
            current_state = guild_data.get("leave_gif_enabled", True)
            guild_data["leave_gif_enabled"] = not current_state
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if not current_state else "停用"
            await interaction.response.send_message(
                embed=build_success_embed("設定成功", f"離開GIF生成已{status}。", bot_user=self.bot_user), ephemeral=True
            )
        else:
            modal = SettingsModal(
                target_type=selected,
                original_interaction=self.original_interaction,
                bot_user=self.bot_user,
                parent_view=self,
            )
            await interaction.response.send_modal(modal)

    def profile_select(self):
        select = Select(
            placeholder="選擇用戶檔案設定...",
            options=[
                discord.SelectOption(
                    label="設定自訂橫幅圖",
                    value="profile_banner",
                    description="設定用戶檔案的自訂橫幅圖片",
                ),
                discord.SelectOption(
                    label="清除橫幅圖",
                    value="clear_profile_banner",
                    description="清除用戶檔案的自訂橫幅圖片",
                ),
            ],
        )
        select.callback = self.profile_callback
        return select

    async def profile_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]
        modal = SettingsModal(
            target_type=selected,
            original_interaction=self.original_interaction,
            bot_user=self.bot_user,
            parent_view=self,
        )
        await interaction.response.send_modal(modal)

    def role_select(self):
        select = Select(
            placeholder="選擇身份組選擇設定...",
            options=[
                discord.SelectOption(
                    label="設定身份組選擇頻道",
                    value="role_selection_channel",
                    description="設定身份組選擇面板的頻道或禁用",
                ),
                discord.SelectOption(
                    label="管理可選身份組",
                    value="manage_selectable_roles",
                    description="設定哪些身份組可供用戶選擇",
                ),
            ],
        )
        select.callback = self.role_callback
        return select

    async def role_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]
        modal = SettingsModal(
            target_type=selected,
            original_interaction=self.original_interaction,
            bot_user=self.bot_user,
            parent_view=self,
        )
        await interaction.response.send_modal(modal)

    def ban_select(self):
        select = Select(
            placeholder="選擇封禁管理設定...",
            options=[
                discord.SelectOption(
                    label="設定封禁管理頻道",
                    value="ban_channel",
                    description="設定封禁管理面板的頻道或禁用",
                ),
                discord.SelectOption(
                    label="設定封禁記錄頻道",
                    value="ban_log_channel",
                    description="設定封禁記錄的頻道或禁用",
                ),
            ],
        )
        select.callback = self.ban_callback
        return select

    async def ban_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]
        modal = SettingsModal(
            target_type=selected,
            original_interaction=self.original_interaction,
            bot_user=self.bot_user,
            parent_view=self,
        )
        await interaction.response.send_modal(modal)

    def dvc_select(self):
        select = Select(
            placeholder="選擇動態語音頻道設定...",
            options=[
                discord.SelectOption(
                    label="設定觸發語音頻道",
                    value="dvc_trigger_channel",
                    description="設定動態語音頻道的觸發頻道或禁用",
                ),
                discord.SelectOption(
                    label="設定語音頻道分類",
                    value="dvc_category",
                    description="設定動態語音頻道的分類或清空",
                ),
            ],
        )
        select.callback = self.dvc_callback
        return select

    async def dvc_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]
        modal = SettingsModal(
            target_type=selected,
            original_interaction=self.original_interaction,
            bot_user=self.bot_user,
            parent_view=self,
        )
        await interaction.response.send_modal(modal)

    async def _update_original_command_message(self, interaction, guild_id):
        """Update the original command message with current settings"""
        try:
            current_guild_data = await get_guild_data(guild_id)
            embed, view = self._create_current_page(current_guild_data, self.bot_user)
            await self.original_interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Failed to update original command message: {e}")

    def _create_current_page(self, guild_data, bot_user):
        """Create the current page embed and view based on current_page"""
        view = SettingsView(
            original_interaction=self.original_interaction, bot_user=bot_user
        )
        view.current_page = self.current_page

        if self.current_page == 0:
            # Welcome settings page
            embed = discord.Embed(
                title="⚙️ 伺服器設定面板",
                description="歡迎來到伺服器設定面板！請選擇要設定的功能。",
                color=discord.Color.blue(),
            )
            welcome_channel = (
                interaction.guild.get_channel(guild_data.get("welcome_channel_id"))
                if guild_data.get("welcome_channel_id")
                else None
            )
            welcome_image_enabled = guild_data.get("welcome_image_enabled", True)
            welcome_gif_enabled = guild_data.get("welcome_gif_enabled", True)
            welcome_initial_role = (
                interaction.guild.get_role(guild_data.get("welcome_initial_role_id"))
                if guild_data.get("welcome_initial_role_id")
                else None
            )
            welcome_banner_url = guild_data.get("welcome_custom_banner_url")
            welcome_field = (
                f"**歡迎頻道**: {welcome_channel.mention if welcome_channel else '未設定'}\n"
                f"**歡迎訊息**: {guild_data.get('welcome_message_template', '歡迎 {member} 加入 {guild}！')}\n"
                f"**圖片生成**: {'啟用' if welcome_image_enabled else '停用'}\n"
                f"**GIF生成**: {'啟用' if welcome_gif_enabled else '停用'}\n"
                f"**初始身份組**: {welcome_initial_role.mention if welcome_initial_role else '未設定'}\n"
                f"**自訂橫幅**: {'已設定' if welcome_banner_url else '使用頭像'}"
            )
            embed.add_field(name="目前設定", value=welcome_field, inline=False)
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務 | 頁面 1/6",
                icon_url=bot_user.display_avatar.url,
            )
            select = view.welcome_select()
            view.add_item(select)
        elif self.current_page == 1:
            # Leave settings page
            embed = discord.Embed(
                title="⚙️ 伺服器設定面板",
                description="離開訊息設定",
                color=discord.Color.blue(),
            )
            leave_channel = (
                interaction.guild.get_channel(guild_data.get("leave_channel_id"))
                if guild_data.get("leave_channel_id")
                else None
            )
            leave_image_enabled = guild_data.get("leave_image_enabled", True)
            leave_gif_enabled = guild_data.get("leave_gif_enabled", True)
            leave_banner_url = guild_data.get("leave_custom_banner_url")
            leave_field = (
                f"**離開頻道**: {leave_channel.mention if leave_channel else '未設定'}\n"
                f"**離開訊息**: {guild_data.get('leave_message_template', '{member} 已離開 {guild}！')}\n"
                f"**圖片生成**: {'啟用' if leave_image_enabled else '停用'}\n"
                f"**GIF生成**: {'啟用' if leave_gif_enabled else '停用'}\n"
                f"**自訂橫幅**: {'已設定' if leave_banner_url else '使用頭像'}"
            )
            embed.add_field(name="目前設定", value=leave_field, inline=False)
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務 | 頁面 2/6",
                icon_url=bot_user.display_avatar.url,
            )
            select = view.leave_select()
            view.add_item(select)
        elif self.current_page == 2:
            # Profile settings page
            embed = discord.Embed(
                title="⚙️ 伺服器設定面板",
                description="用戶檔案設定",
                color=discord.Color.blue(),
            )
            profile_banner_url = guild_data.get("profile_custom_banner_url")
            profile_field = f"**自訂橫幅**: {'已設定' if profile_banner_url else '未設定'}"
            embed.add_field(name="目前設定", value=profile_field, inline=False)
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務 | 頁面 3/6",
                icon_url=bot_user.display_avatar.url,
            )
            select = view.profile_select()
            view.add_item(select)
        elif self.current_page == 3:
            # Role selection settings page
            embed = discord.Embed(
                title="⚙️ 伺服器設定面板",
                description="身份組選擇設定",
                color=discord.Color.blue(),
            )
            role_selection_channel = (
                interaction.guild.get_channel(guild_data.get("role_selection_channel_id"))
                if guild_data.get("role_selection_channel_id")
                else None
            )
            selectable_roles = guild_data.get("selectable_roles", [])
            role_mentions = [
                interaction.guild.get_role(role_id).mention
                for role_id in selectable_roles
                if interaction.guild.get_role(role_id)
            ]
            role_field = (
                f"**身份組選擇頻道**: {role_selection_channel.mention if role_selection_channel else '未設定'}\n"
                f"**可選身份組**: {', '.join(role_mentions) if role_mentions else '未設定'}"
            )
            embed.add_field(name="目前設定", value=role_field, inline=False)
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務 | 頁面 4/6",
                icon_url=bot_user.display_avatar.url,
            )
            select = view.role_select()
            view.add_item(select)
        elif self.current_page == 4:
            # Ban management settings page
            embed = discord.Embed(
                title="⚙️ 伺服器設定面板",
                description="封禁管理設定",
                color=discord.Color.blue(),
            )
            ban_channel = (
                interaction.guild.get_channel(guild_data.get("ban_channel_id"))
                if guild_data.get("ban_channel_id")
                else None
            )
            ban_log_channel = (
                interaction.guild.get_channel(guild_data.get("ban_log_channel_id"))
                if guild_data.get("ban_log_channel_id")
                else None
            )
            ban_field = (
                f"**封禁管理頻道**: {ban_channel.mention if ban_channel else '未設定'}\n"
                f"**封禁記錄頻道**: {ban_log_channel.mention if ban_log_channel else '未設定'}"
            )
            embed.add_field(name="目前設定", value=ban_field, inline=False)
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務 | 頁面 5/6",
                icon_url=bot_user.display_avatar.url,
            )
            select = view.ban_select()
            view.add_item(select)
        elif self.current_page == 5:
            # Dynamic voice channel settings page
            embed = discord.Embed(
                title="⚙️ 伺服器設定面板",
                description="動態語音頻道設定",
                color=discord.Color.blue(),
            )
            trigger_channel = (
                interaction.guild.get_channel(guild_data.get("dvc_trigger_channel_id"))
                if guild_data.get("dvc_trigger_channel_id")
                else None
            )
            category = (
                interaction.guild.get_channel(guild_data.get("dvc_category_id"))
                if guild_data.get("dvc_category_id")
                else None
            )
            dvc_field = (
                f"**觸發語音頻道**: {trigger_channel.mention if trigger_channel else '未設定'}\n"
                f"**語音頻道分類**: {category.name if category else '未設定（使用伺服器預設位置）'}"
            )
            embed.add_field(name="目前設定", value=dvc_field, inline=False)
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務 | 頁面 6/6",
                icon_url=bot_user.display_avatar.url,
            )
            select = view.dvc_select()
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
