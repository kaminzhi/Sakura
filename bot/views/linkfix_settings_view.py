import discord
from discord import ui, Interaction
from ..utils.database import get_guild_data, update_guild_data


class ToggleAutoButton(ui.Button):
    def __init__(self):
        super().__init__(
            label="總開關",
            style=discord.ButtonStyle.gray,
            custom_id="toggle_auto_link_fix",
        )

    async def callback(self, interaction: Interaction):
        if not await self.view.is_authorized(interaction):
            return
        config = await get_guild_data(self.view.guild_id)
        current = config.get("auto_link_fix", False)
        await update_guild_data(self.view.guild_id, {"auto_link_fix": not current})
        await self.view.refresh_message(interaction)


class PreserveLinkButton(ui.Button):
    def __init__(self):
        super().__init__(
            label="原始連結",
            style=discord.ButtonStyle.gray,
            custom_id="toggle_preserve_link",
        )

    async def callback(self, interaction: Interaction):
        if not await self.view.is_authorized(interaction):
            return
        config = await get_guild_data(self.view.guild_id)
        current = config.get("preserve_original_link", False)
        await update_guild_data(
            self.view.guild_id, {"preserve_original_link": not current}
        )
        await self.view.refresh_message(interaction)


class LinkFixSettingsView(ui.View):
    def __init__(self, bot: discord.Client, guild_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.platform_keys: list[str] = []

        self.add_item(ToggleAutoButton())
        self.add_item(PreserveLinkButton())

    async def is_authorized(self, interaction: Interaction) -> bool:
        config = await get_guild_data(self.guild_id)
        allowed_roles = config.get("allowed_roles", [])

        if interaction.user.guild_permissions.administrator:
            return True

        if not allowed_roles:
            await interaction.response.send_message(
                "❌ 僅限管理員調整設定。", ephemeral=True
            )
            return False

        user_role_ids = [str(r.id) for r in interaction.user.roles]
        if any(rid in allowed_roles for rid in user_role_ids):
            return True

        await interaction.response.send_message(
            "❌ 你沒有權限調整此設定。", ephemeral=True
        )
        return False

    async def build_embed(self) -> discord.Embed:
        config = await get_guild_data(self.guild_id)
        platforms = config.get("platforms", {})
        self.platform_keys = list(platforms.keys())

        embed = discord.Embed(
            title="🔧 自動連結修正設定",
            description="這裡可以設定自動連結修正的功能。",
            color=discord.Color.green()
            if config.get("auto_link_fix")
            else discord.Color.red(),
        )

        embed.add_field(
            name="總開關",
            value="🟢 啟用" if config.get("auto_link_fix") else "🔴 停用",
            inline=False,
        )

        embed.add_field(
            name="原始連結",
            value="🔗 保留"
            if not config.get("preserve_original_link")
            else "🚫 不保留",
            inline=False,
        )

        enabled = [key.title() for key, val in platforms.items() if val]
        embed.add_field(
            name="啟用的平台",
            value="```\n" + "\n".join(f"• {label}" for label in enabled) + "\n```"
            if enabled
            else "無",
            inline=False,
        )

        allowed_channels = config.get("allowed_channels", [])
        embed.add_field(
            name="💬啓用的頻道",
            value="全部頻道皆可用"
            if not allowed_channels
            else "\n".join(f"<#{ch_id}>" for ch_id in allowed_channels),
            inline=False,
        )

        allowed_roles = config.get("allowed_roles", [])
        embed.add_field(
            name="😚允許操作的身份組",
            value="僅限管理員"
            if not allowed_roles
            else "\n".join(f"<@&{r}>" for r in allowed_roles),
            inline=False,
        )

        embed.set_footer(
            text=f"由 {self.bot.user.name} 提供服務",
            icon_url=self.bot.user.display_avatar.url,
        )

        return embed

    async def add_platform_select(self):
        config = await get_guild_data(self.guild_id)
        platforms = config.get("platforms", {})
        self.platform_keys = list(platforms.keys())

        options = [
            discord.SelectOption(
                label=key.title(), value=key, default=platforms.get(key, False)
            )
            for key in self.platform_keys
        ]

        select = ui.Select(
            placeholder="選擇要啟用的平台",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="select_enabled_platforms",
        )

        async def callback(interaction: Interaction):
            if not await self.is_authorized(interaction):
                return
            selected = set(select.values)
            new_platforms = {k: k in selected for k in self.platform_keys}
            await update_guild_data(self.guild_id, {"platforms": new_platforms})
            await self.refresh_message(interaction)

        select.callback = callback
        self.add_item(select)

    async def add_channel_select(self, interaction: discord.Interaction):
        config = await get_guild_data(self.guild_id)
        allowed_channels = config.get("allowed_channels", [])

        channels = [
            discord.SelectOption(
                label=channel.name,
                value=str(channel.id),
                default=channel.id in allowed_channels,
            )
            for channel in interaction.guild.text_channels
        ]

        select = ui.Select(
            placeholder="選擇頻道（留空代表全部）",
            min_values=0,
            max_values=len(channels),
            options=channels,
            custom_id="select_allowed_channels",
        )

        async def callback(interaction: Interaction):
            if not await self.is_authorized(interaction):
                return
            await update_guild_data(
                self.guild_id, {"allowed_channels": [int(v) for v in select.values]}
            )
            await self.refresh_message(interaction)

        select.callback = callback
        self.add_item(select)

    async def add_role_select(self, interaction: discord.Interaction):
        config = await get_guild_data(self.guild_id)
        allowed_roles = config.get("allowed_roles", [])

        roles = [
            discord.SelectOption(
                label=role.name,
                value=str(role.id),
                default=str(role.id) in allowed_roles,
            )
            for role in interaction.guild.roles
            if not role.is_default()
        ]

        select = ui.Select(
            placeholder="選擇允許設定的身份組（留空僅限管理員）",
            min_values=0,
            max_values=len(roles),
            options=roles,
            custom_id="select_allowed_roles",
        )

        async def callback(interaction: Interaction):
            if not await self.is_authorized(interaction):
                return
            await update_guild_data(
                self.guild_id, {"allowed_roles": [str(v) for v in select.values]}
            )
            await self.refresh_message(interaction)

        select.callback = callback
        self.add_item(select)

    async def refresh_message(self, interaction: Interaction):
        self.clear_items()
        self.add_item(ToggleAutoButton())
        self.add_item(PreserveLinkButton())
        await self.add_platform_select()
        await self.add_channel_select(interaction)
        await self.add_role_select(interaction)
        embed = await self.build_embed()

        if interaction.response.is_done():
            await interaction.followup.edit_message(
                message_id=interaction.message.id, embed=embed, view=self
            )
        else:
            await interaction.response.edit_message(embed=embed, view=self)
