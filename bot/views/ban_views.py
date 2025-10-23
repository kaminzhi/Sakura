# bot/views/ban_views.py
import discord
from discord.ui import Button, View, Select
from datetime import datetime
import logging
from ..utils.database import get_guild_data, log_ban
from .embed_builder import build_ban_log_embed, build_error_embed, build_success_embed

logger = logging.getLogger(__name__)


class BanSystemView(View):
    def __init__(self, guild_data: dict, guild: discord.Guild):
        super().__init__(timeout=None) 
        self.guild_data = guild_data
        self.guild = guild

        select_users_button = Button(
            label="選擇成員",
            style=discord.ButtonStyle.primary,
            custom_id="select_users_button",
        )
        select_users_button.callback = self.select_users
        self.add_item(select_users_button)

        cancel_button = Button(
            label="取消",
            style=discord.ButtonStyle.secondary,
            custom_id="ban_cancel_button",
        )
        cancel_button.callback = self.cancel
        self.add_item(cancel_button)

    async def check_user_permissions(self, user: discord.Member) -> bool:
        if user.guild_permissions.ban_members:
            return True
        logger.debug(f"User {user.id} lacks ban_members permission")
        return False

    async def select_users(self, interaction: discord.Interaction):
        guild_data = self.guild_data
        if not interaction.guild.me.guild_permissions.ban_members:
            await interaction.response.send_message(
                "機器人缺少封禁成員權限！請檢查機器人角色權限。", ephemeral=True
            )
            return
        if not await self.check_user_permissions(interaction.user):
            await interaction.response.send_message(
                "你需要封禁成員權限來執行此操作！", ephemeral=True
            )
            return

        members = [
            member
            for member in self.guild.members
            if not member.bot and not member.guild_permissions.administrator
        ]
        if not members:
            await interaction.response.send_message(
                "沒有可封禁的成員！", ephemeral=True
            )
            return

        options = [
            discord.SelectOption(
                label=member.display_name,
                value=str(member.id),
                description=f"ID: {member.id}",
            )
            for member in members[:25]
        ]
        select = Select(
            placeholder="選擇要封禁的成員（可多選）",
            options=options,
            min_values=1,
            max_values=min(len(options), 25),
            custom_id=f"ban_user_select_{self.guild.id}",
        )

        async def on_select(interaction: discord.Interaction):
            selected_user_ids = [int(uid) for uid in interaction.data["values"]]
            logger.debug(f"Selected user IDs for ban: {selected_user_ids}")
            selected_members = [
                self.guild.get_member(uid)
                for uid in selected_user_ids
                if self.guild.get_member(uid)
            ]
            if not selected_members:
                await interaction.response.send_message(
                    "無效的選擇！請重試。", ephemeral=True
                )
                return

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="確認封禁成員",
                    description=f"你確定要封禁以下成員嗎？\n{', '.join(m.mention for m in selected_members)}",
                    color=discord.Color.red(),
                ),
                view=ConfirmBanUserView(selected_members, self.guild, guild_data),
                ephemeral=True,
            )

        select.callback = on_select
        view = View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="選擇要封禁的成員",
                description="請從下拉選單中選擇要封禁的成員。",
                color=discord.Color.blue(),
            ),
            view=view,
            ephemeral=True,
        )

    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.send_message("已取消操作。", ephemeral=True)


class ConfirmBanUserView(View):
    def __init__(self, members: list, guild: discord.Guild, guild_data: dict):
        super().__init__(timeout=60)
        self.members = members
        self.guild = guild
        self.guild_data = guild_data

    async def check_user_permissions(self, user: discord.Member) -> bool:
        if user.guild_permissions.ban_members:
            return True
        logger.debug(f"User {user.id} lacks ban_members permission")
        return False

    @discord.ui.button(
        label="確認", style=discord.ButtonStyle.danger, custom_id="confirm_ban_user"
    )
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not await self.check_user_permissions(interaction.user):
            await interaction.response.send_message(
                "你需要封禁成員權限來確認！", ephemeral=True
            )
            return

        log_channel_id = self.guild_data.get("ban_log_channel_id")
        log_channel = self.guild.get_channel(log_channel_id) if log_channel_id else None
        reason = "管理員通過封禁面板發起的封禁"
        bot_member = self.guild.me

        banned_members = []
        errors = []
        for member in self.members:
            try:
                member_top_role = max(
                    member.roles, key=lambda r: r.position, default=None
                )
                bot_top_role = max(
                    bot_member.roles, key=lambda r: r.position, default=None
                )
                logger.debug(
                    f"Attempting to ban {member.id}: "
                    f"Member top role: {member_top_role.name if member_top_role else 'None'} (position {member_top_role.position if member_top_role else 0}), "
                    f"Bot top role: {bot_top_role.name if bot_top_role else 'None'} (position {bot_top_role.position if bot_top_role else 0})"
                )

                await member.ban(reason=reason)
                logger.info(
                    f"Banned user {member.id} in guild {self.guild.id} by {interaction.user.id}"
                )
                banned_members.append(member)

                ban_data = {
                    "guild_id": self.guild.id,
                    "user_id": member.id,
                    "moderator_id": interaction.user.id,
                    "reason": reason,
                    "type": "user",
                }
                await log_ban(ban_data)

                if (
                    log_channel
                    and log_channel.permissions_for(self.guild.me).send_messages
                ):
                    embed = build_ban_log_embed(
                        member=member,
                        guild=self.guild,
                        reason=reason,
                        moderator=interaction.user,
                        bot_user=self.guild.me
                    )
                    await log_channel.send(embed=embed)
                    logger.debug(
                        f"Sent ban log to channel {log_channel_id} for user {member.id}"
                    )
            except discord.Forbidden:
                logger.error(
                    f"Failed to ban user {member.id}: missing permissions or role hierarchy issue. "
                    f"Bot permissions: {bot_member.guild_permissions.ban_members}"
                )
                errors.append(f"無法封禁 {member.display_name}：權限不足或角色層級問題")
            except discord.HTTPException as e:
                logger.error(f"Failed to ban user {member.id}: {e}")
                errors.append(f"無法封禁 {member.display_name}：HTTP 錯誤 ({e})")

        if banned_members:
            description = f"已封禁: {', '.join(m.mention for m in banned_members)}"
            if errors:
                description += "\n\n錯誤:\n" + "\n".join(errors)
            embed = build_success_embed(
                title="封禁結果",
                description=description,
                bot_user=self.guild.me
            )
            if errors:
                embed.color = discord.Color.yellow()
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            error_message = (
                "無法封禁任何成員:\n" + "\n".join(errors)
                if errors
                else "未知錯誤，請檢查日誌。"
            )
            embed = build_error_embed(
                title="封禁失敗",
                description=error_message,
                bot_user=self.guild.me
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="取消", style=discord.ButtonStyle.secondary, custom_id="cancel_ban_user"
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("已取消成員封禁。", ephemeral=True)
