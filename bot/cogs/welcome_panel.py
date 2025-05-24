# bot/cogs/welcome_panel.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Select
import re
import io
import aiohttp
import asyncio

from bot.utils.database import get_guild_data, update_guild_data


class WelcomeSettingsModal(Modal):
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
            "welcome_banner": "設定歡迎橫幅圖片 URL",
            "clear_welcome_banner": "確認清除歡迎橫幅圖片",
            "welcome_initial_role": "設定初始身份組",  # New: Modal for initial role
        }.get(target_type, "設定歡迎選項")

        super().__init__(title=modal_title)
        self.target_type = target_type
        self.original_interaction = original_interaction
        self.bot_user = bot_user
        self.parent_view = parent_view

        if target_type == "welcome_channel":
            self.input = TextInput(
                label="頻道 ID",
                placeholder="輸入文字頻道的 ID (例如: 123456789012345678)",
                required=True,
                style=discord.TextStyle.short,
            )
            if current_value:
                self.input.default = current_value
            self.add_item(self.input)
        elif target_type == "welcome_message":
            self.input = TextInput(
                label="歡迎訊息模板",
                placeholder="輸入訊息模板 (使用 {member} 和 {guild} 作為佔位符)",
                required=True,
                style=discord.TextStyle.paragraph,
                default="歡迎 {member} 加入 {guild}！"
                if not current_value
                else current_value,
            )
            self.add_item(self.input)
        elif target_type == "welcome_banner":
            self.input = TextInput(
                label="圖片 URL",
                placeholder="輸入圖片的 URL (例如: https://example.com/image.png)",
                required=True,
                style=discord.TextStyle.short,
            )
            if current_value:
                self.input.default = current_value
            self.add_item(self.input)
        elif target_type == "clear_welcome_banner":
            self.input = TextInput(
                label="輸入 'Yes' 以清除橫幅",
                placeholder="輸入 'Yes'",
                required=True,
                style=discord.TextStyle.short,
            )
            self.add_item(self.input)
        elif target_type == "welcome_initial_role":
            self.input = TextInput(
                label="身份組 ID",
                placeholder="輸入身份組的 ID (例如: 123456789012345678)",
                required=True,
                style=discord.TextStyle.short,
            )
            if current_value:
                self.input.default = current_value
            self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        guild_data = await get_guild_data(guild_id)
        response_embed = discord.Embed(color=discord.Color.blue())
        response_files = []

        if self.target_type == "welcome_channel":
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
                    guild_data["welcome_channel_id"] = int(channel_id)
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
                response_embed.description = "目前使用使用者的頭像作爲歡迎橫幅圖"
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


