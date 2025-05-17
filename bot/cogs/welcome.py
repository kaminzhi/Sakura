import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
import random
from datetime import datetime, timezone
from ..utils import redis_manager
from ..utils import checks
import logging

# 取得一個 logger 實例
logger = logging.getLogger(__name__)

redis_client = redis_manager.get_redis_client()


def get_time_greeting():
    now = datetime.now(timezone.utc)
    hour = now.hour
    time_map = {
        (0, 6): "凌晨",
        (6, 12): "早上",
        (12, 13): "中午",
        (13, 18): "下午",
        (18, 24): "半夜",
    }
    for (start, end), greeting in time_map.items():
        if start <= hour < end:
            return greeting
    return "半夜"  # 預設值


class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 配置 logger (如果還沒有在其他地方配置)
        if not logger.hasHandlers():
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
            )

    class WelcomeMessageModal(ui.Modal, title="設定歡迎訊息"):
        def __init__(self, welcome_view):
            super().__init__()
            self.welcome_view = welcome_view
            self.welcome_message = ui.TextInput(
                label="歡迎訊息",
                style=discord.TextStyle.paragraph,
                placeholder="輸入文字可含 {user} {server}",
                required=False,
            )
            self.add_item(self.welcome_message)

        async def on_submit(self, interaction: discord.Interaction):
            redis_client.set(
                f"server:{interaction.guild_id}:welcome_message",
                self.welcome_message.value,
            )
            await interaction.response.send_message("✅ 歡迎訊息已更新", ephemeral=True)

    #            await interaction.message.delete()

    #            await self.welcome_view.remove_embed(interaction)
    #            await interaction.edit_original_response(view=self.welcome_view)

    class WelcomeTitleModal(ui.Modal, title="設定歡迎標題"):
        def __init__(self, welcome_view):
            super().__init__()
            self.welcome_view = welcome_view
            self.welcome_title = ui.TextInput(
                label="歡迎標題",
                placeholder="輸入歡迎訊息的標題 (可含 {user} {server})",
                required=False,
            )
            self.add_item(self.welcome_title)

        async def on_submit(self, interaction: discord.Interaction):
            redis_client.set(
                f"server:{interaction.guild_id}:welcome_title", self.welcome_title.value
            )
            await interaction.response.send_message("✅ 歡迎標題已更新", ephemeral=True)

    class WelcomeChannelSelect(ui.Select):
        def __init__(self, bot, current_channel_id: int = None):
            self.bot = bot
            options = [
                discord.SelectOption(
                    label="無 (關閉歡迎訊息)",
                    value="none",
                    default=current_channel_id is None,
                )
            ]
            guild = self.bot.get_guild(
                int(list(self.bot.guilds)[0].id)
            )  # Assuming in a guild
            if guild:
                for channel in guild.text_channels:
                    options.append(
                        discord.SelectOption(
                            label=f"#{channel.name}",
                            value=str(channel.id),
                            default=current_channel_id == channel.id,
                        )
                    )
            super().__init__(
                placeholder="選擇歡迎頻道",
                min_values=1,
                max_values=1,
                options=options,
            )

        async def callback(self, interaction: discord.Interaction):
            selected_value = self.values[0]
            if selected_value == "none":
                redis_client.delete(f"server:{interaction.guild_id}:welcome_channel")
                await interaction.response.send_message(
                    "✅ 歡迎訊息已關閉。", ephemeral=True
                )
            else:
                redis_client.set(
                    f"server:{interaction.guild_id}:welcome_channel", selected_value
                )
                channel = self.bot.get_channel(int(selected_value))
                if channel:
                    await interaction.response.send_message(
                        f"✅ 歡迎頻道已設定為 {channel.mention}", ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "⚠️ 無法找到該頻道，但設定已儲存。", ephemeral=True
                    )

    class RandomImageToggle(ui.Select):
        def __init__(self, current_random_state: bool):
            options = [
                discord.SelectOption(
                    label="啟用", value="True", default=current_random_state
                ),
                discord.SelectOption(
                    label="禁用", value="False", default=not current_random_state
                ),
            ]
            super().__init__(
                placeholder="切換隨機圖片",
                min_values=1,
                max_values=1,
                options=options,
            )

        async def callback(self, interaction: discord.Interaction):
            selected_value = self.values[0]
            redis_client.set(
                f"server:{interaction.guild_id}:random_image", selected_value
            )
            await interaction.response.send_message(
                f"✅ 隨機圖片已{'啟用' if selected_value == 'True' else '禁用'}",
                ephemeral=True,
            )
            await self.view.update_embed(interaction)

    class WelcomeSettingsView(ui.View):
        def __init__(
            self,
            bot,
            current_channel_id: int = None,
            current_random_state: bool = False,
        ):
            super().__init__(timeout=300)
            self.bot = bot
            self.channel_select = WelcomeCog.WelcomeChannelSelect(
                bot, current_channel_id
            )
            self.random_toggle = WelcomeCog.RandomImageToggle(current_random_state)
            self.welcome_message_modal = WelcomeCog.WelcomeMessageModal(
                self
            )  # 傳遞自身引用
            self.welcome_title_modal = WelcomeCog.WelcomeTitleModal(
                self
            )  # 傳遞自身引用

            self.add_item(self.channel_select)
            self.add_item(self.random_toggle)

        async def update_embed(self, interaction: discord.Interaction):
            guild_id = interaction.guild_id
            welcome_channel_id_bytes = redis_client.get(
                f"server:{guild_id}:welcome_channel"
            )
            welcome_channel = None
            if welcome_channel_id_bytes:
                try:
                    if isinstance(welcome_channel_id_bytes, bytes):
                        welcome_channel_id = int(welcome_channel_id_bytes.decode())
                    elif isinstance(welcome_channel_id_bytes, str):
                        welcome_channel_id = int(welcome_channel_id_bytes)
                    else:
                        welcome_channel_id = None  # Handle unexpected type
                    if welcome_channel_id is not None:
                        welcome_channel = self.bot.get_channel(welcome_channel_id)
                    else:
                        welcome_channel = "設定錯誤"  # 處理 Redis 中儲存了無效 ID
                except ValueError:
                    welcome_channel = "設定錯誤"  # 處理 Redis 中儲存了無效 ID
            welcome_channel_mention = (
                welcome_channel.mention
                if isinstance(welcome_channel, discord.TextChannel)
                else "未設定"
            )

            random_image_raw = redis_client.get(f"server:{guild_id}:random_image")
            random_enabled = random_image_raw == b"True" or random_image_raw == "True"
            welcome_message_preview_raw = redis_client.get(
                f"server:{guild_id}:welcome_message"
            )
            welcome_message_preview = "未設定"
            if isinstance(welcome_message_preview_raw, bytes):
                welcome_message_preview = (
                    welcome_message_preview_raw.decode()[:50] + "..."
                )
            elif isinstance(welcome_message_preview_raw, str):
                welcome_message_preview = welcome_message_preview_raw[:50] + "..."

            welcome_title_preview_raw = redis_client.get(
                f"server:{guild_id}:welcome_title"
            )
            welcome_title_preview = "未設定"
            if isinstance(welcome_title_preview_raw, bytes):
                welcome_title_preview = welcome_title_preview_raw.decode()[:50] + "..."
            elif isinstance(welcome_title_preview_raw, str):
                welcome_title_preview = welcome_title_preview_raw[:50] + "..."

            embed = discord.Embed(title="歡迎訊息設定", color=discord.Color.blurple())
            embed.description = "請在下方選擇要設定的項目並預覽效果。"
            embed.add_field(
                name="歡迎頻道",
                value=welcome_channel_mention,
                inline=False,
            )
            embed.add_field(
                name="隨機圖片",
                value="啟用" if random_enabled else "禁用",
                inline=False,
            )
            embed.add_field(
                name="歡迎訊息預覽", value=welcome_message_preview, inline=False
            )
            embed.add_field(
                name="歡迎標題預覽", value=welcome_title_preview, inline=False
            )

            await interaction.edit_original_response(embed=embed, view=self)

        async def disable_items(self):
            for item in self.children:
                item.disabled = True
            await self.update()

        async def on_timeout(self):
            await self.disable_items()

        async def update(self):
            if self.message:
                await self.message.edit(view=self)

        async def on_message(self, message):
            self.message = message

        @ui.button(
            label="設定歡迎訊息",
            custom_id="set_welcome_message_button",
            style=discord.ButtonStyle.secondary,
        )
        async def set_message_callback(
            self, interaction: discord.Interaction, button: ui.Button
        ):
            await interaction.response.send_modal(self.welcome_message_modal)

        @ui.button(
            label="設定歡迎標題",
            custom_id="set_welcome_title_button",
            style=discord.ButtonStyle.secondary,
        )
        async def set_title_callback(
            self, interaction: discord.Interaction, button: ui.Button
        ):
            await interaction.response.send_modal(self.welcome_title_modal)

        @ui.button(
            label="預覽",
            custom_id="preview_welcome_message_button",
            style=discord.ButtonStyle.primary,
        )
        async def preview_callback(
            self, interaction: discord.Interaction, button: ui.Button
        ):
            guild_id = interaction.guild_id
            welcome_channel_id_bytes = redis_client.get(
                f"server:{guild_id}:welcome_channel"
            )
            default_role_id = redis_client.get(f"server:{guild_id}:default_role")
            welcome_message_raw = redis_client.get(f"server:{guild_id}:welcome_message")
            welcome_title_bytes = redis_client.get(f"server:{guild_id}:welcome_title")
            image_urls_bytes = redis_client.lrange(
                f"server:{guild_id}:welcome_images", 0, -1
            )
            image_urls = [
                url.decode() if isinstance(url, bytes) else url
                for url in image_urls_bytes
            ]
            random_image_raw = redis_client.get(f"server:{guild_id}:random_image")
            use_random_image = random_image_raw == b"True" or random_image_raw == "True"

            if not welcome_message_raw:
                await interaction.response.send_message(
                    "尚未設定歡迎訊息，無法預覽。", ephemeral=True
                )
                return

            embed = discord.Embed(color=discord.Color.random())
            if welcome_title_bytes:
                welcome_title = welcome_title_bytes
                if isinstance(welcome_title_bytes, bytes):
                    welcome_title = welcome_title_bytes.decode()
                embed.title = welcome_title.format(
                    user=interaction.user.name, server=interaction.guild.name
                )
            else:
                embed.title = f"歡迎 {interaction.user.name} 加入 {interaction.guild.name}！"  # 預設標題

            welcome_message = welcome_message_raw
            if isinstance(welcome_message_raw, bytes):
                welcome_message = welcome_message_raw.decode()
            embed.description = welcome_message.format(
                user=interaction.user.mention, server=interaction.guild.name
            )

            if image_urls:
                if use_random_image and image_urls:
                    embed.set_image(url=random.choice(image_urls))
                elif image_urls:
                    embed.set_image(url=image_urls[0])

            embed.set_thumbnail(
                url=interaction.user.avatar.url
                if interaction.user.avatar
                else interaction.user.default_avatar.url
            )

            now = datetime.now(timezone.utc).strftime("%H:%M")
            embed.set_footer(
                text=f"{get_time_greeting()} {now}",
                icon_url=self.bot.user.avatar.url,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="welcome-settings", description="設定歡迎相關功能")
    @checks.is_guild_admin()
    async def welcome_settings_command(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        old_settings_message_id_bytes = redis_client.get(
            f"server:{guild_id}:welcome_settings_message_id"
        )

        logger.info(
            f"[{guild_id}] 嘗試刪除舊設定 Embed，Redis 值 (bytes): {old_settings_message_id_bytes}"
        )

        # 嘗試刪除舊的設定訊息
        if old_settings_message_id_bytes:
            if isinstance(old_settings_message_id_bytes, bytes):
                try:
                    old_settings_message_id = int(
                        old_settings_message_id_bytes.decode()
                    )
                    channel = interaction.channel
                    try:
                        old_message = await channel.fetch_message(
                            old_settings_message_id
                        )
                        await old_message.delete()
                        redis_client.delete(
                            f"server:{guild_id}:welcome_settings_message_id"
                        )  # 刪除舊的 ID
                        logger.info(
                            f"[{guild_id}] 成功刪除舊設定 Embed，ID: {old_settings_message_id}"
                        )
                    except discord.NotFound:
                        logger.warning(
                            f"[{guild_id}] 警告：找不到舊的歡迎設定訊息 {old_settings_message_id}"
                        )
                    except discord.Forbidden:
                        await interaction.response.send_message(
                            "❌ Bot 沒有刪除舊設定訊息的權限。", ephemeral=True
                        )
                        logger.error(
                            f"[{guild_id}] 錯誤：Bot 沒有刪除舊設定 Embed ({old_settings_message_id}) 的權限。"
                        )
                    except Exception as e:
                        logger.error(
                            f"[{guild_id}] 刪除舊設定 Embed ({old_settings_message_id}) 時發生錯誤: {e}"
                        )
                except ValueError:
                    logger.warning(
                        f"[{guild_id}] 警告：儲存的舊歡迎設定訊息 ID ({old_settings_message_id_bytes}) 無效。"
                    )
            else:
                logger.warning(
                    f"[{guild_id}] 警告：舊歡迎設定訊息 ID 的格式不正確 (不是 bytes): {old_settings_message_id_bytes}"
                )
        else:
            logger.info(f"[{guild_id}] 沒有找到儲存的舊歡迎訊息設定 Embed ID。")

        current_channel_id_bytes = redis_client.get(
            f"server:{guild_id}:welcome_channel"
        )
        current_channel_id = None
        if current_channel_id_bytes:
            if isinstance(current_channel_id_bytes, bytes):
                try:
                    current_channel_id = int(current_channel_id_bytes.decode())
                except ValueError:
                    pass  # Redis 中儲存了無效 ID
            elif isinstance(current_channel_id_bytes, str):
                try:
                    current_channel_id = int(current_channel_id_bytes)
                except ValueError:
                    pass

        random_image_raw = redis_client.get(f"server:{guild_id}:random_image")
        current_random_state = random_image_raw == b"True" or random_image_raw == "True"

        embed = discord.Embed(title="歡迎訊息設定", color=discord.Color.blurple())
        embed.description = "請在下方選擇要設定的項目並預覽效果。"
        embed.set_footer(icon_url=self.bot.user.avatar.url, text=self.bot.user.name)

        view = self.WelcomeSettingsView(
            self.bot, current_channel_id, current_random_state
        )
        response = await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )
        await view.on_message(await interaction.original_response())
        redis_client.set(
            f"server:{guild_id}:welcome_settings_message_id",
            str(response.id).encode("utf-8"),
        )
        logger.info(
            f"[{guild_id}] 已儲存新的設定 Embed ID: {response.id} (儲存為 bytes)"
        )

    @app_commands.command(name="add-welcome-image-file", description="新增歡迎圖片")
    @checks.is_guild_admin()
    async def add_welcome_image(
        self, interaction: discord.Interaction, image: discord.Attachment
    ):
        if not image.content_type.startswith("image/"):
            await interaction.response.send_message("請上傳圖片檔案！", ephemeral=True)
            return
        image_url = image.url
        redis_client.rpush(
            f"server:{interaction.guild_id}:welcome_images", image_url.encode("utf-8")
        )
        await interaction.response.send_message(
            f"歡迎圖片已新增：{image_url}", ephemeral=True
        )

    @app_commands.command(name="add-welcome-image-url", description="新增歡迎圖片 URL")
    @checks.is_guild_admin()
    async def add_welcome_image_url(
        self, interaction: discord.Interaction, image_url: str
    ):
        if not image_url.startswith("http"):
            await interaction.response.send_message(
                "請提供有效的圖片 URL！", ephemeral=True
            )
            return
        redis_client.rpush(
            f"server:{interaction.guild_id}:welcome_images", image_url.encode("utf-8")
        )
        await interaction.response.send_message(
            f"歡迎圖片已新增：{image_url}", ephemeral=True
        )

    @app_commands.command(
        name="remove-welcome-image", description="移除歡迎圖片 (使用 ID)"
    )
    @checks.is_guild_admin()
    async def remove_welcome_image(
        self, interaction: discord.Interaction, image_id: int
    ):
        images_bytes = redis_client.lrange(
            f"server:{interaction.guild.id}:welcome_images", 0, -1
        )
        images = [
            url.decode() if isinstance(url, bytes) else url for url in images_bytes
        ]
        if 0 <= image_id < len(images):
            removed_image = redis_client.lrem(
                f"server:{interaction.guild.id}:welcome_images",
                1,
                images_bytes[image_id]
                if isinstance(images_bytes[image_id], bytes)
                else images_bytes[image_id],
            )
            removed_url = images[image_id]
            if removed_image > 0:
                await interaction.response.send_message(
                    f"已移除歡迎圖片 (ID: {image_id})：{removed_url}",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"找不到 ID 為 {image_id} 的圖片。", ephemeral=True
                )
        else:
            await interaction.response.send_message(
                f"無效的圖片 ID，請輸入 0 到 {len(images) - 1} 之間的數字。",
                ephemeral=True,
            )

    @app_commands.command(
        name="list-welcome-images",
        description="列出目前儲存的歡迎圖片 URL 清單 (帶 ID)",
    )
    @checks.is_guild_admin()
    async def list_welcome_images(self, interaction: discord.Interaction):
        images = redis_client.lrange(
            f"server:{interaction.guild_id}:welcome_images", 0, -1
        )

        embed = discord.Embed(title="歡迎圖片列表", color=discord.Color.blue())

        if images:
            embed.description = "以下是目前儲存的圖片："
            for index, url in enumerate(images):
                embed.add_field(
                    name=f"ID: {index}",
                    value=f"{url.decode() if isinstance(url, bytes) else url}",
                    inline=False,
                )
        else:
            embed.description = "目前沒有設定任何圖片"

        embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="preview-welcome-message",
        description="預覽歡迎訊息 + 圖片 + 標題 + Footer",
    )
    async def preview_welcome_message(self, interaction: discord.Interaction):
        welcome_message_raw = redis_client.get(
            f"server:{interaction.guild_id}:welcome_message"
        )
        welcome_message = (
            welcome_message_raw.decode()
            if isinstance(welcome_message_raw, bytes)
            else welcome_message_raw
        )

        welcome_title_bytes = redis_client.get(
            f"server:{interaction.guild_id}:welcome_title"
        )
        welcome_title = (
            welcome_title_bytes.decode()
            if isinstance(welcome_title_bytes, bytes)
            else welcome_title_bytes
        )

        image_urls_bytes = redis_client.lrange(
            f"server:{interaction.guild_id}:welcome_images", 0, -1
        )
        image_urls = [
            url.decode() if isinstance(url, bytes) else url for url in image_urls_bytes
        ]

        use_random_image = (
            redis_client.get(f"server:{interaction.guild_id}:random_image") == b"True"
            or redis_client.get(f"server:{interaction.guild_id}:random_image") == "True"
        )

        if not welcome_message:
            await interaction.response.send_message(
                "尚未設定歡迎訊息。", ephemeral=True
            )
            return

        embed = discord.Embed(
            description=welcome_message.format(
                user=interaction.user.mention, server=interaction.guild.name
            )
        )

        if welcome_title:
            embed.title = welcome_title.format(
                user=interaction.user.name, server=interaction.guild.name
            )
        else:
            embed.title = f"歡迎 {interaction.user.name} 加入 {interaction.guild.name}！"  # 預設標題

        if image_urls:
            if use_random_image:
                embed.set_image(url=random.choice(image_urls))
            else:
                embed.set_image(url=image_urls[0] if image_urls else None)

        embed.set_thumbnail(
            url=interaction.user.avatar.url
            if interaction.user.avatar
            else interaction.user.default_avatar.url
        )

        now = datetime.now(timezone.utc).strftime("%H:%M")
        embed.set_footer(
            text=f"{get_time_greeting()} {now}",
            icon_url=self.bot.user.avatar.url,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="delete-welcome-settings", description="刪除歡迎訊息設定的 Embed"
    )
    @checks.is_guild_admin()
    async def delete_welcome_settings_command(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        settings_message_id_bytes = redis_client.get(
            f"server:{guild_id}:welcome_settings_message_id"
        )

        if settings_message_id_bytes:
            try:
                settings_message_id = int(settings_message_id_bytes.decode())
                # 假設設定訊息發送在呼叫指令的同一個頻道
                channel = interaction.channel
                try:
                    message = await channel.fetch_message(settings_message_id)
                    await message.delete()
                    redis_client.delete(
                        f"server:{guild_id}:welcome_settings_message_id"
                    )
                    await interaction.response.send_message(
                        "✅ 歡迎訊息設定的 Embed 已刪除。", ephemeral=True
                    )
                except discord.NotFound:
                    await interaction.response.send_message(
                        "⚠️ 找不到該訊息，可能已被刪除。", ephemeral=True
                    )
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "❌ Bot 沒有刪除該訊息的權限。", ephemeral=True
                    )
            except ValueError:
                await interaction.response.send_message(
                    "⚠️ 儲存的訊息 ID 無效。", ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "ℹ️ 沒有找到儲存的歡迎訊息設定 Embed ID。", ephemeral=True
            )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild_id = member.guild.id
        welcome_channel_id_bytes = redis_client.get(
            f"server:{guild_id}:welcome_channel"
        )
        default_role_id = redis_client.get(f"server:{guild_id}:default_role")
        welcome_message_raw = redis_client.get(f"server:{guild_id}:welcome_message")
        welcome_title_bytes = redis_client.get(f"server:{guild_id}:welcome_title")
        image_urls_bytes = redis_client.lrange(
            f"server:{guild_id}:welcome_images", 0, -1
        )
        image_urls = [url.decode() for url in image_urls_bytes]
        random_image_raw = redis_client.get(f"server:{guild_id}:random_image")
        use_random_image = random_image_raw == b"True" or random_image_raw == "True"

        if welcome_channel_id_bytes:
            channel = self.bot.get_channel(int(welcome_channel_id_bytes.decode()))
            if channel:
                embed = discord.Embed(color=discord.Color.random())
                if welcome_title_bytes:
                    embed.title = welcome_title_bytes.decode().format(
                        user=member.name, server=member.guild.name
                    )
                else:
                    embed.title = (
                        f"歡迎 {member.name} 加入 {member.guild.name}！"  # 預設標題
                    )

                if welcome_message_raw:
                    welcome_message = (
                        welcome_message_raw.decode()
                        if isinstance(welcome_message_raw, bytes)
                        else welcome_message_raw
                    )
                    embed.description = welcome_message.format(
                        user=member.mention, server=member.guild.name
                    )

                if image_urls:
                    if use_random_image:
                        embed.set_image(url=random.choice(image_urls))
                    else:
                        embed.set_image(url=image_urls[0] if image_urls else None)

                embed.set_thumbnail(
                    url=member.avatar.url
                    if member.avatar
                    else member.default_avatar.url
                )

                now = datetime.now(timezone.utc).strftime("%H:%M")
                embed.set_footer(
                    text=f"{get_time_greeting()} {now}",
                    icon_url=self.bot.user.avatar.url,
                )

                await channel.send(embed=embed)

        if default_role_id:
            role = member.guild.get_role(int(default_role_id.decode()))
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    print(
                        f"警告：無法將身分組 {role.name} 分配給 {member.name}，Bot 可能沒有足夠的權限。"
                    )


async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
