# bot/views/announcement_views.py
import discord
from discord.ui import Modal, TextInput, View, Select, Button
import re
import aiohttp
import asyncio
import logging
from typing import List, Optional
import os
from datetime import datetime
import csv
import io

from bot.utils.database import (
    get_guild_data,
    update_guild_data,
)
from bot.views.embed_builder import build_success_embed, build_error_embed, build_info_embed, build_warning_embed

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class AnnouncementModal(Modal):
    def __init__(
        self,
        parent_view: View,
        original_interaction: discord.Interaction = None,
        bot_user: discord.User = None,
    ):
        super().__init__(title="創建公告")
        self.parent_view = parent_view
        self.original_interaction = original_interaction
        self.bot_user = bot_user

        self.title_input = TextInput(
            label="標題",
            placeholder="輸入公告標題 (最多256字元)",
            required=True,
            max_length=256,
            style=discord.TextStyle.short,
        )
        self.description_input = TextInput(
            label="內容",
            placeholder="輸入公告內容 (最多4000字元)",
            required=True,
            max_length=4000,
            style=discord.TextStyle.paragraph,
        )
        self.color_input = TextInput(
            label="顏色 (HEX碼)",
            placeholder="輸入HEX顏色碼 (例如: #FF0000) 或留空使用預設",
            required=False,
            style=discord.TextStyle.short,
        )
        self.image_input = TextInput(
            label="圖片 URL (可選)",
            placeholder="輸入圖片URL (例如: https://example.com/image.png)",
            required=False,
            style=discord.TextStyle.short,
        )

        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.color_input)
        self.add_item(self.image_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        response_embed = discord.Embed(color=discord.Color.blue())

        # Validate color
        color_hex = self.color_input.value.strip() or "#00FF00"  # Default to green
        if not re.match(r"^#?[0-9A-Fa-f]{6}$", color_hex):
            response_embed = build_error_embed("操作失敗", "無效的HEX顏色碼。請使用格式如 #FF0000。", bot_user=self.bot_user)
            await interaction.edit_original_response(embed=response_embed, view=None)
            return

        # Validate image URL
        image_url = self.image_input.value.strip()
        if image_url:
            if not re.match(
                r"https?://.*\.(?:png|jpg|jpeg|gif|webp)", image_url, re.IGNORECASE
            ):
                response_embed = build_error_embed("操作失敗", "無效的圖片URL。請輸入有效的圖片URL (png, jpg, jpeg, gif, webp)。", bot_user=self.bot_user)
                await interaction.edit_original_response(
                    embed=response_embed, view=None
                )
                return

            # Validate image accessibility
            bot_session = getattr(interaction.client, "session", None)
            should_close_session = False
            if not isinstance(bot_session, aiohttp.ClientSession):
                bot_session = aiohttp.ClientSession()
                should_close_session = True
            try:
                async with bot_session.get(image_url, timeout=10) as resp:
                    if resp.status != 200:
                        response_embed = build_warning_embed("圖片驗證失敗", f"無法訪問圖片URL。HTTP狀態碼: {resp.status}。將繼續使用URL。", bot_user=self.bot_user)
                        await interaction.edit_original_response(
                            embed=response_embed, view=None
                        )
                        return
                    content_type = resp.headers.get("Content-Type", "").lower()
                    if not content_type.startswith("image/"):
                        response_embed = build_error_embed("操作失敗", "URL指向的內容不是圖片。請確認URL。", bot_user=self.bot_user)
                        await interaction.edit_original_response(
                            embed=response_embed, view=None
                        )
                        return
            except aiohttp.ClientError as e:
                response_embed = build_warning_embed("圖片驗證失敗", f"驗證圖片URL時發生網路錯誤: {e}。將繼續使用URL。", bot_user=self.bot_user)
                await interaction.edit_original_response(
                    embed=response_embed, view=None
                )
                return
            except asyncio.TimeoutError:
                response_embed = build_warning_embed("圖片驗證失敗", "驗證圖片URL逾時 (10秒)。將繼續使用URL。", bot_user=self.bot_user)
                await interaction.edit_original_response(
                    embed=response_embed, view=None
                )
                return
            except Exception as e:
                response_embed = build_warning_embed("圖片驗證失敗", f"驗證圖片URL時發生未知錯誤: {e}。將繼續使用URL。", bot_user=self.bot_user)
                await interaction.edit_original_response(
                    embed=response_embed, view=None
                )
                return
            finally:
                if should_close_session:
                    await bot_session.close()

        # Process color
        if color_hex.startswith("#"):
            color_hex = color_hex[1:]
        try:
            color = discord.Color(int(color_hex, 16))
        except ValueError:
            response_embed = build_error_embed("操作失敗", "無效的HEX顏色碼。請使用格式如 #FF0000。", bot_user=self.bot_user)
            await interaction.edit_original_response(embed=response_embed, view=None)
            return

        # Store announcement data
        self.parent_view.announcement_data = {
            "title": self.title_input.value.strip(),
            "description": self.description_input.value.strip(),
            "color": color,
            "image_url": image_url if image_url else None,
        }

        # Update parent view
        await self.parent_view._update_original_command_message(
            interaction, interaction.guild_id
        )

        response_embed = build_success_embed("公告創建成功", "公告內容已設定。請選擇頻道並點擊「預覽」查看效果。", bot_user=self.bot_user)
        await interaction.edit_original_response(embed=response_embed, view=None)


class ChannelSelect(Select):
    def __init__(self, guild: discord.Guild):
        self.guild = guild
        options = []
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                options.append(
                    discord.SelectOption(
                        label=channel.name,
                        value=str(channel.id),
                        description=f"ID: {channel.id}",
                    )
                )
        super().__init__(
            placeholder="選擇要發送公告的頻道...",
            min_values=1,
            max_values=len(options) if options else 1,
            options=options,
            custom_id="channel_select",
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_channel_ids = [int(value) for value in self.values]
        logger.debug(
            f"Selected channels: {self.view.selected_channel_ids}, interaction_id: {interaction.id}"
        )
        await interaction.response.defer()


class AnnouncementView(View):
    def __init__(
        self,
        original_interaction: discord.Interaction = None,
        bot_user: discord.User = None,
        guild: discord.Guild = None,
    ):
        super().__init__(timeout=180)
        self.original_interaction = original_interaction
        self.bot_user = bot_user
        self.guild = guild
        self.selected_channel_ids: List[int] = []
        self.announcement_data: Optional[dict] = None
        if original_interaction is None:
            logger.warning(
                "AnnouncementView initialized with None original_interaction"
            )
        else:
            logger.debug(
                f"AnnouncementView initialized with original_interaction: {original_interaction.id}"
            )

        # Add channel select
        if guild:
            self.add_item(ChannelSelect(guild))

        # Add buttons
        self.add_item(self.create_button())
        self.add_item(self.preview_button())
        self.add_item(self.cancel_button())

    def create_button(self):
        button = Button(label="創建公告", style=discord.ButtonStyle.primary)
        button.callback = self.create_announcement
        logger.debug(f"Created create_button: {button}")
        return button

    def preview_button(self):
        button = Button(
            label="預覽", style=discord.ButtonStyle.secondary, disabled=True
        )
        button.callback = self.preview_announcement
        logger.debug(f"Created preview_button: {button}")
        return button

    def cancel_button(self):
        button = Button(label="取消", style=discord.ButtonStyle.danger)
        button.callback = self.cancel
        logger.debug(f"Created cancel_button: {button}")
        return button

    async def create_announcement(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            AnnouncementModal(
                parent_view=self,
                original_interaction=self.original_interaction,
                bot_user=self.bot_user,
            )
        )

    async def preview_announcement(self, interaction: discord.Interaction):
        if not self.announcement_data:
            await interaction.response.send_message(
                embed=build_info_embed("尚未設定", "尚未設定公告內容。", bot_user=self.bot_user), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=self.announcement_data["title"],
            description=self.announcement_data["description"],
            color=self.announcement_data["color"],
        )
        if self.announcement_data["image_url"]:
            embed.set_image(url=self.announcement_data["image_url"])
        embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務",
            icon_url=self.bot_user.display_avatar.url,
        )

        view = ConfirmationView(
            original_interaction=self.original_interaction,
            bot_user=self.bot_user,
            announcement_data=self.announcement_data,
            selected_channel_ids=self.selected_channel_ids,
            guild=self.guild,
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_info_embed("操作取消", "公告創建已取消。", bot_user=self.bot_user), ephemeral=True)
        self.stop()

    async def _update_original_command_message(
        self, interaction: discord.Interaction, guild_id: int
    ):
        embed = discord.Embed(
            title="公告面板",
            description="選擇頻道並創建公告。使用「預覽」查看效果，然後決定是否發送。",
            color=discord.Color.blue(),
        )
        if self.selected_channel_ids:
            channels = [
                self.guild.get_channel(cid) for cid in self.selected_channel_ids
            ]
            channel_mentions = ", ".join(c.mention for c in channels if c)
            embed.add_field(name="已選頻道", value=channel_mentions, inline=False)
        if self.announcement_data:
            embed.add_field(
                name="公告狀態", value="已設定，點擊「預覽」查看。", inline=False
            )
        embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務",
            icon_url=self.bot_user.display_avatar.url,
        )

        view = self
        for item in view.children:
            if isinstance(item, Button) and item.label == "預覽":
                item.disabled = not bool(self.announcement_data)

        if self.original_interaction and self.original_interaction.message:
            try:
                logger.debug(
                    f"Updating original message, embed: {embed.title}, interaction_id: {self.original_interaction.id}"
                )
                await self.original_interaction.edit_original_response(
                    embed=embed, view=view
                )
            except discord.NotFound:
                logger.error(
                    "Original message not found, falling back to current interaction"
                )
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Failed to update with current interaction: {e}")
            except discord.Forbidden:
                logger.error("Bot lacks permissions to edit the original message")
            except Exception as e:
                logger.error(f"Unexpected error updating original message: {e}")
        else:
            logger.warning(
                f"Cannot update original message: original_interaction={self.original_interaction}, message={self.original_interaction.message if self.original_interaction else None}"
            )
            try:
                logger.debug(
                    f"Falling back to current interaction, embed: {embed.title}, interaction_id: {interaction.id}"
                )
                await interaction.edit_original_response(embed=embed, view=view)
            except discord.InteractionResponded:
                logger.debug("Interaction already responded, sending followup")
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception as e:
                logger.error(f"Failed to update with current interaction: {e}")


