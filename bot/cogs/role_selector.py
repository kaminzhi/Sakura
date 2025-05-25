# bot/cogs/role_selector.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select
import logging
from bot.utils.database import get_guild_data, update_guild_data

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class RoleSelectorView(View):
    def __init__(self, guild_data: dict, guild: discord.Guild):
        super().__init__(timeout=None)  # Persistent view
        self.guild_data = guild_data
        self.guild = guild

        button = Button(
            label="選擇身份組",
            style=discord.ButtonStyle.primary,
            custom_id="role_selector_button",  # Added custom_id
        )
        button.callback = self.select_roles
        self.add_item(button)

    async def select_roles(self, interaction: discord.Interaction):
        guild_data = self.guild_data
        role_selection_channel_id = guild_data.get("role_selection_channel_id")
        logger.debug(
            f"select_roles called: channel_id={interaction.channel_id}, expected={role_selection_channel_id}"
        )
        if (
            not role_selection_channel_id
            or interaction.channel_id != role_selection_channel_id
        ):
            await interaction.response.send_message(
                "此功能未在此頻道啟用！", ephemeral=True
            )
            return

        selectable_roles = guild_data.get("selectable_roles", [])
        logger.debug(f"Selectable roles from DB: {selectable_roles}")
        options = [
            discord.SelectOption(
                label=self.guild.get_role(role_id).name, value=str(role_id)
            )
            for role_id in selectable_roles
            if self.guild.get_role(role_id)
        ]
        logger.debug(f"Dropdown options: {[opt.label for opt in options]}")
        if not options:
            await interaction.response.send_message(
                "目前沒有可選的身份組！", ephemeral=True
            )
            return

        select = Select(
            placeholder="選擇你的身份組（可多選）",
            options=options,
            min_values=0,
            max_values=len(options),
            custom_id=f"role_selector_select_{interaction.guild_id}",  # Unique custom_id per guild
        )

        async def on_select(interaction: discord.Interaction):
            selected_role_ids = [int(rid) for rid in interaction.data["values"]]
            member = interaction.user
            logger.debug(f"Selected role IDs: {selected_role_ids}, Member: {member.id}")

            # Get current roles
            current_roles = {role.id for role in member.roles}
            logger.debug(f"Current roles: {current_roles}")

            # Validate roles to add
            roles_to_add = [
                self.guild.get_role(rid)
                for rid in selected_role_ids
                if self.guild.get_role(rid) and rid not in current_roles
            ]
            logger.debug(f"Roles to add: {[r.name for r in roles_to_add if r]}")

            # Validate roles to remove
            roles_to_remove = [
                self.guild.get_role(rid)
                for rid in selectable_roles
                if self.guild.get_role(rid)
                and rid in current_roles
                and rid not in selected_role_ids
            ]
            logger.debug(f"Roles to remove: {[r.name for r in roles_to_remove if r]}")

            try:
                if roles_to_add:
                    await member.add_roles(*roles_to_add, reason="身份組選擇")
                    logger.info(
                        f"Added roles to {member.id}: {[r.name for r in roles_to_add]}"
                    )
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="身份組選擇")
                    logger.info(
                        f"Removed roles from {member.id}: {[r.name for r in roles_to_remove]}"
                    )

                # Refresh member to get updated roles
                member = await self.guild.fetch_member(member.id)
                current_selectable_roles = [
                    role for role in member.roles if role.id in selectable_roles
                ]
                role_mentions = [role.mention for role in current_selectable_roles]
                logger.debug(f"Updated roles in selectable: {role_mentions}")

                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="✅ 身份組更新成功",
                        description=f"目前身份組: {', '.join(role_mentions) if role_mentions else '無'}",
                        color=discord.Color.green(),
                    ),
                    ephemeral=True,
                )
            except discord.Forbidden as e:
                logger.error(f"Permission error assigning roles for {member.id}: {e}")
                await interaction.response.send_message(
                    "無法更新身份組，機器人權限不足！請確保機器人具有管理身份組權限且其角色高於目標角色。",
                    ephemeral=True,
                )
            except discord.HTTPException as e:
                logger.error(f"HTTP error assigning roles for {member.id}: {e}")
                await interaction.response.send_message(
                    "更新身份組時發生錯誤，請稍後重試！", ephemeral=True
                )

        select.callback = on_select
        view = View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="選擇身份組",
                description="請從下拉選單中選擇你想要的身份組。",
                color=discord.Color.blue(),
            ),
            view=view,
            ephemeral=True,
        )


