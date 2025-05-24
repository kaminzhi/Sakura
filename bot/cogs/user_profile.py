import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import io, warnings
import asyncio, math
import aiohttp
import imageio.v3 as iio
from PIL import Image, ImageSequence, ImageDraw, ImageFont, ImageFilter
import os, logging

from bot.utils.database import get_guild_data

# --- Constants (unchanged) ---
DISCORD_BANNER_WIDTH = 600
DISCORD_BANNER_HEIGHT = 240
AVATAR_TARGET_SIZE = 140
AVATAR_BORDER_WIDTH = 5
MISTY_LAYER_COLOR = (0, 0, 0, 80)
FONT_DIR = "fonts"
FONT_FALLBACK_PATHS = [
    os.path.join(FONT_DIR, "cute.ttf"),
    os.path.join(FONT_DIR, "setofont.ttf"),
]
USERNAME_FONT_SIZE = 65
DISCRIMINATOR_FONT_SIZE = 40
DATE_FONT_SIZE = 16
TEXT_COLOR = (255, 255, 255, 255)
LINE_SPACING = 15

warnings.filterwarnings("ignore", category=UserWarning, module="imageio.plugins.pillow")


class UserProfile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not hasattr(self.bot, "session") or not isinstance(
            self.bot.session, aiohttp.ClientSession
        ):
            self.bot.session = aiohttp.ClientSession()
            print("Debug: Initialized bot.session within UserProfile cog.")

        warnings.filterwarnings(
            "ignore", category=UserWarning, module="imageio.plugins.pillow"
        )

        self.username_fonts = self._load_fonts(USERNAME_FONT_SIZE)
        self.discriminator_fonts = self._load_fonts(DISCRIMINATOR_FONT_SIZE)
        self.date_fonts = self._load_fonts(DATE_FONT_SIZE)

    def _load_fonts(self, size: int):
        fonts = []
        for font_path in FONT_FALLBACK_PATHS:
            try:
                font = ImageFont.truetype(font_path, size)
                fonts.append(font)
            except IOError:
                logging.error(
                    f"Warning: Could not load font from {font_path}. Skipping."
                )
            except Exception as e:
                logging.error(f"Error loading font {font_path}: {e}")

        if not fonts:
            logging.error("Error: No fonts loaded, falling back to default PIL font.")
            fonts.append(ImageFont.load_default())
        return fonts

    def _get_font_for_char(self, char: str, font_list: list[ImageFont.FreeTypeFont]):
        for font in font_list:
            if font.getmask(char).getbbox():
                return font
        return font_list[0]

    def _draw_text_with_fallback(
        self,
        draw: ImageDraw.ImageDraw,
        xy: tuple,
        text: str,
        font_list: list[ImageFont.FreeTypeFont],
        fill: tuple,
    ):
        x, y = xy
        for char in text:
            char_font = self._get_font_for_char(char, font_list)
            draw.text((x, y), char, font=char_font, fill=fill)
            char_width = char_font.getlength(char)
            x += char_width

    async def cog_unload(self):
        if (
            hasattr(self.bot, "session")
            and self.bot.session
            and self.bot.session._owner
        ):
            await self.bot.session.close()

    async def download_image(self, url: str) -> io.BytesIO | None:
        if not url:
            return None
        try:
            async with self.bot.session.get(url) as response:
                response.raise_for_status()
                image_bytes = await response.read()
                return io.BytesIO(image_bytes)
        except aiohttp.ClientError as e:
            logging.error(f"Error downloading image from {url}: {e}")
            return None

    def round_avatar(
        self, avatar_img: Image.Image, size: int, border_width: int
    ) -> Image.Image:
        avatar_resized = avatar_img.resize((size, size), Image.Resampling.LANCZOS)

        mask_size = size * 4
        mask = Image.new("L", (mask_size, mask_size), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, mask_size, mask_size), fill=255)
        mask = mask.resize((size, size), Image.Resampling.LANCZOS)

        rounded_avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rounded_avatar.paste(avatar_resized, (0, 0), mask)

        shadow_spread = border_width * 2.0
        shadow_blur_radius = border_width * 1.5
        shadow_offset_x = border_width * 0.75
        shadow_offset_y = border_width * 0.75
        shadow_alpha = 150

        canvas_size = int(size + shadow_spread * 2)
        composite_image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

        shadow_base_size = int(size + shadow_spread)

        shadow_source_canvas_size = int(shadow_base_size + shadow_blur_radius * 2)
        raw_shadow_source = Image.new(
            "RGBA", (shadow_source_canvas_size, shadow_source_canvas_size), (0, 0, 0, 0)
        )
        draw_raw_shadow = ImageDraw.Draw(raw_shadow_source)

        ellipse_x1 = (shadow_source_canvas_size - shadow_base_size) / 2
        ellipse_y1 = (shadow_source_canvas_size - shadow_base_size) / 2
        ellipse_x2 = ellipse_x1 + shadow_base_size
        ellipse_y2 = ellipse_y1 + shadow_base_size

        draw_raw_shadow.ellipse(
            (ellipse_x1, ellipse_y1, ellipse_x2, ellipse_y2),
            fill=(0, 0, 0, shadow_alpha),
        )

        shadow_blurred = raw_shadow_source.filter(
            ImageFilter.GaussianBlur(radius=shadow_blur_radius)
        )

        shadow_paste_x = int(
            (canvas_size - shadow_source_canvas_size) / 2 + shadow_offset_x
        )
        shadow_paste_y = int(
            (canvas_size - shadow_source_canvas_size) / 2 + shadow_offset_y
        )

        composite_image.paste(
            shadow_blurred, (shadow_paste_x, shadow_paste_y), shadow_blurred
        )

        avatar_x_pos = int((canvas_size - size) / 2)
        avatar_y_pos = int((canvas_size - size) / 2)

        composite_image.paste(
            rounded_avatar, (avatar_x_pos, avatar_y_pos), rounded_avatar
        )

        return composite_image

    def _prepare_banner_frame(self, frame: Image.Image) -> Image.Image:
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
        return cropped_frame.convert("RGBA")

    def _get_image_frames_and_durations(self, img: Image.Image):
        frames = []
        durations = []
        for f in ImageSequence.Iterator(img):
            frames.append(f.copy().convert("RGBA"))
            duration = f.info.get("duration", 100)
            try:
                duration = int(duration)
                if duration <= 0:
                    duration = 100
            except (ValueError, TypeError):
                duration = 100
            durations.append(duration)
        return frames, durations

    def _draw_profile_text(
        self,
        draw: ImageDraw.ImageDraw,
        avatar_final_display_size: int,
        text_x: int,
        username_line_1: str,
        username_line_2: str,
        display_date_text: str,
    ):
        # Calculate text positions
        sample_font_username1 = (
            self.username_fonts[0] if self.username_fonts else ImageFont.load_default()
        )
        sample_font_username2 = (
            self.discriminator_fonts[0]
            if self.discriminator_fonts
            else ImageFont.load_default()
        )
        sample_font_date = (
            self.date_fonts[0] if self.date_fonts else ImageFont.load_default()
        )

        username_line_1_bbox = draw.textbbox(
            (0, 0), username_line_1, font=sample_font_username1
        )
        username_line_1_height = username_line_1_bbox[3] - username_line_1_bbox[1]

        username_line_2_bbox = draw.textbbox(
            (0, 0), username_line_2, font=sample_font_username2
        )
        username_line_2_height = username_line_2_bbox[3] - username_line_2_bbox[1]

        total_text_height = (
            username_line_1_height + username_line_2_height + LINE_SPACING
        )

        username_y_1 = (DISCORD_BANNER_HEIGHT - avatar_final_display_size) // 2 + (
            avatar_final_display_size - total_text_height
        ) // 2
        username_y_2 = username_y_1 + username_line_1_height + LINE_SPACING

        # Draw username and discriminator
        self._draw_text_with_fallback(
            draw,
            (text_x, username_y_1),
            username_line_1,
            self.username_fonts,
            TEXT_COLOR,
        )
        self._draw_text_with_fallback(
            draw,
            (text_x, username_y_2),
            username_line_2,
            self.discriminator_fonts,
            TEXT_COLOR,
        )

        # Draw date
        date_text_bbox = draw.textbbox((0, 0), display_date_text, font=sample_font_date)
        date_width = date_text_bbox[2] - date_text_bbox[0]
        date_height = date_text_bbox[3] - date_text_bbox[1]

        date_x = DISCORD_BANNER_WIDTH - date_width - 10
        date_y = DISCORD_BANNER_HEIGHT - date_height - 10
        self._draw_text_with_fallback(
            draw,
            (date_x, date_y),
            display_date_text,
            self.date_fonts,
            TEXT_COLOR,
        )

    def process_image_sync(
        self,
        banner_data: io.BytesIO,
        avatar_data: io.BytesIO,
        target_user_display_name: str,
        target_user_name: str,
        target_user_discriminator: str,
        created_at_date_str: str,
        generate_gif: bool,
    ) -> io.BytesIO | None:
        try:
            banner_img = Image.open(banner_data)
            avatar_img_raw = Image.open(avatar_data)

            output_frames = []
            frame_durations = []

            banner_is_animated = (
                hasattr(banner_img, "is_animated") and banner_img.is_animated
            )
            avatar_is_animated = (
                hasattr(avatar_img_raw, "is_animated") and avatar_img_raw.is_animated
            )

            should_generate_gif = generate_gif and (
                banner_is_animated or avatar_is_animated
            )

            temp_processed_avatar = self.round_avatar(
                avatar_img_raw.copy(), AVATAR_TARGET_SIZE, AVATAR_BORDER_WIDTH
            )
            avatar_final_display_size = temp_processed_avatar.width

            misty_layer = Image.new(
                "RGBA", (DISCORD_BANNER_WIDTH, DISCORD_BANNER_HEIGHT), MISTY_LAYER_COLOR
            )

            username_line_1 = target_user_display_name
            username_line_2 = (
                f"@{target_user_name}"
                if target_user_discriminator == "0"
                else f"#{target_user_discriminator}"
            )
            display_date_text = created_at_date_str

            if should_generate_gif:
                banner_frames, banner_durations = self._get_image_frames_and_durations(
                    banner_img
                )
                avatar_frames_raw, avatar_durations = (
                    self._get_image_frames_and_durations(avatar_img_raw)
                )

                avatar_frames_processed = [
                    self.round_avatar(f, AVATAR_TARGET_SIZE, AVATAR_BORDER_WIDTH)
                    for f in avatar_frames_raw
                ]

                max_frames = max(len(banner_frames), len(avatar_frames_processed))

                for i in range(max_frames):
                    current_banner_frame = banner_frames[i % len(banner_frames)]
                    current_avatar_frame = avatar_frames_processed[
                        i % len(avatar_frames_processed)
                    ]

                    composite_frame = self._prepare_banner_frame(
                        current_banner_frame
                    ).copy()
                    draw = ImageDraw.Draw(composite_frame)

                    composite_frame.paste(misty_layer, (0, 0), misty_layer)

                    x_pos = 30
                    y_pos = (DISCORD_BANNER_HEIGHT - avatar_final_display_size) // 2
                    composite_frame.paste(
                        current_avatar_frame, (x_pos, y_pos), current_avatar_frame
                    )

                    text_x = x_pos + avatar_final_display_size + 20
                    self._draw_profile_text(
                        draw,
                        avatar_final_display_size,
                        text_x,
                        username_line_1,
                        username_line_2,
                        display_date_text,
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
                    palettsize=64,
                )
                output_buffer.seek(0)
                return output_buffer

            else:
                banner_img_final = self._prepare_banner_frame(banner_img)

                if avatar_is_animated:
                    avatar_img_raw.seek(0)
                    static_avatar_frame = avatar_img_raw.convert("RGBA")
                    avatar_img_processed = self.round_avatar(
                        static_avatar_frame, AVATAR_TARGET_SIZE, AVATAR_BORDER_WIDTH
                    )
                else:
                    avatar_img_processed = self.round_avatar(
                        avatar_img_raw, AVATAR_TARGET_SIZE, AVATAR_BORDER_WIDTH
                    )

                composite_img = banner_img_final.copy()
                draw = ImageDraw.Draw(composite_img)

                composite_img.paste(misty_layer, (0, 0), misty_layer)

                x_pos = 30
                y_pos = (DISCORD_BANNER_HEIGHT - avatar_final_display_size) // 2
                composite_img.paste(
                    avatar_img_processed, (x_pos, y_pos), avatar_img_processed
                )

                text_x = x_pos + avatar_final_display_size + 20
                self._draw_profile_text(
                    draw,
                    avatar_final_display_size,
                    text_x,
                    username_line_1,
                    username_line_2,
                    display_date_text,
                )

                output_buffer = io.BytesIO()
                composite_img.save(output_buffer, format="PNG")
                output_buffer.seek(0)
                print("Debug: Successfully created PNG output.")
                return output_buffer

        except Exception as e:
            print(f"Debug: Error in process_image_sync for {target_user_name}: {e}")
            import traceback

            traceback.print_exc()
            return None

    @app_commands.command(
        name="user-profile",
        description="查詢用戶資訊",
    )
    async def user_profile(
        self, interaction: discord.Interaction, member: discord.Member = None
    ):
        await interaction.response.defer()

        original_member = member or interaction.user
        guild = interaction.guild

        member_to_use = original_member
        if guild:
            try:
                full_member = await guild.fetch_member(original_member.id)
                member_to_use = full_member
            except (discord.NotFound, discord.HTTPException):
                try:
                    full_member = await self.bot.fetch_user(original_member.id)
                    member_to_use = full_member
                except (discord.NotFound, discord.HTTPException) as e:
                    logging.error(
                        f"Debug: Failed to fetch user {original_member.id}: {e}"
                    )

        guild_data = await get_guild_data(interaction.guild_id)
        custom_banner_url = guild_data.get("custom_banner_url")
        generate_gif_enabled = guild_data.get("generate_gif_profile_image", True)

        avatar_url = member_to_use.display_avatar.url
        user = await self.bot.fetch_user(member_to_use.id)

        banner_to_download_url = (
            user.banner.url if user.banner else (custom_banner_url or avatar_url)
        )

        avatar_data = await self.download_image(avatar_url)
        banner_data = await self.download_image(banner_to_download_url)

        created_at_str = (
            member_to_use.created_at.strftime("%Y/%m/%d %H:%M")
            if member_to_use.created_at
            else "未知日期"
        )

        processed_image_buffer = await asyncio.to_thread(
            self.process_image_sync,
            banner_data,
            avatar_data,
            member_to_use.display_name,
            member_to_use.name,
            member_to_use.discriminator,
            created_at_str,
            generate_gif_enabled,
        )

        file = None
        if processed_image_buffer:
            is_gif = processed_image_buffer.getvalue()[:4] == b"GIF8"
            filename = "user_profile.gif" if is_gif else "user_profile.png"
            file = discord.File(processed_image_buffer, filename=filename)
            logging.info(f"Debug: Output file prepared: {filename}")
        else:
            logging.error(
                "Debug: processed_image_buffer is None. File will not be attached."
            )

        embed = discord.Embed(
            title=f"**{member_to_use.display_name}** 的個人資訊",
            color=discord.Color.from_rgb(245, 140, 175),
            timestamp=datetime.utcnow(),
        )

        author_name = (
            member_to_use.name
            if member_to_use.discriminator == "0"
            else f"{member_to_use.name}#{member_to_use.discriminator}"
        )
        embed.set_author(
            name=f"查詢者：{interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )

        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        if file:
            embed.set_image(url=f"attachment://{file.filename}")
        else:
            embed.add_field(
                name="⚠️ **無法生成個人橫幅**",
                value="請確保用戶有設定橫幅，或伺服器有設定自定義橫幅。若無，將使用頭像作為替代橫幅。",
                inline=False,
            )

        # Row 1: User ID and Account Type (with a blank field for spacing)
        embed.add_field(
            name="🔗 **帳號 ID**", value=f"`{member_to_use.id}`", inline=True
        )
        user_type = "🤖 機器人" if member_to_use.bot else "👤 使用者"
        embed.add_field(name="✨ **此帳號的類型**", value=user_type, inline=True)
        embed.add_field(
            name="\u200b", value="\u200b", inline=True
        )  # Invisible field for spacing

        # Row 2: Account Created At and Joined Server At
        embed.add_field(name="📅 **加入Discord於**", value=created_at_str, inline=True)
        if isinstance(member_to_use, discord.Member) and guild:
            joined_at = (
                member_to_use.joined_at.strftime("%Y/%m/%d %H:%M")
                if member_to_use.joined_at
                else "未知"
            )
            embed.add_field(
                name=f"📥 **加入`{guild.name}`於**", value=joined_at, inline=True
            )
            embed.add_field(
                name="\u200b", value="\u200b", inline=True
            )  # Invisible field for spacing
        else:
            embed.add_field(
                name="📥 **加入伺服器於**",
                value="`該用戶目前不在本伺服器`",
                inline=True,
            )
            embed.add_field(
                name="\u200b", value="\u200b", inline=True
            )  # Invisible field for spacing

        # Row 3: Server Boosting and Roles
        if isinstance(member_to_use, discord.Member):
            boosting_status = (
                "💎 正在加成" if member_to_use.premium_since else "❌ 向未加成"
            )
            embed.add_field(
                name="🚀 **加成此伺服器**", value=boosting_status, inline=True
            )

            roles = [
                role.mention for role in member_to_use.roles if role.name != "@everyone"
            ]
            roles_str = ", ".join(roles) if roles else "無任何身分組"
            embed.add_field(name="🎭 **擁有的身分組**", value=roles_str, inline=True)
            embed.add_field(
                name="\u200b", value="\u200b", inline=True
            )  # Invisible field for spacing
        else:
            embed.add_field(
                name="🚀 **伺服器加成**",
                value="`無法獲取 (用戶不在伺服器)`",
                inline=True,
            )
            embed.add_field(
                name="🎭 **擁有的身分組**",
                value="`無法獲取 (用戶不在伺服器)`",
                inline=True,
            )
            embed.add_field(
                name="\u200b", value="\u200b", inline=True
            )  # Invisible field for spacing

        embed.set_footer(
            text=f"由 {self.bot.user.name} 提供服務",
            icon_url=self.bot.user.display_avatar.url,
        )

        if file:
            await interaction.followup.send(embed=embed, file=file)
            print("Debug: Sent embed with file.")
        else:
            await interaction.followup.send(embed=embed)
            print("Debug: Sent embed without file (due to error).")


async def setup(bot: commands.Bot):
    await bot.add_cog(UserProfile(bot))