class ConfirmationView(View):
    def __init__(
        self,
        original_interaction: discord.Interaction,
        bot_user: discord.User,
        announcement_data: dict,
        selected_channel_ids: List[int],
        guild: discord.Guild,
    ):
        super().__init__(timeout=60)
        self.original_interaction = original_interaction
        self.bot_user = bot_user
        self.announcement_data = announcement_data
        self.selected_channel_ids = selected_channel_ids
        self.guild = guild
        self.add_item(self.send_button())
        self.add_item(self.cancel_button())

    def send_button(self):
        button = Button(label="發送", style=discord.ButtonStyle.green)
        button.callback = self.send_announcement
        return button

    def cancel_button(self):
        button = Button(label="取消", style=discord.ButtonStyle.danger)
        button.callback = self.cancel
        return button

    async def send_announcement(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=self.announcement_data["title"],
            description=self.announcement_data["description"],
            color=self.announcement_data["color"],
        )
        if self.announcement_data["image_url"]:
            embed.set_image(url=self.announcement_data["image_url"])
        embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務",
            icon_url=self.bot_user.display_avatar.url,
        )

        sent_channels = []
        failed_channels = []
        for channel_id in self.selected_channel_ids:
            channel = self.guild.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(embed=embed)
                    sent_channels.append(channel.mention)
                except discord.Forbidden:
                    failed_channels.append(f"{channel.name} (無權限)")
                except Exception as e:
                    failed_channels.append(f"{channel.name} ({str(e)})")
            else:
                failed_channels.append(f"ID {channel_id} (無效頻道)")

        # Save selected channels to database as announcement channels
        guild_data = await get_guild_data(self.guild.id)
        guild_data["announcement_channel_ids"] = self.selected_channel_ids
        await update_guild_data(self.guild.id, guild_data)
        logger.debug(
            f"Saved announcement_channel_ids: {self.selected_channel_ids} for guild_id: {self.guild.id}"
        )

        response_embed = discord.Embed(
            title="公告發送完成", color=discord.Color.green()
        )
        if sent_channels:
            response_embed.add_field(
                name="成功發送至", value=", ".join(sent_channels), inline=False
            )
        if failed_channels:
            response_embed.add_field(
                name="發送失敗", value=", ".join(failed_channels), inline=False
            )
        response_embed.add_field(
            name="公告頻道設定",
            value=f"已將以下頻道設為公告頻道: {', '.join(sent_channels) if sent_channels else '無'}",
            inline=False,
        )
        response_embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務",
            icon_url=self.bot_user.display_avatar.url,
        )

        await interaction.response.send_message(embed=response_embed, ephemeral=True)
        self.stop()

    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_info_embed("操作取消", "公告發送已取消。", bot_user=self.bot_user), ephemeral=True)
        self.stop()


