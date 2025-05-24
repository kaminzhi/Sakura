import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Select
import re
import io
import aiohttp
import asyncio

from bot.utils.database import get_guild_data, update_guild_data


class URLInputModal(Modal):
    def __init__(
        self,
        target_type: str,
        current_value: str = None,
        original_interaction: discord.Interaction = None,
        bot_user: discord.User = None,
        parent_view: View = None,  # Added to access _update_original_command_message
    ):
        modal_title = ""
        if target_type == "banner":
            modal_title = "設定橫幅圖片 URL"
        elif target_type == "clear_banner":
            modal_title = "確認清除橫幅圖片"

        super().__init__(title=modal_title)

        self.target_type = target_type
        self.original_interaction = original_interaction
        self.bot_user = bot_user
        self.parent_view = parent_view  # Store the parent view

        if target_type == "banner":
            self.image_url_input = TextInput(
                label="圖片 URL",
                placeholder="輸入圖片的 URL (例如: https://example.com/image.png)",
                required=True,
                style=discord.TextStyle.short,
            )
            if current_value:
                self.image_url_input.default = current_value
            self.add_item(self.image_url_input)
        elif target_type == "clear_banner":
            self.confirm_clear_text_input = TextInput(
                label="輸入 'Yes' 以清除橫幅",
                placeholder="輸入 'Yes'",
                required=True,
                style=discord.TextStyle.short,
            )
            self.add_item(self.confirm_clear_text_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild_id
        guild_data = await get_guild_data(guild_id)

        response_embed = discord.Embed(color=discord.Color.blue())
        response_files = []

        if self.target_type == "clear_banner":
            if self.confirm_clear_text_input.value.strip().lower() != "yes":
                response_embed.title = "❌ 操作失敗"
                response_embed.description = (
                    "輸入不正確。請輸入 **'Yes'** 來確認清除操作。"
                )
                response_embed.color = discord.Color.red()
            else:
                guild_data["custom_banner_url"] = None
                await update_guild_data(guild_id, guild_data)

                response_embed.title = "✅ 操作成功"
                response_embed.description = "目前使用使用者的頭像作爲背景圖"
                response_embed.color = discord.Color.green()

        elif self.target_type == "banner":
            url = self.image_url_input.value.strip()

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
                    # Fallback for when bot.session isn't set up
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

        response_embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務",
            icon_url=self.bot_user.display_avatar.url,
        )

        await interaction.edit_original_response(
            embed=response_embed, attachments=response_files
        )

        # Update the original command message after any action
        if self.parent_view:
            await self.parent_view._update_original_command_message(
                interaction, guild_id
            )


class ImageSettingsView(View):
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
        placeholder="選擇要設定的模式...",
        options=[
            discord.SelectOption(
                label="設定自訂的橫幅圖",
                value="banner",
                description="設定自訂的橫幅圖片",
            ),
            discord.SelectOption(
                label="設定用使用者頭像作為橫幅圖",  # Changed description
                value="clear_banner",
                description="將使用者頭像做為橫幅圖片",
            ),
            discord.SelectOption(
                label="切換動態/靜態圖片生成",
                value="toggle_gif",
                description="啟用或停用動態 (GIF) 圖片生成",
            ),
        ],
    )
    async def select_image_type(self, interaction: discord.Interaction, select: Select):
        selected_value = select.values[0]
        guild_id = interaction.guild_id
        guild_data = await get_guild_data(guild_id)

        if selected_value == "toggle_gif":
            await interaction.response.defer(ephemeral=True)

            current_gif_setting = guild_data.get("generate_gif_profile_image", True)
            new_gif_setting = not current_gif_setting
            guild_data["generate_gif_profile_image"] = new_gif_setting
            await update_guild_data(guild_id, guild_data)

            status = "啟用" if new_gif_setting else "停用"
            response_embed = discord.Embed(
                title="✅ 設定已更新",
                description=f"動態圖片生成已 **{status}**。",
                color=discord.Color.green(),
            )
            response_embed.set_footer(
                text=f"由 {self.bot_user.display_name} 提供服務",
                icon_url=self.bot_user.display_avatar.url,
            )
            await interaction.edit_original_response(embed=response_embed)

        elif selected_value == "clear_banner":
            await interaction.response.send_modal(
                URLInputModal(
                    "clear_banner",
                    original_interaction=self.original_interaction,
                    bot_user=self.bot_user,
                    parent_view=self,  # Pass self as parent_view
                )
            )
            return

        elif selected_value == "banner":
            current_value = guild_data.get("custom_banner_url")
            await interaction.response.send_modal(
                URLInputModal(
                    "banner",
                    current_value,
                    self.original_interaction,
                    self.bot_user,
                    parent_view=self,  # Pass self as parent_view
                )
            )
            return

        # Update the original command message after any action (except modals, which handle it in on_submit)
        if selected_value != "banner" and selected_value != "clear_banner":
            await self._update_original_command_message(interaction, guild_id)

    async def _update_original_command_message(
        self, interaction: discord.Interaction, guild_id: int
    ):
        """
        Helper method to update the original command message (the one with the select menu)
        after any setting has been changed.
        """
        if self.original_interaction and self.original_interaction.message:
            try:
                updated_guild_data = await get_guild_data(guild_id)
                original_command_embed = self._create_profile_image_embed(
                    updated_guild_data, self.bot_user
                )

                # Re-send the view to ensure it stays active
                await self.original_interaction.edit_original_response(
                    embed=original_command_embed,
                    view=ImageSettingsView(  # Re-instantiate the view
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

    def _create_profile_image_embed(self, guild_data: dict, bot_user: discord.User):
        """
        Helper method to create the embed for the profile image settings.
        Centralizes embed creation logic.
        """
        embed = discord.Embed(
            title="🖼️ 個人資料圖片設定",
            description="請使用下方的選單來設定自訂橫幅的圖片 URL 或動態/靜態圖片生成。",
            color=discord.Color.blue(),
        )

        current_banner_url = guild_data.get("custom_banner_url")
        generate_gif_enabled = guild_data.get("generate_gif_profile_image", True)

        field_value = ""
        if current_banner_url:
            field_value = f"目前圖片：[圖片連結]({current_banner_url})"
            embed.set_image(url=current_banner_url)
        else:
            field_value = "目前使用使用者的頭像作爲背景圖"
            embed.set_image(url=None)

        gif_status = "啟用" if generate_gif_enabled else "停用"
        field_value += f"\n動態圖片生成: {gif_status}"

        embed.add_field(name="目前設定", value=field_value, inline=False)

        if bot_user:
            embed.set_footer(
                text=f"由 {bot_user.display_name} 提供服務",
                icon_url=bot_user.display_avatar.url,
            )
        return embed


class EmbedManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="set-profile-images", description="管理自訂個人資料橫幅圖片"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def set_profile_images(self, interaction: discord.Interaction):
        current_guild_data = await get_guild_data(interaction.guild_id)

        # Use the centralized embed creation method
        embed = ImageSettingsView(
            original_interaction=interaction, bot_user=self.bot.user
        )._create_profile_image_embed(current_guild_data, self.bot.user)

        view = ImageSettingsView(
            original_interaction=interaction, bot_user=self.bot.user
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedManager(bot))
