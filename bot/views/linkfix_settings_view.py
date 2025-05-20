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
        view: LinkFixSettingsView = self.view
        config = await get_guild_data(view.guild_id)
        current = config.get("auto_link_fix", False)
        await update_guild_data(view.guild_id, {"auto_link_fix": not current})
        await view.refresh_message(interaction)


class PreserveLinkButton(ui.Button):
    def __init__(self):
        super().__init__(
            label="保留原始連結",
            style=discord.ButtonStyle.blurple,
            custom_id="toggle_preserve_link",
        )

    async def callback(self, interaction: Interaction):
        view: LinkFixSettingsView = self.view
        config = await get_guild_data(view.guild_id)
        current = config.get("preserve_original_link", False)
        await update_guild_data(view.guild_id, {"preserve_original_link": not current})
        await view.refresh_message(interaction)


class LinkFixSettingsView(ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.platform_keys: list[str] = []

        # 預先加入按鈕，選單稍後用 build_embed 之後加入
        self.add_item(ToggleAutoButton())
        self.add_item(PreserveLinkButton())

    async def build_embed(self) -> discord.Embed:
        config = await get_guild_data(self.guild_id)
        platforms = config.get("platforms", {})
        self.platform_keys = list(platforms.keys())  # 儲存平台 key

        embed = discord.Embed(
            title="🔧 自動連結修正設定",
            description="可開關總開關與各平台是否啟用自動修正",
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
            name="是否保留原始連結",
            value="🔗 保留" if config.get("preserve_original_link") else "🚫 不保留",
            inline=False,
        )

        enabled = [key.title() for key, val in platforms.items() if val]
        embed.add_field(
            name="啟用的平台",
            value=f"```\n" + "\n".join(f"• {label}" for label in enabled) + "\n```"
            if enabled
            else "無",
            inline=False,
        )

        return embed

    def add_platform_select(self):
        if not self.platform_keys:
            return

        options = [
            discord.SelectOption(label=key.title(), value=key)
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
            selected = set(select.values)
            new_platforms = {k: k in selected for k in self.platform_keys}
            await update_guild_data(self.guild_id, {"platforms": new_platforms})
            await self.refresh_message(interaction)

        select.callback = callback
        self.add_item(select)

    async def refresh_message(self, interaction: Interaction):
        self.clear_items()
        self.add_item(ToggleAutoButton())
        self.add_item(PreserveLinkButton())
        self.add_platform_select()
        embed = await self.build_embed()

        if interaction.response.is_done():
            await interaction.followup.edit_message(
                message_id=interaction.message.id, embed=embed, view=self
            )
        else:
            await interaction.response.edit_message(embed=embed, view=self)
