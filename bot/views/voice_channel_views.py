# bot/views/voice_channel_views.py
import discord
from discord.ui import Modal, TextInput, Button, View
import logging
from bot.views.embed_builder import build_success_embed, build_error_embed

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
                embed=build_success_embed(
                    "頻道名稱已設定",
                    f"臨時語音頻道名稱已設為：**{new_name}**",
                    bot_user=interaction.client.user
                ),
                ephemeral=True,
            )
        except discord.errors.Forbidden:
            await interaction.followup.send(
                embed=build_error_embed("權限不足", "機器人缺少管理頻道的權限，無法更改頻道名稱！", bot_user=interaction.client.user), ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to set channel name for {self.member.id}: {e}")
            await interaction.followup.send(
                embed=build_error_embed("設定失敗", f"設定頻道名稱時發生錯誤：{str(e)}", bot_user=interaction.client.user), ephemeral=True
            )


class VoiceChannelView(View):
    def __init__(self, member: discord.Member, temp_channel: discord.VoiceChannel):
        super().__init__(timeout=300)
        self.member = member
        self.temp_channel = temp_channel
        self.add_item(self.rename_button())

    def rename_button(self):
        button = Button(
            label="重新命名頻道",
            style=discord.ButtonStyle.primary,
            emoji="✏️",
        )
        button.callback = self.rename_channel
        return button

    async def rename_channel(self, interaction: discord.Interaction):
        if interaction.user != self.member:
            await interaction.response.send_message(
                embed=build_error_embed("權限不足", "只有頻道創建者可以重新命名頻道！", bot_user=interaction.client.user), ephemeral=True
            )
            return
        await interaction.response.send_modal(
            ChannelNameModal(self.member, self.temp_channel)
        )
