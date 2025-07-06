# bot/cogs/voice_channel.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, Button, View
import logging
from bot.utils.database import get_guild_data, update_guild_data

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ChannelNameModal(Modal):
    def __init__(self, member: discord.Member, temp_channel: discord.VoiceChannel):
        super().__init__(title="設定臨時語音頻道名稱")
        self.member = member
        self.temp_channel = temp_channel
        self.name_input = TextInput(
            label="頻道名稱",
            placeholder="輸入新頻道名稱（留空使用預設）",
            default=f"{member.display_name}的語音頻道",
            max_length=100,
            required=False,
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_name = (
            self.name_input.value.strip() or f"{self.member.display_name}的語音頻道"
        )
        try:
            await self.temp_channel.edit(name=new_name)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ 頻道名稱已設定",
                    description=f"臨時語音頻道名稱已設為：**{new_name}**",
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )
        except discord.errors.Forbidden:
            await interaction.followup.send(
                "機器人缺少管理頻道的權限，無法更改頻道名稱！", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to set channel name for {self.member.id}: {e}")
            await interaction.followup.send(
                f"設定頻道名稱時發生錯誤：{str(e)}", ephemeral=True
            )


class VoiceChannel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_channels = {}  # Dict to track temporary channels: {guild_id: {user_id: channel_id}}

    async def check_permissions(self, guild: discord.Guild) -> bool:
        """Check if bot has required permissions."""
        bot_member = guild.me
        required_perms = (
            bot_member.guild_permissions.manage_channels
            and bot_member.guild_permissions.connect
            and bot_member.guild_permissions.move_members
        )
        if not required_perms:
            logger.warning(f"Bot lacks required permissions in guild {guild.id}")
        return required_perms

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Handle voice channel joins and leaves for dynamic channels."""
        if not await self.check_permissions(member.guild):
            return

        guild_data = await get_guild_data(member.guild.id)
        trigger_channel_id = guild_data.get("dvc_trigger_channel_id")
        category_id = guild_data.get("dvc_category_id")

        # Initialize active_channels for guild if not present
        if member.guild.id not in self.active_channels:
            self.active_channels[member.guild.id] = {}

        # Handle joining the trigger channel
        if after.channel and after.channel.id == trigger_channel_id:
            try:
                category = (
                    member.guild.get_channel(category_id) if category_id else None
                )
                temp_channel = await member.guild.create_voice_channel(
                    name=f"{member.display_name}的語音頻道",
                    category=category,
                    reason="動態語音頻道創建",
                )
                await temp_channel.set_permissions(
                    member, manage_channels=True, connect=True, speak=True
                )
                await member.move_to(temp_channel)
                self.active_channels[member.guild.id][member.id] = temp_channel.id

                # Send modal for channel name via DM
                view = View(timeout=60)
                button = Button(
                    label="設定名稱",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"set_channel_name_{temp_channel.id}",
                )

                async def button_callback(interaction: discord.Interaction):
                    await interaction.response.send_modal(
                        ChannelNameModal(member, temp_channel)
                    )

                button.callback = button_callback
                view.add_item(button)

                await member.send(
                    embed=discord.Embed(
                        title="🔊 設定臨時語音頻道名稱",
                        description="請點擊下方按鈕輸入新頻道名稱，或留空以使用預設名稱。",
                        color=discord.Color.blue(),
                    ),
                    view=view,
                )
                logger.info(
                    f"Created temp voice channel {temp_channel.id} for {member.id}"
                )
            except discord.errors.Forbidden:
                logger.error(
                    f"Failed to create voice channel for {member.id}: Missing permissions"
                )
                await member.send(
                    "機器人缺少管理頻道的權限，無法創建臨時語音頻道！", ephemeral=True
                )
            except Exception as e:
                logger.error(f"Failed to create voice channel for {member.id}: {e}")
                await member.send(
                    f"創建臨時語音頻道時發生錯誤：{str(e)}", ephemeral=True
                )

        # Handle leaving a temporary channel
        if (
            before.channel
            and before.channel.id
            in self.active_channels.get(member.guild.id, {}).values()
        ):
            channel = before.channel
            if not channel.members:  # Channel is empty
                try:
                    await channel.delete(reason="動態語音頻道無人，自動刪除")
                    self.active_channels[member.guild.id] = {
                        k: v
                        for k, v in self.active_channels[member.guild.id].items()
                        if v != channel.id
                    }
                    logger.info(f"Deleted empty temp voice channel {channel.id}")
                except discord.errors.Forbidden:
                    logger.error(
                        f"Failed to delete voice channel {channel.id}: Missing permissions"
                    )
                except Exception as e:
                    logger.error(f"Failed to delete voice channel {channel.id}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceChannel(bot))
