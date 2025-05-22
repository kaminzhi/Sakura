import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import io
import asyncio
import aiohttp
import imageio.v3 as iio
from PIL import Image, ImageSequence

# DEFAULT_BANNER_URL = "https://cdn.discordapp.com/attachments/1334764445775298590/1374903599771160709/tumblr_pdfsjua6ht1vhnny1o1_500_2.gif?ex=682fbe42&is=682e6cc2&hm=66132648328fd964ee7a5198560cb8b56ef5c72d48a5fcdf386a69663dab382b&"
DEFAULT_BANNER_URL = None  # 這裡可以設置一個預設的橫幅 URL，如果需要的話“


class UserProfile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.bot.session:
            await self.bot.session.close()

    async def download_image(self, url: str) -> io.BytesIO | None:
        if not url:
            return None
        try:
            print(f"Debug: Attempting to download image from: {url}")
            async with self.bot.session.get(url) as response:
                if response.status == 200:
                    print(
                        f"Debug: Successfully downloaded {url} (Status: {response.status})"
                    )
                    return io.BytesIO(await response.read())
                else:
                    print(
                        f"Debug: Failed to download image from {url}: HTTP Status {response.status}"
                    )
                    return None
        except aiohttp.ClientError as ce:  # 捕獲 aiohttp 特有的錯誤
            print(f"Debug: aiohttp ClientError downloading from {url}: {ce}")
            return None
        except Exception as e:
            print(f"Debug: Generic Error downloading image from {url}: {e}")
            return None

    def process_image_sync(
        self, banner_data: io.BytesIO, avatar_data: io.BytesIO, member_name: str
    ) -> io.BytesIO | None:
        try:
            if banner_data:
                banner_img = Image.open(banner_data)
                print(
                    f"Debug: Banner image opened. Size: {banner_img.size}, Mode: {banner_img.mode}"
                )
            else:
                # 備用方案：如果沒有橫幅資料，則建立一個純黑背景
                banner_img = Image.new("RGB", (800, 200), color="black")
                print("Debug: No banner_data provided, creating black fallback banner.")

            if avatar_data:
                avatar_img = Image.open(avatar_data)
                print(
                    f"Debug: Avatar image opened. Size: {avatar_img.size}, Mode: {avatar_img.mode}"
                )
            else:
                avatar_img = Image.new("RGBA", (128, 128), color=(0, 0, 0, 0))
                print(
                    "Debug: No avatar_data provided, creating transparent fallback avatar."
                )

            if avatar_img.mode != "RGBA":
                avatar_img = avatar_img.convert("RGBA")
                print(f"Debug: Avatar converted to RGBA mode: {avatar_img.mode}")

            output_frames = []
            frame_durations = []
            is_output_gif = False  # 標誌，用於判斷輸出是否應該是 GIF

            banner_is_animated = (
                hasattr(banner_img, "is_animated") and banner_img.is_animated
            )
            avatar_is_animated = (
                hasattr(avatar_img, "is_animated") and avatar_img.is_animated
            )

            if banner_is_animated or avatar_is_animated:
                is_output_gif = True

                banner_frames = [
                    f.copy().convert("RGBA") for f in ImageSequence.Iterator(banner_img)
                ]
                banner_durations = [
                    banner_img.info.get("duration", 100) for _ in banner_frames
                ]
                print(
                    f"Debug: Banner has {len(banner_frames)} frames, durations: {banner_durations}"
                )

                avatar_frames = [
                    f.copy().convert("RGBA") for f in ImageSequence.Iterator(avatar_img)
                ]
                avatar_durations = [
                    avatar_img.info.get("duration", 100) for _ in avatar_frames
                ]
                print(
                    f"Debug: Avatar has {len(avatar_frames)} frames, durations: {avatar_durations}"
                )

                max_frames = max(len(banner_frames), len(avatar_frames))

                for i in range(max_frames):
                    current_banner_frame = banner_frames[i % len(banner_frames)]
                    current_avatar_frame = avatar_frames[i % len(avatar_frames)]

                    target_avatar_size = min(
                        current_banner_frame.width // 4,
                        current_banner_frame.height // 2,
                    )
                    current_avatar_frame_resized = current_avatar_frame.resize(
                        (target_avatar_size, target_avatar_size)
                    )

                    x_pos = (current_banner_frame.width - target_avatar_size) // 2
                    y_pos = (current_banner_frame.height - target_avatar_size) // 2

                    composite_frame = current_banner_frame.copy()
                    composite_frame.paste(
                        current_avatar_frame_resized,
                        (x_pos, y_pos),
                        current_avatar_frame_resized,
                    )

                    output_frames.append(composite_frame)

                    banner_frame_duration = banner_durations[i % len(banner_durations)]
                    avatar_frame_duration = avatar_durations[i % len(avatar_durations)]
                    frame_durations.append(
                        max(banner_frame_duration, avatar_frame_duration)
                    )

                output_buffer = io.BytesIO()
                iio.imwrite(
                    output_buffer,
                    [f.convert("RGB") for f in output_frames],
                    format="GIF",
                    loop=0,
                    duration=frame_durations,
                )
                output_buffer.seek(0)
                print("Debug: Successfully created GIF output.")
                return output_buffer

            else:  # static image
                target_avatar_size = min(banner_img.width // 4, banner_img.height // 2)
                avatar_img_resized = avatar_img.resize(
                    (target_avatar_size, target_avatar_size)
                )

                x_pos = (banner_img.width - target_avatar_size) // 2
                y_pos = (banner_img.height - target_avatar_size) // 2

                composite_img = banner_img.copy().convert("RGBA")
                composite_img.paste(
                    avatar_img_resized, (x_pos, y_pos), avatar_img_resized
                )

                output_buffer = io.BytesIO()
                composite_img.save(output_buffer, format="PNG")
                output_buffer.seek(0)
                print("Debug: Successfully created PNG output.")
                return output_buffer

        except Exception as e:
            print(f"Debug: Error in process_image_sync for {member_name}: {e}")
            import traceback

            traceback.print_exc()
            return None

    @app_commands.command(
        name="user-profile", description="查看使用者的個人資訊，包含自訂橫幅和頭像"
    )
    async def user_profile(
        self, interaction: discord.Interaction, member: discord.Member = None
    ):
        await interaction.response.defer()

        member = member or interaction.user
        guild = interaction.guild

        avatar_url = member.display_avatar.url

        # User Banner Check
        user = await self.bot.fetch_user(member.id)
        if user.banner:
            banner_url = user.banner.url
        else:
            if DEFAULT_BANNER_URL != None:
                banner_url = DEFAULT_BANNER_URL
            else:
                banner_url = avatar_url

        avatar_data = await self.download_image(avatar_url)
        banner_data = await self.download_image(banner_url)

        processed_image_buffer = await asyncio.to_thread(
            self.process_image_sync, banner_data, avatar_data, member.display_name
        )

        file = None
        if processed_image_buffer:
            is_gif = processed_image_buffer.getvalue()[:4] == b"GIF8"
            filename = "user_profile.gif" if is_gif else "user_profile.png"
            file = discord.File(processed_image_buffer, filename=filename)
            print(f"Debug: Output file prepared: {filename}")
        else:
            print("Debug: processed_image_buffer is None. File will not be attached.")

        embed = discord.Embed(
            title=f"👤 {member.display_name} 的個人資訊",
            color=discord.Color.pink(),
            timestamp=datetime.utcnow(),
        )

        embed.set_author(
            name=f"{member.name}#{member.discriminator}",
            icon_url=member.display_avatar.url,
        )

        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        if file:
            embed.set_image(url=f"attachment://{file.filename}")
        else:
            embed.add_field(name="錯誤", value="無法生成個人資料橫幅。", inline=False)
            embed.add_field(
                name="提示",
                value="請檢查機器人主控台的除錯訊息，確保橫幅圖片能夠下載。",
                inline=False,
            )

        joined_at = (
            member.joined_at.strftime("%Y/%m/%d %H:%M") if member.joined_at else "未知"
        )
        created_at = member.created_at.strftime("%Y/%m/%d %H:%M")

        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_str = ", ".join(roles) if roles else "無"

        embed.add_field(name="🆔 使用者 ID", value=str(member.id), inline=False)
        embed.add_field(name="📥 加入伺服器時間", value=joined_at, inline=True)
        embed.add_field(name="📅 加入 Discord 時間", value=created_at, inline=True)
        embed.add_field(name="🎭 擁有的身分組", value=roles_str, inline=False)

        embed.set_footer(
            text=f"由 {interaction.user.display_name} 查詢",
            icon_url=interaction.user.display_avatar.url,
        )

        if file:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(UserProfile(bot))
