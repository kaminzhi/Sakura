import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import io
import asyncio
import aiohttp
import imageio.v3 as iio
from PIL import Image, ImageSequence, ImageDraw

DEFAULT_BANNER_URL = "https://cdn.discordapp.com/attachments/1334764445775298590/1374903599771160709/tumblr_pdfsjua6ht1vhnny1o1_500_2.gif?ex=682fbe42&is=682e6cc2&hm=66132648328fd964ee7a5198560cb8b56ef5c72d48a5fcdf386a69663dab382b&"

# Banner size
DISCORD_BANNER_WIDTH = 600
DISCORD_BANNER_HEIGHT = 240

# Avatar Size
AVATAR_TARGET_SIZE = 160
AVATAR_BORDER_WIDTH = 5
AVATAR_BORDER_COLOR = (255, 255, 255)


class UserProfile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.bot.session:
            await self.bot.session.close()

    async def download_image(self, url: str) -> io.BytesIO | None:
        if not url:
            print("Debug: Download URL is empty or None.")
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
        except aiohttp.ClientError as ce:
            print(f"Debug: aiohttp ClientError downloading from {url}: {ce}")
            return None
        except Exception as e:
            print(f"Debug: Generic Error downloading image from {url}: {e}")
            return None

    def round_avatar_with_border(
        self, avatar_img: Image.Image, size: int, border_width: int, border_color: tuple
    ) -> Image.Image:
        """
        Avatar border and round funtion, base on PIL Image
        """
        avatar_resized = avatar_img.resize((size, size), Image.Resampling.LANCZOS)

        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)

        rounded_avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rounded_avatar.paste(avatar_resized, (0, 0), mask)

        border_size = size + border_width * 2
        border_img = Image.new("RGBA", (border_size, border_size), (0, 0, 0, 0))
        draw_border = ImageDraw.Draw(border_img)

        draw_border.ellipse((0, 0, border_size, border_size), fill=border_color)
        draw_border.ellipse(
            (border_width, border_width, size + border_width, size + border_width),
            fill=(0, 0, 0, 0),
        )

        border_img.paste(rounded_avatar, (border_width, border_width), rounded_avatar)
        return border_img

    def process_image_sync(
        self, banner_data: io.BytesIO, avatar_data: io.BytesIO, member_name: str
    ) -> io.BytesIO | None:
        try:
            if banner_data:
                banner_img = Image.open(banner_data)
            else:
                banner_img = Image.new(
                    "RGB", (DISCORD_BANNER_WIDTH, DISCORD_BANNER_HEIGHT), color="black"
                )
                print("Debug: No banner_data provided, creating black fallback banner.")

            if avatar_data:
                avatar_img_raw = Image.open(avatar_data)
            else:
                # 備用方案：如果沒有頭像資料，則使用一個透明的頭像佔位符
                avatar_img_raw = Image.new("RGBA", (128, 128), color=(0, 0, 0, 0))
                print(
                    "Debug: No avatar_data provided, creating transparent fallback avatar."
                )

            if avatar_img_raw.mode != "RGBA":
                avatar_img_raw = avatar_img_raw.convert("RGBA")

            output_frames = []
            frame_durations = []
            is_output_gif = False

            banner_is_animated = (
                hasattr(banner_img, "is_animated") and banner_img.is_animated
            )
            avatar_is_animated = (
                hasattr(avatar_img_raw, "is_animated")
                and avatar_img_raw.is_animated  # 注意這裡用 avatar_img_raw
            )
            print(
                f"Debug: Banner is animated: {banner_is_animated}, Avatar is animated: {avatar_is_animated}"
            )

            final_avatar_display_size = AVATAR_TARGET_SIZE + AVATAR_BORDER_WIDTH * 2

            if banner_is_animated or avatar_is_animated:
                is_output_gif = True

                banner_frames_raw = [
                    f.copy().convert("RGBA") for f in ImageSequence.Iterator(banner_img)
                ]
                banner_frames = []
                for frame in banner_frames_raw:
                    original_width, original_height = frame.size
                    target_aspect_ratio = DISCORD_BANNER_WIDTH / DISCORD_BANNER_HEIGHT
                    original_aspect_ratio = original_width / original_height

                    if original_aspect_ratio > target_aspect_ratio:
                        new_height = DISCORD_BANNER_HEIGHT
                        new_width = int(original_width * (new_height / original_height))
                        resized_frame = frame.resize(
                            (new_width, new_height), Image.Resampling.LANCZOS
                        )

                        left = (new_width - DISCORD_BANNER_WIDTH) / 2
                        top = 0
                        right = (new_width + DISCORD_BANNER_WIDTH) / 2
                        bottom = DISCORD_BANNER_HEIGHT
                        cropped_frame = resized_frame.crop((left, top, right, bottom))
                    else:
                        new_width = DISCORD_BANNER_WIDTH
                        new_height = int(original_height * (new_width / original_width))
                        resized_frame = frame.resize(
                            (new_width, new_height), Image.Resampling.LANCZOS
                        )

                        left = 0
                        top = (new_height - DISCORD_BANNER_HEIGHT) / 2
                        right = DISCORD_BANNER_WIDTH
                        bottom = (new_height + DISCORD_BANNER_HEIGHT) / 2
                        cropped_frame = resized_frame.crop((left, top, right, bottom))

                    banner_frames.append(cropped_frame)

                banner_durations = [
                    banner_img.info.get("duration", 100) for _ in banner_frames_raw
                ]
                print(
                    f"Debug: Banner (processed) has {len(banner_frames)} frames, durations: {banner_durations}"
                )

                avatar_frames_raw = [
                    f.copy().convert("RGBA")
                    for f in ImageSequence.Iterator(avatar_img_raw)
                ]
                avatar_frames_processed = []
                for frame in avatar_frames_raw:
                    processed_avatar = self.round_avatar_with_border(
                        frame,
                        AVATAR_TARGET_SIZE,
                        AVATAR_BORDER_WIDTH,
                        AVATAR_BORDER_COLOR,
                    )
                    avatar_frames_processed.append(processed_avatar)

                avatar_durations = [
                    avatar_img_raw.info.get("duration", 100) for _ in avatar_frames_raw
                ]

                max_frames = max(len(banner_frames), len(avatar_frames_processed))
                print(f"Debug: Max frames for output GIF: {max_frames}")

                for i in range(max_frames):
                    current_banner_frame = banner_frames[i % len(banner_frames)]
                    current_avatar_frame = avatar_frames_processed[
                        i % len(avatar_frames_processed)
                    ]

                    # x_pos = (DISCORD_BANNER_WIDTH - final_avatar_display_size) // 2
                    x_pos = 30
                    y_pos = (DISCORD_BANNER_HEIGHT - final_avatar_display_size) // 2

                    composite_frame = current_banner_frame.copy()
                    composite_frame.paste(
                        current_avatar_frame,
                        (x_pos, y_pos),
                        current_avatar_frame,  # paste with alpha mask
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
                    codec="gifski",
                )
                output_buffer.seek(0)
                return output_buffer

            else:  # Process static images, like PNG or JPEG
                original_width, original_height = banner_img.size
                target_aspect_ratio = DISCORD_BANNER_WIDTH / DISCORD_BANNER_HEIGHT
                original_aspect_ratio = original_width / original_height

                if original_aspect_ratio > target_aspect_ratio:
                    new_height = DISCORD_BANNER_HEIGHT
                    new_width = int(original_width * (new_height / original_height))
                    resized_banner_img = banner_img.resize(
                        (new_width, new_height), Image.Resampling.LANCZOS
                    )

                    left = (new_width - DISCORD_BANNER_WIDTH) / 2
                    top = 0
                    right = (new_width + DISCORD_BANNER_WIDTH) / 2
                    bottom = DISCORD_BANNER_HEIGHT
                    cropped_banner_img = resized_banner_img.crop(
                        (left, top, right, bottom)
                    )
                else:
                    new_width = DISCORD_BANNER_WIDTH
                    new_height = int(original_height * (new_width / original_width))
                    resized_banner_img = banner_img.resize(
                        (new_width, new_height), Image.Resampling.LANCZOS
                    )

                    left = 0
                    top = (new_height - DISCORD_BANNER_HEIGHT) / 2
                    right = DISCORD_BANNER_WIDTH
                    bottom = (new_height + DISCORD_BANNER_HEIGHT) / 2
                    cropped_banner_img = resized_banner_img.crop(
                        (left, top, right, bottom)
                    )

                banner_img_final = cropped_banner_img

                # Border and round the avatar
                avatar_img_processed = self.round_avatar_with_border(
                    avatar_img_raw,
                    AVATAR_TARGET_SIZE,
                    AVATAR_BORDER_WIDTH,
                    AVATAR_BORDER_COLOR,
                )

                # x_pos = (DISCORD_BANNER_WIDTH - final_avatar_display_size) // 2
                x_pos = 30
                y_pos = (DISCORD_BANNER_HEIGHT - final_avatar_display_size) // 2

                composite_img = banner_img_final.copy().convert("RGBA")
                composite_img.paste(
                    avatar_img_processed, (x_pos, y_pos), avatar_img_processed
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

        original_member = member or interaction.user
        guild = interaction.guild

        full_member = None
        if guild:
            try:
                full_member = await guild.fetch_member(original_member.id)
                print(
                    f"Debug: Successfully fetched full member data for {original_member.name} from guild."
                )
            except discord.NotFound:
                print(
                    f"Debug: Member {original_member.id} not found in guild cache, will try fetch_user."
                )
            except discord.HTTPException as e:
                print(
                    f"Debug: HTTP error fetching member {original_member.id} from guild: {e}"
                )

        if not full_member:
            try:
                full_member = await self.bot.fetch_user(original_member.id)
                print(
                    f"Debug: Successfully fetched user data for {original_member.name} directly."
                )
            except discord.NotFound:
                print(f"Debug: User {original_member.id} not found via bot.fetch_user.")
                full_member = original_member
                print(
                    f"Debug: Falling back to original member object due to fetch failure."
                )
            except discord.HTTPException as e:
                print(f"Debug: HTTP error fetching user {original_member.id}: {e}")
                full_member = original_member
                print(
                    f"Debug: Falling back to original member object due to fetch error."
                )

        member_to_use = full_member
        print(
            f"Debug: Final member object for processing: {member_to_use.name} (ID: {member_to_use.id})"
        )

        avatar_url = member_to_use.display_avatar.url
        print(f"Debug: Member avatar URL: {avatar_url}")

        print(f"Debug: member_to_use.banner object: {member_to_use.banner}")
        if member_to_use.banner:
            banner_url = member_to_use.banner.url
            print(f"Debug: User has custom banner. URL: {banner_url}")
        else:
            banner_url = DEFAULT_BANNER_URL
            print(
                f"Debug: User has NO custom banner (member_to_use.banner is None). Using DEFAULT_BANNER_URL: {banner_url}"
            )

        avatar_data = await self.download_image(avatar_url)
        banner_data = await self.download_image(banner_url)

        processed_image_buffer = await asyncio.to_thread(
            self.process_image_sync,
            banner_data,
            avatar_data,
            member_to_use.display_name,
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
            title=f"👤 {member_to_use.display_name} 的個人資訊",
            color=discord.Color.pink(),
            timestamp=datetime.utcnow(),
        )

        embed.set_author(
            name=f"{member_to_use.name}#{member_to_use.discriminator}",
            icon_url=member_to_use.display_avatar.url,
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

        if isinstance(member_to_use, discord.Member):
            joined_at = (
                member_to_use.joined_at.strftime("%Y/%m/%d %H:%M")
                if member_to_use.joined_at
                else "未知"
            )
            roles = [
                role.mention for role in member_to_use.roles if role.name != "@everyone"
            ]
            roles_str = ", ".join(roles) if roles else "無"
            embed.add_field(name="📥 加入伺服器時間", value=joined_at, inline=True)
            embed.add_field(name="🎭 擁有的身分組", value=roles_str, inline=False)
        else:
            embed.add_field(
                name="📥 加入伺服器時間", value="不在伺服器內或無法獲取", inline=True
            )
            embed.add_field(
                name="🎭 擁有的身分組", value="不在伺服器內或無法獲取", inline=False
            )

        created_at = member_to_use.created_at.strftime("%Y/%m/%d %H:%M")

        embed.add_field(name="🆔 使用者 ID", value=str(member_to_use.id), inline=False)
        embed.add_field(name="📅 加入 Discord 時間", value=created_at, inline=True)

        embed.set_footer(
            text=f"由 {interaction.user.display_name} 查詢",
            icon_url=interaction.user.display_avatar.url,
        )

        if file:
            await interaction.followup.send(embed=embed, file=file)
            print("Debug: Sent embed with file.")
        else:
            await interaction.followup.send(embed=embed)
            print("Debug: Sent embed without file (due to error).")


async def setup(bot: commands.Bot):
    await bot.add_cog(UserProfile(bot))
