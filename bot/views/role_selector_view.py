# bot/views/role_selector_view.py
import discord
from discord.ui import Button, View, Select
import logging
from .embed_builder import build_success_embed, build_error_embed, build_info_embed

logger = logging.getLogger(__name__)


class RoleSelectorView(View):
    def __init__(self, guild_data: dict, guild: discord.Guild):
        super().__init__(timeout=None)
        self.guild_data = guild_data
        self.guild = guild

        button = Button(
            label="選擇身份組",
            style=discord.ButtonStyle.primary,
            custom_id="role_selector_button",
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
            custom_id=f"role_selector_select_{interaction.guild_id}",
        )

        async def on_select(interaction: discord.Interaction):
            selected_role_ids = [int(rid) for rid in interaction.data["values"]]
            member = interaction.user
            logger.debug(f"Selected role IDs: {selected_role_ids}, Member: {member.id}")

            current_roles = {role.id for role in member.roles}
            logger.debug(f"Current roles: {current_roles}")

            roles_to_add = [
                self.guild.get_role(rid)
                for rid in selected_role_ids
                if self.guild.get_role(rid) and rid not in current_roles
            ]
            logger.debug(f"Roles to add: {[r.name for r in roles_to_add if r]}")

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

                member = await self.guild.fetch_member(member.id)
                current_selectable_roles = [
                    role for role in member.roles if role.id in selectable_roles
                ]
                role_mentions = [role.mention for role in current_selectable_roles]
                logger.debug(f"Updated roles in selectable: {role_mentions}")

                embed = build_success_embed(
                    title="身份組更新成功",
                    description=f"目前身份組: {', '.join(role_mentions) if role_mentions else '無'}",
                    bot_user=self.guild.me
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.Forbidden as e:
                logger.error(f"Permission error assigning roles for {member.id}: {e}")
                embed = build_error_embed(
                    title="權限錯誤",
                    description="無法更新身份組，機器人權限不足！請確保機器人具有管理身份組權限且其角色高於目標角色。",
                    bot_user=self.guild.me
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.HTTPException as e:
                logger.error(f"HTTP error assigning roles for {member.id}: {e}")
                embed = build_error_embed(
                    title="網路錯誤",
                    description="更新身份組時發生錯誤，請稍後重試！",
                    bot_user=self.guild.me
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        select.callback = on_select
        view = View(timeout=60)
        view.add_item(select)
        
        embed = build_info_embed(
            title="選擇身份組",
            description="請從下拉選單中選擇你想要的身份組。",
            bot_user=self.guild.me
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