class RoleSelector(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register persistent view with valid components
        placeholder_guild = bot.get_guild(0) or discord.Object(
            id=0
        )  # Fallback if no guilds available
        view = RoleSelectorView({}, placeholder_guild)
        self.bot.add_view(view)
        logger.info("Registered persistent RoleSelectorView with custom_id")

    async def cog_load(self):
        logger.info("RoleSelector cog loaded")

    @app_commands.command(name="rolepanel", description="發送身份組選擇面板")
    @app_commands.default_permissions(manage_roles=True)
    async def role_panel(self, interaction: discord.Interaction):
        guild_data = await get_guild_data(interaction.guild_id)
        role_selection_channel_id = guild_data.get("role_selection_channel_id")
        logger.debug(
            f"Role panel requested: channel_id={interaction.channel_id}, expected={role_selection_channel_id}"
        )
        if not role_selection_channel_id:
            await interaction.response.send_message(
                "請先在設定面板中設定身份組選擇頻道！", ephemeral=True
            )
            return
        if interaction.channel_id != role_selection_channel_id:
            channel = interaction.guild.get_channel(role_selection_channel_id)
            await interaction.response.send_message(
                f"身份組選擇面板只能在 {channel.mention} 中發送！", ephemeral=True
            )
            return

        # Clean up old panels in the channel
        channel = interaction.guild.get_channel(role_selection_channel_id)
        if (
            channel
            and channel.permissions_for(interaction.guild.me).read_message_history
        ):
            async for message in channel.history(limit=100):
                if (
                    message.author == self.bot.user
                    and message.embeds
                    and message.embeds[0].title == "🎭 選擇你的身份組"
                ):
                    try:
                        await message.delete()
                        logger.debug(f"Deleted old role panel message: {message.id}")
                    except discord.Forbidden:
                        logger.warning(
                            "Failed to delete old panel: missing permissions"
                        )
                    except discord.HTTPException as e:
                        logger.error(f"Failed to delete old panel: {e}")

        embed = discord.Embed(
            title="🎭 選擇你的身份組",
            description="點擊下方按鈕以選擇或更改你的身份組。",
            color=discord.Color.purple(),
        )
        view = RoleSelectorView(guild_data, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"Sent new role panel in channel {role_selection_channel_id}")

    @app_commands.command(
        name="refresh_rolepanel", description="更新現有的身份組選擇面板"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def refresh_role_panel(self, interaction: discord.Interaction):
        guild_data = await get_guild_data(interaction.guild_id)
        role_selection_channel_id = guild_data.get("role_selection_channel_id")
        logger.debug(
            f"Refresh role panel requested: channel_id={interaction.channel_id}, expected={role_selection_channel_id}"
        )
        if not role_selection_channel_id:
            await interaction.response.send_message(
                "請先在設定面板中設定身份組選擇頻道！", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(role_selection_channel_id)
        if not channel:
            await interaction.response.send_message(
                "設定的頻道無效！請重新設定身份組選擇頻道。", ephemeral=True
            )
            return

        # Find and update existing panel
        updated = False
        if channel.permissions_for(interaction.guild.me).read_message_history:
            async for message in channel.history(limit=100):
                if (
                    message.author == self.bot.user
                    and message.embeds
                    and message.embeds[0].title == "🎭 選擇你的身份組"
                ):
                    try:
                        embed = discord.Embed(
                            title="🎭 選擇你的身份組",
                            description="點擊下方按鈕以選擇或更改你的身份組。",
                            color=discord.Color.purple(),
                        )
                        view = RoleSelectorView(guild_data, interaction.guild)
                        await message.edit(embed=embed, view=view)
                        logger.debug(
                            f"Updated existing role panel message: {message.id}"
                        )
                        updated = True
                        break
                    except discord.Forbidden:
                        logger.warning("Failed to edit panel: missing permissions")
                    except discord.HTTPException as e:
                        logger.error(f"Failed to edit panel: {e}")

        if not updated:
            # If no panel found or update failed, send a new one
            embed = discord.Embed(
                title="🎭 選擇你的身份組",
                description="點擊下方按鈕以選擇或更改你的身份組。",
                color=discord.Color.purple(),
            )
            view = RoleSelectorView(guild_data, interaction.guild)
            await channel.send(embed=embed, view=view)
            logger.info(
                f"Sent new role panel for refresh in channel {role_selection_channel_id}"
            )

        await interaction.response.send_message(
            "身份組選擇面板已更新！", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleSelector(bot))