class GlobalAnnouncementView(View):
    def __init__(
        self,
        original_interaction: discord.Interaction = None,
        bot_user: discord.User = None,
        bot = None,
    ):
        super().__init__(timeout=180)
        self.original_interaction = original_interaction
        self.bot_user = bot_user
        self.bot = bot
        self.announcement_data: Optional[dict] = None
        if original_interaction is None:
            logger.warning(
                "GlobalAnnouncementView initialized with None original_interaction"
            )
        else:
            logger.debug(
                f"GlobalAnnouncementView initialized with original_interaction: {original_interaction.id}"
            )

        self.add_item(self.create_button())
        self.add_item(self.preview_button())
        self.add_item(self.cancel_button())

    def create_button(self):
        button = Button(label="創建公告", style=discord.ButtonStyle.primary)
        button.callback = self.create_announcement
        return button

    def preview_button(self):
        button = Button(
            label="預覽", style=discord.ButtonStyle.secondary, disabled=True
        )
        button.callback = self.preview_announcement
        return button

    def cancel_button(self):
        button = Button(label="取消", style=discord.ButtonStyle.danger)
        button.callback = self.cancel
        return button

    async def create_announcement(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            AnnouncementModal(
                parent_view=self,
                original_interaction=self.original_interaction,
                bot_user=self.bot_user,
            )
        )

    async def preview_announcement(self, interaction: discord.Interaction):
        if not self.announcement_data:
            await interaction.response.send_message(
                embed=build_info_embed("尚未設定", "尚未設定公告內容。", bot_user=self.bot_user), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=self.announcement_data["title"],
            description=self.announcement_data["description"],
            color=self.announcement_data["color"],
        )
        if self.announcement_data["image_url"]:
            embed.set_image(url=self.announcement_data["image_url"])
        embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務",
            icon_url=self.bot_user.display_avatar.url,
        )

        view = GlobalConfirmationView(
            original_interaction=self.original_interaction,
            bot_user=self.bot_user,
            announcement_data=self.announcement_data,
            bot=self.bot,
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_info_embed("操作取消", "全局公告創建已取消。", bot_user=self.bot_user), ephemeral=True)
        self.stop()

    async def _update_original_command_message(
        self, interaction: discord.Interaction, guild_id: int
    ):
        embed = discord.Embed(
            title="全局公告面板",
            description="創建將發送至所有伺服器公告頻道的公告。使用「預覽」查看效果，然後決定是否發送。",
            color=discord.Color.blue(),
        )
        if self.announcement_data:
            embed.add_field(
                name="公告狀態", value="已設定，點擊「預覽」查看。", inline=False
            )
        embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務",
            icon_url=self.bot_user.display_avatar.url,
        )

        view = self
        for item in view.children:
            if isinstance(item, Button) and item.label == "預覽":
                item.disabled = not bool(self.announcement_data)

        if self.original_interaction and self.original_interaction.message:
            try:
                logger.debug(
                    f"Updating original message, embed: {embed.title}, interaction_id: {self.original_interaction.id}"
                )
                await self.original_interaction.edit_original_response(
                    embed=embed, view=view
                )
            except discord.NotFound:
                logger.error(
                    "Original message not found, falling back to current interaction"
                )
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Failed to update with current interaction: {e}")
            except discord.Forbidden:
                logger.error("Bot lacks permissions to edit the original message")
            except Exception as e:
                logger.error(f"Unexpected error updating original message: {e}")
        else:
            logger.warning(
                f"Cannot update original message: original_interaction={self.original_interaction}, message={self.original_interaction.message if self.original_interaction else None}"
            )
            try:
                logger.debug(
                    f"Falling back to current interaction, embed: {embed.title}, interaction_id: {interaction.id}"
                )
                await interaction.edit_original_response(embed=embed, view=view)
            except discord.InteractionResponded:
                logger.debug("Interaction already responded, sending followup")
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception as e:
                logger.error(f"Failed to update with current interaction: {e}")