class WelcomeSettingsView(View):
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
        placeholder="選擇要設定的歡迎選項...",
        options=[
            discord.SelectOption(
                label="設定歡迎頻道",
                value="welcome_channel",
                description="設定新成員加入時的歡迎訊息頻道",
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
                label="設定初始身份組",  # New: Option for initial role
                value="welcome_initial_role",
                description="設定新成員加入時自動指派的身份組",
            ),
            discord.SelectOption(
                label="清除初始身份組",  # New: Option to clear initial role
                value="clear_welcome_initial_role",
                description="移除自動指派的初始身份組",
            ),
        ],
    )
    async def select_welcome_option(
        self, interaction: discord.Interaction, select: Select
    ):
        selected_value = select.values[0]
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
            await interaction.edit_original_response(embed=response_embed)
        elif selected_value == "toggle_welcome_gif":
            await interaction.response.defer(ephemeral=True)
            current_gif_setting = guild_data.get("welcome_generate_gif", True)
            new_gif_setting = not current_gif_setting
            guild_data["welcome_generate_gif"] = new_gif_setting
            await update_guild_data(guild_id, guild_data)
            status = "啟用" if new_gif_setting else "停用"
            response_embed = discord.Embed(
                title="✅ 設定已更新",
                description=f"歡迎訊息GIF生成已 **{status}**。",
                color=discord.Color.green(),
            )
            response_embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務",
                icon_url=self.bot_user.display_avatar.url,
            )
            await interaction.edit_original_response(embed=response_embed)
        elif selected_value == "welcome_channel":
            current_value = str(guild_data.get("welcome_channel_id", ""))
            await interaction.response.send_modal(
                WelcomeSettingsModal(
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
                WelcomeSettingsModal(
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
                WelcomeSettingsModal(
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
                WelcomeSettingsModal(
                    "clear_welcome_banner",
                    original_interaction=self.original_interaction,
                    bot_user=self.bot_user,
                    parent_view=self,
                )
            )
            return
        elif selected_value == "welcome_initial_role":
            current_value = str(guild_data.get("welcome_initial_role_id", ""))
            await interaction.response.send_modal(
                WelcomeSettingsModal(
                    "welcome_initial_role",
                    current_value,
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,
                )
            )
            return
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
            await interaction.edit_original_response(embed=response_embed)

        if selected_value not in [
            "welcome_channel",
            "welcome_message",
            "welcome_banner",
            "clear_welcome_banner",
            "welcome_initial_role",
        ]:
            await self._update_original_command_message(interaction, guild_id)

    async def _update_original_command_message(
        self, interaction: discord.Interaction, guild_id: int
    ):
        if self.original_interaction and self.original_interaction.message:
            try:
                updated_guild_data = await get_guild_data(guild_id)
                original_command_embed = self._create_welcome_settings_embed(
                    updated_guild_data, self.bot_user
                )
                await self.original_interaction.edit_original_response(
                    embed=original_command_embed,
                    view=WelcomeSettingsView(
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

    def _create_welcome_settings_embed(self, guild_data: dict, bot_user: discord.User):
        embed = discord.Embed(
            title="📬 歡迎訊息設定",
            description="請使用下方的選單來設定歡迎頻道、訊息模板、圖片生成、GIF生成、自訂橫幅或初始身份組。",
            color=discord.Color.blue(),
        )
        welcome_channel_id = guild_data.get("welcome_channel_id")
        welcome_message_template = guild_data.get("welcome_message_template", "未設定")
        welcome_image_enabled = guild_data.get("welcome_image_enabled", True)
        welcome_generate_gif = guild_data.get("welcome_generate_gif", True)
        welcome_custom_banner_url = guild_data.get("welcome_custom_banner_url")
        welcome_initial_role_id = guild_data.get(
            "welcome_initial_role_id"
        )  # New: Get initial role ID

        field_value = (
            f"歡迎頻道: {welcome_channel_id if welcome_channel_id else '未設定'}"
        )
        field_value += f"\n訊息模板: `{welcome_message_template}`"
        field_value += f"\n圖片生成: {'啟用' if welcome_image_enabled else '停用'}"
        field_value += f"\nGIF生成: {'啟用' if welcome_generate_gif else '停用'}"
        if welcome_custom_banner_url:
            field_value += f"\n自訂橫幅: [圖片連結]({welcome_custom_banner_url})"
            embed.set_image(url=welcome_custom_banner_url)
        else:
            field_value += f"\n自訂橫幅: 使用使用者頭像"
            embed.set_image(url=None)
        field_value += f"\n初始身份組: {welcome_initial_role_id if welcome_initial_role_id else '未設定'}"
        embed.add_field(name="目前設定", value=field_value, inline=False)

        if bot_user:
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務",
                icon_url=bot_user.display_avatar.url,
            )
        return embed


class WelcomeManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="set-welcome-settings", description="管理歡迎訊息設定")
    @app_commands.default_permissions(manage_guild=True)
    async def set_welcome_settings(self, interaction: discord.Interaction):
        current_guild_data = await get_guild_data(interaction.guild_id)
        embed = WelcomeSettingsView(
            original_interaction=interaction, bot_user=self.bot.user
        )._create_welcome_settings_embed(current_guild_data, self.bot.user)
        view = WelcomeSettingsView(
            original_interaction=interaction, bot_user=self.bot.user
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeManager(bot))