class GlobalConfirmationView(View):
    def __init__(
        self,
        original_interaction: discord.Interaction,
        bot_user: discord.User,
        announcement_data: dict,
        bot,
    ):
        super().__init__(timeout=60)
        self.original_interaction = original_interaction
        self.bot_user = bot_user
        self.announcement_data = announcement_data
        self.bot = bot
        self.add_item(self.send_button())
        self.add_item(self.cancel_button())

    def send_button(self):
        button = Button(label="發送", style=discord.ButtonStyle.green)
        button.callback = self.send_announcement
        return button

    def cancel_button(self):
        button = Button(label="取消", style=discord.ButtonStyle.danger)
        button.callback = self.cancel
        return button

    async def send_announcement(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=self.announcement_data["title"],
            description=self.announcement_data["description"],
            color=self.announcement_data["color"],
        )
        if self.announcement_data["image_url"]:
            embed.set_image(url=self.announcement_data["image_url"])
        embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務",
            icon_url=self.bot_user.display_avatar.url,
        )

        success_count = 0
        fail_count = 0
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        csv_file = f"logs/global_announcements_{timestamp}.csv"

        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)

        # Initialize CSV file
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["Guild", "Status", "Channels", "Reason"])
        writer.writerow(["", "", "", f"Title: {self.announcement_data['title']}"])

        for guild in self.bot.guilds:
            guild_data = await get_guild_data(guild.id)
            announcement_channel_ids = guild_data.get("announcement_channel_ids", [])
            if not announcement_channel_ids:
                writer.writerow(
                    [guild.name, "Failed", "", "No announcement channels set"]
                )
                fail_count += 1
                continue

            sent_channels = []
            failed_channels = []
            for channel_id in announcement_channel_ids:
                channel = guild.get_channel(channel_id)
                if (
                    channel
                    and isinstance(channel, discord.TextChannel)
                    and channel.permissions_for(guild.me).send_messages
                ):
                    try:
                        await channel.send(embed=embed)
                        sent_channels.append(channel.name)
                    except discord.Forbidden:
                        failed_channels.append(f"{channel.name} (No permissions)")
                    except Exception as e:
                        failed_channels.append(f"{channel.name} ({str(e)})")
                else:
                    failed_channels.append(f"ID {channel_id} (Invalid channel)")

            if sent_channels:
                success_count += 1
                writer.writerow([guild.name, "Success", ", ".join(sent_channels), ""])
            if failed_channels:
                fail_count += 1
                writer.writerow([guild.name, "Failed", "", ", ".join(failed_channels)])

        # Save CSV to disk for debugging
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            f.write(csv_buffer.getvalue())
        csv_buffer.seek(0)

        # Create Discord file attachment
        file = discord.File(
            fp=io.BytesIO(csv_buffer.getvalue().encode("utf-8")),
            filename=f"global_announcements_{timestamp}.csv",
        )

        response_embed = discord.Embed(
            title="全局公告發送完成", color=discord.Color.green()
        )
        response_embed.add_field(
            name="成功發送伺服器數",
            value=str(success_count),
            inline=True,
        )
        response_embed.add_field(
            name="發送失敗伺服器數",
            value=str(fail_count),
            inline=True,
        )
        response_embed.set_footer(
            text=f"由 {self.bot_user.display_name} 提供服務",
            icon_url=self.bot_user.display_avatar.url,
        )

        await interaction.response.send_message(
            embed=response_embed, file=file, ephemeral=True
        )
        logger.debug(
            f"Global announcement sent: {success_count} successes, {fail_count} failures, CSV attached, interaction_id: {interaction.id}"
        )
        csv_buffer.close()
        self.stop()

    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_info_embed("操作取消", "全局公告發送已取消。", bot_user=self.bot_user), ephemeral=True)
        self.stop()
